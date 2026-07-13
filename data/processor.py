"""
data/processor.py
母表建構：頻率對齊、公告日對齊、長轉寬
全系統唯一負責「跨頻率資料對齊」的模組

對齊規則（依 v2.1 數據管線規格書 0.2 節）：
- 主索引頻率：日頻（以 TaiwanStockPrice 的 date 為主軸）
- 月營收：以 create_time（公告日）merge_asof(direction='backward') 對齊
- 季財報：以 date（公告日）merge_asof(direction='backward') 對齊
- 股利：以 AnnouncementDate（公告日）merge_asof(direction='backward') 對齊
- 本益比：以 date 直接 merge
- 籌碼面：以 date 直接 merge（日頻）
"""

import pandas as pd
import numpy as np
from scipy import stats


def _pivot_financial_statements(df: pd.DataFrame) -> pd.DataFrame:
    """
    將財報長格式（type/value/origin_name）轉為寬格式
    
    財報三表（損益表/資產負債表/現金流量表）在 FinMind 中都是長格式，
    每個 type 是一列，需要 pivot 成每個 type 是一個欄位。
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    # 取需要的欄位
    df = df[["date", "stock_id", "type", "value"]].copy()
    
    # 同一天同一 type 可能有多筆（不同季），取平均或最後一筆
    # 實際上 date 就是公告日，同一天公告的同一 type 應該只有一筆
    df = df.drop_duplicates(subset=["date", "stock_id", "type"])
    
    # Pivot：將 type 轉為欄位
    df_pivot = df.pivot_table(
        index=["date", "stock_id"],
        columns="type",
        values="value",
        aggfunc="first",
    ).reset_index()
    
    # 扁平化 MultiIndex columns
    df_pivot.columns = [str(col) if isinstance(col, tuple) and col[1] == "" 
                        else str(col[1]) if isinstance(col, tuple) 
                        else str(col) for col in df_pivot.columns]
    
    # 確保 date 是 datetime
    df_pivot["date"] = pd.to_datetime(df_pivot["date"])
    
    return df_pivot


def _prepare_revenue_with_announce(df: pd.DataFrame) -> pd.DataFrame:
    """
    準備月營收資料，使用 create_time 作為公告日
    
    月營收的 date 是所屬月份（例如 2026-06-01 代表 6月營收），
    但 create_time 才是實際公告日，對齊時要用 create_time。
    
    注意：FinMind 的 create_time 可能為空字串（舊資料），
    此時改用 date（所屬月份）作為公告日。
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    
    # 處理 create_time：可能為空字串或 NaN
    if "create_time" in df.columns:
        # 將空字串轉為 NaT
        df["create_time"] = pd.to_datetime(df["create_time"], errors="coerce")
        # 若 create_time 為 NaT，用 date 代替
        df["announce_date"] = df["create_time"].fillna(df["date"])
    else:
        df["announce_date"] = df["date"]
    
    return df


def _prepare_dividend_with_announce(df: pd.DataFrame) -> pd.DataFrame:
    """
    準備股利資料，使用 AnnouncementDate 作為公告日
    
    股利資料的 date 是除權息日，但 AnnouncementDate 才是實際公告日。
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    
    if "AnnouncementDate" in df.columns and df["AnnouncementDate"].notna().any():
        df["announce_date"] = pd.to_datetime(df["AnnouncementDate"])
    else:
        # 若無 AnnouncementDate，用 date 代替
        df["announce_date"] = df["date"]
    
    return df


def build_universal_base_table(
    df_price: pd.DataFrame,
    df_month_revenue: pd.DataFrame = None,
    df_financial: pd.DataFrame = None,
    df_balance: pd.DataFrame = None,
    df_cash_flow: pd.DataFrame = None,
    df_dividend: pd.DataFrame = None,
    df_per: pd.DataFrame = None,
    df_institutional: pd.DataFrame = None,
    df_margin: pd.DataFrame = None,
    df_short_sale: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    建構 Universal Base Table（萬用底層資料表）
    
    以日頻股價為主軸，將所有低頻資料以公告日 merge_asof(direction='backward') 對齊
    
    Parameters:
        df_price: 股價 DataFrame（主軸），需含 date, open, high, low, close, volume
        df_month_revenue: 月營收 DataFrame
        df_financial: 損益表 DataFrame（長格式）
        df_balance: 資產負債表 DataFrame（長格式）
        df_cash_flow: 現金流量表 DataFrame（長格式）
        df_dividend: 股利 DataFrame
        df_per: 本益比歷史 DataFrame
        df_institutional: 三大法人買賣超 DataFrame
        df_margin: 融資券 DataFrame
        df_short_sale: 借券 DataFrame
    
    Returns:
        對齊完成的母表 DataFrame
    """
    if df_price is None or df_price.empty:
        return pd.DataFrame()
    
    # 確保 date 是 datetime 且排序
    df_price = df_price.copy()
    df_price["date"] = pd.to_datetime(df_price["date"])
    df_price = df_price.sort_values("date").reset_index(drop=True)
    
    # 以股價為主軸（只取存在的欄位）
    price_cols = ["date", "stock_id", "open", "high", "low", "close", "volume"]
    for col in ["Trading_turnover", "trading_money", "spread"]:
        if col in df_price.columns:
            price_cols.append(col)
    base = df_price[price_cols].copy()
    
    # === 預先計算 Data_Years_Available（從原始財報日期計算，不受股價範圍限制） ===
    fin_dates = []
    for df_fin in [df_financial, df_balance, df_cash_flow]:
        if df_fin is not None and not df_fin.empty:
            fin_dates.extend(pd.to_datetime(df_fin["date"]).dropna().tolist())
    if fin_dates:
        fin_min = min(fin_dates)
        fin_max = max(fin_dates)
        data_years_available = round((fin_max - fin_min).days / 365.0, 1)
    else:
        data_years_available = 0.0
    
    # === 1. 月營收：以 create_time（公告日）對齊 ===
    if df_month_revenue is not None and not df_month_revenue.empty:
        df_rev = _prepare_revenue_with_announce(df_month_revenue)
        # 取每月最後一筆公告（同一個公告日可能有多筆）
        df_rev = df_rev.sort_values("announce_date").drop_duplicates(subset=["announce_date"], keep="last")
        
        # 在原始營收資料上計算 Revenue_YoY 和 Revenue_MoM（此時 revenue_year/revenue_month 有多個不同月份）
        df_rev = df_rev.copy()
        df_rev["revenue_year"] = df_rev["revenue_year"].astype(int)
        df_rev["revenue_month"] = df_rev["revenue_month"].astype(int)
        df_rev["this_year_key"] = df_rev["revenue_year"].astype(str) + "_" + df_rev["revenue_month"].astype(str)
        df_rev["last_year_key"] = (df_rev["revenue_year"] - 1).astype(str) + "_" + df_rev["revenue_month"].astype(str)
        last_year_rev = df_rev.set_index("this_year_key")["revenue"].to_dict()
        df_rev["last_year_revenue"] = df_rev["last_year_key"].map(last_year_rev)
        # Revenue_YoY 轉為百分比（0.3009 → 30.09），與評分門檻（整數百分比）一致
        df_rev["Revenue_YoY"] = ((df_rev["revenue"] - df_rev["last_year_revenue"]) / df_rev["last_year_revenue"]) * 100
        
        # Revenue_MoM：用原始營收資料按公告日排序後計算月增率
        df_rev = df_rev.sort_values("announce_date")
        df_rev["Revenue_MoM"] = df_rev["revenue"].pct_change() * 100
        df_rev["Revenue_MoM"] = df_rev["Revenue_MoM"].fillna(0)
        
        # 準備對齊用的欄位
        df_rev_align = df_rev[["announce_date", "revenue", "revenue_year", "revenue_month", "Revenue_YoY", "Revenue_MoM"]].copy()
        df_rev_align = df_rev_align.rename(columns={"announce_date": "date"})
        df_rev_align["date"] = pd.to_datetime(df_rev_align["date"])
        df_rev_align = df_rev_align.sort_values("date")
        
        # merge_asof backward：公告日當天及之後才看得到新營收
        base["date"] = pd.to_datetime(base["date"])
        base = pd.merge_asof(
            base.sort_values("date"),
            df_rev_align.sort_values("date"),
            on="date",
            direction="backward",
        )
        # 重新命名避免混淆
        base = base.rename(columns={
            "revenue": "month_revenue",
            "revenue_year": "revenue_year",
            "revenue_month": "revenue_month",
        })
    
    # === 2. 損益表：以 date（公告日）對齊 ===
    if df_financial is not None and not df_financial.empty:
        df_fin_pivot = _pivot_financial_statements(df_financial)
        if not df_fin_pivot.empty:
            # 移除 stock_id 避免與母表重複
            df_fin_pivot = df_fin_pivot.drop(columns=["stock_id"], errors="ignore")
            df_fin_pivot = df_fin_pivot.sort_values("date")
            base["date"] = pd.to_datetime(base["date"])
            base = pd.merge_asof(
                base.sort_values("date"),
                df_fin_pivot.sort_values("date"),
                on="date",
                direction="backward",
            )
    
    # === 3. 資產負債表：以 date（公告日）對齊 ===
    if df_balance is not None and not df_balance.empty:
        df_bal_pivot = _pivot_financial_statements(df_balance)
        if not df_bal_pivot.empty:
            # 移除 stock_id 避免與母表重複
            df_bal_pivot = df_bal_pivot.drop(columns=["stock_id"], errors="ignore")
            df_bal_pivot = df_bal_pivot.sort_values("date")
            base["date"] = pd.to_datetime(base["date"])
            base = pd.merge_asof(
                base.sort_values("date"),
                df_bal_pivot.sort_values("date"),
                on="date",
                direction="backward",
            )
    
    # === 4. 現金流量表：以 date（公告日）對齊 ===
    if df_cash_flow is not None and not df_cash_flow.empty:
        df_cf_pivot = _pivot_financial_statements(df_cash_flow)
        if not df_cf_pivot.empty:
            # 移除 stock_id 避免與母表重複
            df_cf_pivot = df_cf_pivot.drop(columns=["stock_id"], errors="ignore")
            df_cf_pivot = df_cf_pivot.sort_values("date")
            base["date"] = pd.to_datetime(base["date"])
            base = pd.merge_asof(
                base.sort_values("date"),
                df_cf_pivot.sort_values("date"),
                on="date",
                direction="backward",
            )
    
    # === 5. 股利：以 AnnouncementDate（公告日）對齊 ===
    if df_dividend is not None and not df_dividend.empty:
        df_div = _prepare_dividend_with_announce(df_dividend)
        if "year" in df_div.columns:
            # 解析 year 欄位：可能有多種格式
            def _parse_year(val):
                if pd.isna(val):
                    return None
                val_str = str(val).strip()
                import re
                matches = re.findall(r"\d+", val_str)
                if not matches:
                    return None
                num = int(matches[0])
                if num <= 150:
                    return num + 1911  # 民國年轉西元
                else:
                    return num  # 已經是西元年
            
            df_div["year_num"] = df_div["year"].apply(_parse_year)
            df_div = df_div.dropna(subset=["year_num"]).copy()
            df_div["year_num"] = df_div["year_num"].astype(int)
            
            # 年化處理：對同一年度的多筆配息（如季配息）加總
            # 先計算每筆的單次配息總額
            df_div["cash_dividend"] = df_div["CashEarningsDistribution"].fillna(0)
            df_div["cash_statutory"] = df_div["CashStatutorySurplus"].fillna(0)
            df_div["cash_total"] = df_div["cash_dividend"] + df_div["cash_statutory"]
            
            # 按 year_num 加總同一年度的所有配息
            yearly_div = df_div.groupby("year_num").agg({
                "cash_dividend": "sum",
                "cash_statutory": "sum",
                "cash_total": "sum",
                "announce_date": "max",  # 取該年度最後一次公告日
            }).reset_index()
            
            # 用年化後的資料 merge_asof
            df_div_align = yearly_div[["announce_date", "cash_dividend", "cash_statutory", "cash_total", "year_num"]].copy()
            df_div_align = df_div_align.rename(columns={"announce_date": "date"})
            df_div_align["date"] = pd.to_datetime(df_div_align["date"])
            df_div_align = df_div_align.sort_values("date")
            
            base["date"] = pd.to_datetime(base["date"])
            base = pd.merge_asof(
                base.sort_values("date"),
                df_div_align.sort_values("date"),
                on="date",
                direction="backward",
            )
    
    # === 6. 本益比歷史：以 date 直接 merge（日頻） ===
    if df_per is not None and not df_per.empty:
        df_per = df_per.copy()
        df_per["date"] = pd.to_datetime(df_per["date"])
        df_per = df_per.sort_values("date")
        # 取需要的欄位（FinMind 可能用 PER/PBR 或 pe_ratio/pb_ratio）
        per_cols = ["date"]
        # 標準化欄位名稱
        rename_map = {}
        for col in df_per.columns:
            if col.upper() == "PER":
                rename_map[col] = "pe_ratio"
            elif col.upper() == "PBR":
                rename_map[col] = "pb_ratio"
            elif col.lower() == "dividend_yield":
                rename_map[col] = "dividend_yield"
        if rename_map:
            df_per = df_per.rename(columns=rename_map)
        for col in ["pe_ratio", "pb_ratio", "dividend_yield"]:
            if col in df_per.columns:
                per_cols.append(col)
        
        base["date"] = pd.to_datetime(base["date"])
        base = pd.merge_asof(
            base.sort_values("date"),
            df_per[per_cols].sort_values("date"),
            on="date",
            direction="backward",
        )
    
    # === 7. 三大法人：以 date 直接 merge（日頻） ===
    if df_institutional is not None and not df_institutional.empty:
        df_inst = df_institutional.copy()
        df_inst["date"] = pd.to_datetime(df_inst["date"])
        # Pivot：將不同法人類別轉為欄位
        df_inst_pivot = df_inst.pivot_table(
            index=["date", "stock_id"],
            columns="name",
            values=["buy", "sell"],
            aggfunc="first",
        )
        df_inst_pivot.columns = [f"{col[0]}_{col[1]}" for col in df_inst_pivot.columns]
        df_inst_pivot = df_inst_pivot.reset_index()
        
        base["date"] = pd.to_datetime(base["date"])
        base = pd.merge_asof(
            base.sort_values("date"),
            df_inst_pivot.sort_values("date"),
            on="date",
            direction="backward",
            suffixes=("", "_inst"),
        )
    
    # === 8. 融資券：以 date 直接 merge（日頻） ===
    if df_margin is not None and not df_margin.empty:
        df_margin = df_margin.copy()
        df_margin["date"] = pd.to_datetime(df_margin["date"])
        margin_cols = ["date"]
        for col in ["MarginPurchaseTodayBalance", "ShortSaleTodayBalance",
                     "MarginPurchaseBuy", "MarginPurchaseSell",
                     "ShortSaleBuy", "ShortSaleSell"]:
            if col in df_margin.columns:
                margin_cols.append(col)
        
        base["date"] = pd.to_datetime(base["date"])
        base = pd.merge_asof(
            base.sort_values("date"),
            df_margin[margin_cols].sort_values("date"),
            on="date",
            direction="backward",
        )
    
    # === 9. 借券：以 date 直接 merge（日頻） ===
    if df_short_sale is not None and not df_short_sale.empty:
        df_ss = df_short_sale.copy()
        df_ss["date"] = pd.to_datetime(df_ss["date"])
        ss_cols = ["date"]
        for col in ["SBLShortSalesPreviousDayBalance", "SBLShortSalesShortSales",
                     "SBLShortSalesReturns", "SBLShortSalesCurrentDayBalance"]:
            if col in df_ss.columns:
                ss_cols.append(col)
        
        base["date"] = pd.to_datetime(base["date"])
        base = pd.merge_asof(
            base.sort_values("date"),
            df_ss[ss_cols].sort_values("date"),
            on="date",
            direction="backward",
        )
    
    # 移除重複的 stock_id 欄位
    stock_cols = [c for c in base.columns if c.startswith("stock_id") if c != "stock_id"]
    if len(stock_cols) > 0:
        base = base.loc[:, ~base.columns.duplicated()]
    
    # 將預先計算的 Data_Years_Available 寫入母表
    base["Data_Years_Available"] = data_years_available
    
    return base


def calculate_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    計算衍生欄位（MA、YoY、TTM、Percentile 等）
    含防呆邏輯（EPS 為負時 PE 設為 NaN、TTM_EPS_Valid 旗標等）
    
    依 v2.1 規格書 0.3 節：
    - MA_5/10/20/60: close.rolling()
    - Vol_MA_5: volume.rolling(5).mean()
    - Revenue_YoY: (當月營收 - 去年同月) / 去年同月
    - TTM_EPS: 最新4季單季EPS rolling(4).sum()
    - TTM_FCF: 4季累計營業現金流 - 4季累計資本支出
    - PE/PB_Percentile: 先過濾 EPS 為負的區間再計算
    - TTM_EPS_Valid: 不足4季標記 False
    - Data_Years_Available: 實際可用年數（用財報日期計算）
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    result = df.copy()
    
    # === 技術指標 ===
    # MA_5/10/20/60
    if "close" in result.columns:
        result["MA_5"] = result["close"].rolling(window=5, min_periods=5).mean()
        result["MA_10"] = result["close"].rolling(window=10, min_periods=10).mean()
        result["MA_20"] = result["close"].rolling(window=20, min_periods=20).mean()
        result["MA_60"] = result["close"].rolling(window=60, min_periods=60).mean()
        
        # High_5D/10D/20D（打分用：短線壓力位）
        result["High_5D"] = result["close"].rolling(window=5, min_periods=5).max()
        result["High_10D"] = result["close"].rolling(window=10, min_periods=10).max()
        result["High_20D"] = result["close"].rolling(window=20, min_periods=20).max()
    
    # Vol_MA_5
    if "volume" in result.columns:
        result["Vol_MA_5"] = result["volume"].rolling(window=5, min_periods=5).mean()
    
    # === 營收 MoM ===
    # Revenue_YoY 和 Revenue_MoM 已在 build_universal_base_table 中從原始營收資料計算並 merge_asof 到母表
    # 此處不再重複計算，避免母表所有 month_revenue 相同導致 pct_change = 0
    
    # === TTM EPS ===
    eps_col = None
    for col in result.columns:
        if col == "EPS":
            eps_col = col
            break
    
    if eps_col:
        result["TTM_EPS"] = result[eps_col].rolling(window=4, min_periods=4).sum()
        result["TTM_EPS_Valid"] = result[eps_col].rolling(window=4, min_periods=4).count() >= 4
    
    # === TTM FCF ===
    # 營業現金流 = CashFlowsFromOperatingActivities
    # 資本支出 = PropertyAndPlantAndEquipment（FinMind 用此代替 AcquisitionOfPPE）
    fcf_operating = None
    fcf_capex = None
    for col in result.columns:
        if col == "CashFlowsFromOperatingActivities":
            fcf_operating = col
        if col == "PropertyAndPlantAndEquipment":
            fcf_capex = col
    
    if fcf_operating and fcf_capex:
        result["TTM_OperatingCF"] = result[fcf_operating].rolling(window=4, min_periods=4).sum()
        result["TTM_CAPEX"] = result[fcf_capex].rolling(window=4, min_periods=4).sum()
        result["TTM_FCF"] = result["TTM_OperatingCF"] - result["TTM_CAPEX"]
    
    # === PE/PB Percentile ===
    # 先過濾 EPS 為負的區間再計算百分位
    if "pe_ratio" in result.columns:
        if eps_col:
            result["pe_ratio_valid"] = result["pe_ratio"].where(result[eps_col] > 0, np.nan)
        else:
            result["pe_ratio_valid"] = result["pe_ratio"]
        
        # 計算百分位（至少需 120 筆 = 約半年交易日，降低門檻讓1年資料也能算）
        valid_pe = result["pe_ratio_valid"].dropna()
        if len(valid_pe) >= 120:
            result["PE_Percentile"] = result["pe_ratio_valid"].rank(pct=True) * 100
        else:
            result["PE_Percentile"] = np.nan
    
    # === 用 TTM_EPS 覆蓋 pe_ratio，確保 PE 與 TTM_EPS 一致 ===
    # 原本 pe_ratio 是從 FinMind TaiwanStockPER 外抓的，
    # 但 TTM_EPS 是自己用 EPS rolling 4 季算的，兩者可能不一致。
    # 修正：用 close / TTM_EPS 重新計算 pe_ratio，確保評分邏輯一致。
    if "TTM_EPS" in result.columns and "close" in result.columns:
        ttm_eps_valid = result.get("TTM_EPS_Valid", pd.Series(True, index=result.index))
        mask = (result["TTM_EPS"] > 0) & ttm_eps_valid
        result["pe_ratio"] = np.where(
            mask,
            result["close"] / result["TTM_EPS"],
            result.get("pe_ratio", np.nan)  # TTM_EPS 無效時保留原始值
        )
        # 同步更新 pe_ratio_valid
        if "pe_ratio_valid" in result.columns:
            result["pe_ratio_valid"] = result["pe_ratio"].where(mask, np.nan)

    
    if "pb_ratio" in result.columns:
        valid_pb = result["pb_ratio"].dropna()
        if len(valid_pb) >= 120:
            result["PB_Percentile"] = result["pb_ratio"].rank(pct=True) * 100
        else:
            result["PB_Percentile"] = np.nan
    
    # === cash_dividend_total（現金股利總額） ===
    # 已在 build_universal_base_table 中按 year_num 加總年化（季配息×4）
    # 若 cash_total 存在則直接使用，否則從 cash_dividend + cash_statutory 加總
    if "cash_total" in result.columns:
        result["cash_dividend_total"] = result["cash_total"]
    elif "cash_dividend" in result.columns or "cash_statutory" in result.columns:
        div_cols = []
        if "cash_dividend" in result.columns:
            div_cols.append("cash_dividend")
        if "cash_statutory" in result.columns:
            div_cols.append("cash_statutory")
        if div_cols:
            result["cash_dividend_total"] = result[div_cols].sum(axis=1, min_count=1)
    
    # === TTM_OCF alias（打分用） ===
    if "TTM_OperatingCF" in result.columns:
        result["TTM_OCF"] = result["TTM_OperatingCF"]
    
    # === Data_Years_Available ===
    # 已在 build_universal_base_table 中從原始財報日期預先計算，
    # 此處保留該欄位不做覆蓋（若不存在則補計算）
    if "Data_Years_Available" not in result.columns:
        if eps_col is not None:
            eps_dates = result.loc[result[eps_col].notna(), "date"]
            if len(eps_dates) >= 2:
                years = (eps_dates.max() - eps_dates.min()).days / 365.0
                result["Data_Years_Available"] = round(years, 1)
            else:
                result["Data_Years_Available"] = 0.0
        elif "date" in result.columns:
            all_dates = result["date"].dropna()
            if len(all_dates) >= 2:
                years = (all_dates.max() - all_dates.min()).days / 365.0
                result["Data_Years_Available"] = round(years, 1)
            else:
                result["Data_Years_Available"] = 0.0
        else:
            result["Data_Years_Available"] = 0.0
    
    return result


if __name__ == "__main__":
    print("processor.py - 斷點 4 實作完成，請用 test_processor.py 測試")
