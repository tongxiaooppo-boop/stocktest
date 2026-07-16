"""
stock/metrics.py
技術與財務指標計算
讀取已對齊的母表，計算各項技術與財務指標
"""
import pandas as pd
import numpy as np


def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    計算技術指標
    
    v4.2 新增：
    - Vol_MA_20（20日均量）
    - MA_Med_Alignment（中期均線排列）
    - Foreign_5D_Net / Trust_5D_Net / Inst_Sync_Buy
    - MA20_Bias（20MA乖離率）
    - Vol_MA_Bullish（均量多頭排列）
    """
    result = df.copy()
    
    # === RSI_6 ===
    if "close" in result.columns:
        delta = result["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=6, min_periods=6).mean()
        avg_loss = loss.rolling(window=6, min_periods=6).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        result["RSI_6"] = 100 - (100 / (1 + rs))
    
    # === MA_Alignment ===
    if all(c in result.columns for c in ["close", "MA_5", "MA_10", "MA_20"]):
        conditions = [
            result["close"] > result["MA_5"],
            result["MA_5"] > result["MA_10"],
            result["MA_10"] > result["MA_20"],
        ]
        result["MA_Alignment"] = sum(conditions).astype(int)
    
    # === v4.2 MA_Med_Alignment（中期均線排列: MA5 > MA20 > MA60） ===
    if all(c in result.columns for c in ["MA_5", "MA_20", "MA_60"]):
        result["MA_Med_Alignment"] = (
            (result["MA_5"] > result["MA_20"]).astype(int) +
            (result["MA_20"] > result["MA_60"]).astype(int)
        )
    
    # === Volume_Ratio ===
    if "volume" in result.columns and "Vol_MA_5" in result.columns:
        result["Volume_Ratio"] = result["volume"] / result["Vol_MA_5"].replace(0, np.nan)
    
    # === v4.2 Vol_MA_20（20日均量） ===
    if "volume" in result.columns:
        result["Vol_MA_20"] = result["volume"].rolling(window=20, min_periods=20).mean()
    
    # === 法人買賣超 ===
    foreign_buy = None; foreign_sell = None
    trust_buy = None; trust_sell = None
    for col in result.columns:
        if "buy_Foreign_Investor" in col: foreign_buy = col
        elif "sell_Foreign_Investor" in col: foreign_sell = col
        elif "buy_Investment_Trust" in col: trust_buy = col
        elif "sell_Investment_Trust" in col: trust_sell = col
    
    if foreign_buy and foreign_sell:
        result["Foreign_Net"] = result[foreign_buy] - result[foreign_sell]
    if trust_buy and trust_sell:
        result["Trust_Net"] = result[trust_buy] - result[trust_sell]
    
    net_cols = [c for c in result.columns if c in ["Foreign_Net", "Trust_Net", "Dealer_Net"]]
    if len(net_cols) >= 2:
        result["Inst_Net"] = result[net_cols].sum(axis=1, min_count=1)
        result["Inst_5D_Net"] = result["Inst_Net"].rolling(5, min_periods=1).sum()
        result["Inst_20D_Net"] = result["Inst_Net"].rolling(20, min_periods=1).sum()
    
    # === v4.2 Foreign_5D_Net / Trust_5D_Net / Inst_Sync_Buy ===
    if "Foreign_Net" in result.columns and "Trust_Net" in result.columns:
        result["Foreign_5D_Net"] = result["Foreign_Net"].rolling(5, min_periods=1).sum()
        result["Trust_5D_Net"] = result["Trust_Net"].rolling(5, min_periods=1).sum()
        result["Inst_Sync_Buy"] = (
            (result["Foreign_5D_Net"] > 0) & (result["Trust_5D_Net"] > 0)
        ).astype(int)
    
    # === Chip_Divergence ===
    if "close" in result.columns and "Inst_5D_Net" in result.columns:
        price_high_5d = result["close"].rolling(5).max()
        price_low_5d = result["close"].rolling(5).min()
        result["Chip_Divergence"] = (
            ((result["close"] == price_high_5d) & (result["Inst_5D_Net"] < 0)) |
            ((result["close"] == price_low_5d) & (result["Inst_5D_Net"] > 0))
        ).astype(int)
    
    # === MA60_Bias ===
    if "close" in result.columns and "MA_60" in result.columns:
        result["MA60_Bias"] = (result["close"] - result["MA_60"]) / result["MA_60"].replace(0, np.nan)
    
    # === v4.2 MA20_Bias ===
    if "close" in result.columns and "MA_20" in result.columns:
        result["MA20_Bias"] = (result["close"] - result["MA_20"]) / result["MA_20"].replace(0, np.nan)
    
    # === Revenue_Momentum ===
    if "Revenue_YoY" in result.columns:
        result["Revenue_Accelerating"] = (
            result["Revenue_YoY"] > result["Revenue_YoY"].shift(1)
        ).astype(bool)
        acc = result["Revenue_Accelerating"].fillna(False)
        result["Revenue_Momentum"] = (acc & acc.shift(1) & acc.shift(2)).astype(int)
    
    # === Price_Revenue_Divergence ===
    if "close" in result.columns and "Revenue_YoY" in result.columns:
        price_high_20d = result["close"].rolling(20).max()
        price_low_20d = result["close"].rolling(20).min()
        rev_yoy_up = result["Revenue_YoY"] > result["Revenue_YoY"].shift(1)
        result["Price_Revenue_Divergence"] = (
            ((result["close"] == price_high_20d) & ~rev_yoy_up) |
            ((result["close"] == price_low_20d) & rev_yoy_up)
        ).astype(int)
    
    # === 融資券變化 ===
    margin_col = None; short_col = None
    for col in result.columns:
        if "MarginPurchaseTodayBalance" in col: margin_col = col
        elif "ShortSaleTodayBalance" in col: short_col = col
    if margin_col: result["Margin_5D_Change"] = result[margin_col].diff(5)
    if short_col: result["Short_5D_Change"] = result[short_col].diff(5)
    
    # === SBL_5D_Change ===
    sbl_col = None
    for col in result.columns:
        if "SBLShortSalesPreviousDayBalance" in col: sbl_col = col; break
    if sbl_col: result["SBL_5D_Change"] = result[sbl_col].diff(5)
    
    # === ATR ===
    if all(c in result.columns for c in ["high", "low", "close"]):
        prev_close = result["close"].shift(1)
        tr = pd.concat([
            (result["high"] - result["low"]).abs(),
            (result["high"] - prev_close).abs(),
            (result["low"] - prev_close).abs(),
        ], axis=1).max(axis=1)
        result["ATR"] = tr.rolling(window=14, min_periods=14).mean()
    
    # === Inst_Consecutive_Days ===
    if "Inst_Net" in result.columns:
        inst_pos = result["Inst_Net"] > 0
        consecutive = inst_pos.groupby((~inst_pos).cumsum()).cumcount() + 1
        result["Inst_Consecutive_Days"] = consecutive.where(inst_pos, 0)
    
    # === 價格 vs 均線 ===
    if "close" in result.columns:
        for ma in ["MA_5", "MA_10", "MA_20", "MA_60"]:
            if ma in result.columns:
                result[f"Above_{ma}"] = (result["close"] > result[ma]).astype(int)
        if all(m in result.columns for m in ["MA_5", "MA_10", "MA_20", "MA_60"]):
            result["Bullish_MA"] = (
                (result["MA_5"] > result["MA_10"]) & 
                (result["MA_10"] > result["MA_20"]) & 
                (result["MA_20"] > result["MA_60"])
            ).astype(int)
        if "Vol_MA_5" in result.columns:
            result["Volume_Above_MA5"] = (result["volume"] > result["Vol_MA_5"]).astype(int)
    
    # === v4.2 Vol_MA_Bullish（5日均量 > 20日均量） ===
    if "Vol_MA_5" in result.columns and "Vol_MA_20" in result.columns:
        result["Vol_MA_Bullish"] = (result["Vol_MA_5"] > result["Vol_MA_20"]).astype(int)
    
    return result


def _compute_quarterly_stability(result, col_name, source_col, window_quarters=20, min_periods=4):
    """在季度頻率計算標準差"""
    if source_col not in result.columns:
        return pd.Series(np.nan, index=result.index)
    s = result[source_col]
    is_new = pd.Series(False, index=result.index) | (s.diff().abs() > 1e-8)
    if pd.notna(s.iloc[0]): is_new.iloc[0] = True
    quarterly = result.loc[is_new, ["date", source_col]].dropna(subset=[source_col]).copy()
    if len(quarterly) < min_periods:
        return pd.Series(np.nan, index=result.index)
    quarterly = quarterly.sort_values("date")
    quarterly["_stability"] = quarterly[source_col].rolling(window=window_quarters, min_periods=min_periods).std()
    result_with_date = result[["date"]].copy()
    result_with_date = pd.merge_asof(
        result_with_date.sort_values("date"),
        quarterly[["date", "_stability"]].sort_values("date"),
        on="date", direction="backward",
    )
    return result_with_date["_stability"]


def _compute_quarterly_trend(result, col_name, source_col, lookback_quarters=20):
    """在季度頻率計算趨勢"""
    if source_col not in result.columns:
        return pd.Series(np.nan, index=result.index)
    s = result[source_col]
    is_new = pd.Series(False, index=result.index) | (s.diff().abs() > 1e-8)
    if pd.notna(s.iloc[0]): is_new.iloc[0] = True
    quarterly = result.loc[is_new, ["date", source_col]].dropna(subset=[source_col]).copy()
    if len(quarterly) < 2:
        return pd.Series(np.nan, index=result.index)
    quarterly = quarterly.sort_values("date")
    quarterly["_trend"] = quarterly[source_col].diff(lookback_quarters)
    result_with_date = result[["date"]].copy()
    result_with_date = pd.merge_asof(
        result_with_date.sort_values("date"),
        quarterly[["date", "_trend"]].sort_values("date"),
        on="date", direction="backward",
    )
    return result_with_date["_trend"]


def _compute_eps_yoy_quarterly(result, eps_col):
    """在季度頻率計算 EPS_YoY"""
    if eps_col not in result.columns:
        return pd.Series(np.nan, index=result.index)
    s = result[eps_col]
    is_new = pd.Series(False, index=result.index) | (s.diff().abs() > 1e-8)
    if pd.notna(s.iloc[0]): is_new.iloc[0] = True
    quarterly = result.loc[is_new, ["date", eps_col]].dropna(subset=[eps_col]).copy()
    if len(quarterly) < 5:
        return pd.Series(np.nan, index=result.index)
    quarterly = quarterly.sort_values("date").reset_index(drop=True)
    eps_prev = quarterly[eps_col].shift(4)
    eps_yoy = pd.Series(np.nan, index=quarterly.index)
    denom_valid = eps_prev.notna() & (eps_prev > 0)
    eps_yoy[denom_valid] = ((quarterly.loc[denom_valid, eps_col] - eps_prev[denom_valid]) / eps_prev[denom_valid]) * 100
    result_with_date = result[["date"]].copy()
    result_with_date = pd.merge_asof(
        result_with_date.sort_values("date"),
        pd.DataFrame({"date": quarterly["date"], "_eps_yoy": eps_yoy}).sort_values("date"),
        on="date", direction="backward",
    )
    return result_with_date["_eps_yoy"]


# ============================================================
# v4.2 新增：輔助運算
# ============================================================

def _compute_eps_qoq_quarterly(result, eps_col):
    """計算 EPS QoQ（季增率）"""
    if eps_col not in result.columns:
        return pd.Series(np.nan, index=result.index)
    s = result[eps_col]
    is_new = pd.Series(False, index=result.index) | (s.diff().abs() > 1e-8)
    if pd.notna(s.iloc[0]): is_new.iloc[0] = True
    quarterly = result.loc[is_new, ["date", eps_col]].dropna(subset=[eps_col]).copy()
    if len(quarterly) < 2:
        return pd.Series(np.nan, index=result.index)
    quarterly = quarterly.sort_values("date").reset_index(drop=True)
    eps_prev = quarterly[eps_col].shift(1)
    eps_qoq = pd.Series(np.nan, index=quarterly.index)
    denom_valid = eps_prev.notna() & (eps_prev > 0)
    eps_qoq[denom_valid] = ((quarterly.loc[denom_valid, eps_col] - eps_prev[denom_valid]) / eps_prev[denom_valid]) * 100
    eps_qoq[~denom_valid & eps_prev.notna() & (eps_prev < 0) & (quarterly[eps_col] > 0)] = 100
    result_with_date = result[["date"]].copy()
    result_with_date = pd.merge_asof(
        result_with_date.sort_values("date"),
        pd.DataFrame({"date": quarterly["date"], "_eps_qoq": eps_qoq}).sort_values("date"),
        on="date", direction="backward",
    )
    return result_with_date["_eps_qoq"]


def _compute_cagr_3y(result):
    """計算 3Y-CAGR（營收3年複合成長率）"""
    if "month_revenue" not in result.columns:
        return pd.Series(np.nan, index=result.index)
    s = result["month_revenue"]
    is_new = pd.Series(False, index=result.index) | (s.diff().abs() > 1e-4)
    if pd.notna(s.iloc[0]): is_new.iloc[0] = True
    monthly = result.loc[is_new, ["date", "month_revenue"]].dropna(subset=["month_revenue"]).copy()
    if len(monthly) < 36:
        return pd.Series(np.nan, index=result.index)
    monthly = monthly.sort_values("date").reset_index(drop=True)
    rev_now = monthly["month_revenue"].values
    rev_36m_ago = monthly["month_revenue"].shift(36).values
    cagr_3y = pd.Series(np.nan, index=monthly.index)
    mask = (rev_36m_ago > 0) & (rev_now > 0)
    cagr_3y[mask] = ((rev_now[mask] / rev_36m_ago[mask]) ** (1.0 / 3.0) - 1) * 100
    result_with_date = result[["date"]].copy()
    result_with_date = pd.merge_asof(
        result_with_date.sort_values("date"),
        pd.DataFrame({"date": monthly["date"], "_cagr_3y": cagr_3y}).sort_values("date"),
        on="date", direction="backward",
    )
    return result_with_date["_cagr_3y"]


def _compute_ocf_to_dividend(result):
    """計算營業現金流/股利比值"""
    if "TTM_OCF" not in result.columns or "cash_dividend_total" not in result.columns:
        return pd.Series(np.nan, index=result.index)
    return result["TTM_OCF"] / result["cash_dividend_total"].replace(0, np.nan)


def _compute_fcf_positive_quarters(result):
    """計算FCF連續為正季度數"""
    fcf_col = "TTM_FCF"
    if fcf_col not in result.columns:
        return pd.Series(np.nan, index=result.index)
    s = result[fcf_col]
    is_new = pd.Series(False, index=result.index) | (s.diff().abs() > 1e-4)
    if pd.notna(s.iloc[0]): is_new.iloc[0] = True
    quarterly = result.loc[is_new, ["date", fcf_col]].dropna(subset=[fcf_col]).copy()
    if len(quarterly) < 4:
        return pd.Series(np.nan, index=result.index)
    quarterly = quarterly.sort_values("date").reset_index(drop=True)
    fcf_positive = quarterly[fcf_col] > 0
    consecutive = 0
    for val in reversed(fcf_positive.values):
        if val: consecutive += 1
        else: break
    result["FCF_Positive_Quarters"] = consecutive
    return result["FCF_Positive_Quarters"]


def _compute_om_yoy_change(result):
    """計算營業利益率年變動"""
    if "Operating_Margin" not in result.columns:
        return pd.Series(np.nan, index=result.index)
    s = result["Operating_Margin"]
    is_new = pd.Series(False, index=result.index) | (s.diff().abs() > 1e-8)
    if pd.notna(s.iloc[0]): is_new.iloc[0] = True
    quarterly = result.loc[is_new, ["date", "Operating_Margin"]].dropna(subset=["Operating_Margin"]).copy()
    if len(quarterly) < 5:
        return pd.Series(np.nan, index=result.index)
    quarterly = quarterly.sort_values("date").reset_index(drop=True)
    om_change = quarterly["Operating_Margin"].diff(4)
    result_with_date = result[["date"]].copy()
    result_with_date = pd.merge_asof(
        result_with_date.sort_values("date"),
        pd.DataFrame({"date": quarterly["date"], "_om_yoy_change": om_change}).sort_values("date"),
        on="date", direction="backward",
    )
    return result_with_date["_om_yoy_change"]


# ============================================================
# 財務指標計算
# ============================================================

def calculate_financial_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    計算財務指標
    
    v4.2 新增運算：
    - EPS_QoQ（EPS季增率）
    - Revenue_3Y_CAGR（營收3年CAGR）
    - OCF_to_Dividend（營業現金流/股利）
    - FCF_Positive_Quarters（FCF連續為正季度數）
    - OM_YoY_Change（營益率年變動）
    - Operating_Margin_Stability（營益率穩定度）
    """
    result = df.copy()
    
    rev_col = gp_col = oi_col = ni_col = ta_col = eps_col = equity_col = liabilities_col = None
    for col in result.columns:
        if col == "Revenue": rev_col = col
        elif col == "GrossProfit": gp_col = col
        elif col == "OperatingIncome": oi_col = col
        elif col == "IncomeAfterTaxes": ni_col = col
        elif col == "TotalAssets": ta_col = col
        elif col == "EPS": eps_col = col
        elif col == "Equity": equity_col = col
        elif col == "Liabilities": liabilities_col = col
    
    # ROE_TTM
    if ni_col and equity_col:
        result["TTM_NetIncome"] = result[ni_col].rolling(window=4, min_periods=4).sum()
        result["ROE_TTM"] = (result["TTM_NetIncome"] / result[equity_col].replace(0, np.nan)) * 100
    
    # ROE_Stability
    result["ROE_Stability"] = _compute_quarterly_stability(result, "ROE_Stability", "ROE_TTM")
    
    # Gross_Margin
    if gp_col and rev_col:
        result["Gross_Margin"] = (result[gp_col] / result[rev_col].replace(0, np.nan)) * 100
    
    # Gross_Margin_Stability
    result["Gross_Margin_Stability"] = _compute_quarterly_stability(result, "Gross_Margin_Stability", "Gross_Margin")
    
    # Operating_Margin
    if oi_col and rev_col:
        result["Operating_Margin"] = (result[oi_col] / result[rev_col].replace(0, np.nan)) * 100
    
    # v4.2 Operating_Margin_Stability
    result["Operating_Margin_Stability"] = _compute_quarterly_stability(result, "Operating_Margin_Stability", "Operating_Margin")
    
    # ROA_TTM
    if "TTM_NetIncome" in result.columns and ta_col:
        result["ROA_TTM"] = (result["TTM_NetIncome"] / result[ta_col].replace(0, np.nan)) * 100
    
    # Current_Ratio
    ca = cl = None
    for col in result.columns:
        if col == "CurrentAssets": ca = col
        elif col == "CurrentLiabilities": cl = col
    if ca and cl: result["Current_Ratio"] = result[ca] / result[cl].replace(0, np.nan)
    
    # Interest_Coverage
    ie = None
    for col in result.columns:
        if col == "InterestExpense": ie = col; break
    if oi_col and ie: result["Interest_Coverage"] = result[oi_col] / result[ie].replace(0, np.nan)
    
    # EPS_Stability
    result["EPS_Stability"] = _compute_quarterly_stability(result, "EPS_Stability", "TTM_EPS")
    
    # EPS_YoY
    if eps_col:
        result["EPS_YoY"] = _compute_eps_yoy_quarterly(result, eps_col)
        result["EPS_YoY_Reason"] = np.where(result["EPS_YoY"].isna() & result[eps_col].notna(), "insufficient_history", "")
    
    # v4.2 EPS_QoQ
    if eps_col:
        result["EPS_QoQ"] = _compute_eps_qoq_quarterly(result, eps_col)
    
    # Debt_Ratio
    if liabilities_col and ta_col:
        result["Debt_Ratio"] = (result[liabilities_col] / result[ta_col].replace(0, np.nan)) * 100
    
    # Debt_Ratio_Trend
    result["Debt_Ratio_Trend"] = _compute_quarterly_trend(result, "Debt_Ratio_Trend", "Debt_Ratio", lookback_quarters=4)
    
    # Payout_Ratio
    if "cash_dividend_total" in result.columns:
        if "TTM_EPS" in result.columns:
            result["Payout_Ratio"] = (result["cash_dividend_total"] / result["TTM_EPS"].replace(0, np.nan)) * 100
        elif eps_col:
            result["Payout_Ratio"] = (result["cash_dividend_total"] / result[eps_col].replace(0, np.nan)) * 100
    
    # Payout_Ratio_Stability
    result["Payout_Ratio_Stability"] = _compute_quarterly_stability(result, "Payout_Ratio_Stability", "Payout_Ratio")
    
    # FCF_Coverage
    if "TTM_FCF" in result.columns and "cash_dividend_total" in result.columns:
        result["FCF_Coverage"] = result["TTM_FCF"] / result["cash_dividend_total"].replace(0, np.nan)
    
    # v4.2 OCF_to_Dividend
    result["OCF_to_Dividend"] = _compute_ocf_to_dividend(result)
    
    # FCF_vs_Dividend
    if "TTM_FCF" in result.columns and "cash_dividend_total" in result.columns:
        result["FCF_vs_Dividend"] = result["TTM_FCF"] - result["cash_dividend_total"]
    
    # v4.2 FCF_Positive_Quarters
    _compute_fcf_positive_quarters(result)
    
    # v4.2 Revenue_3Y_CAGR
    result["Revenue_3Y_CAGR"] = _compute_cagr_3y(result)
    
    # v4.2 OM_YoY_Change
    result["OM_YoY_Change"] = _compute_om_yoy_change(result)
    
    # Dividend_Continuity_Years
    if "cash_dividend_total" in result.columns and "year_num" in result.columns:
        div_data = result[["year_num", "cash_dividend_total"]].dropna(subset=["cash_dividend_total"])
        if not div_data.empty:
            yearly_div = div_data.groupby("year_num")["cash_dividend_total"].sum()
            consecutive = 0
            for year in sorted(yearly_div.index, reverse=True):
                if yearly_div[year] > 0: consecutive += 1
                else: break
            result["Dividend_Continuity_Years"] = consecutive
        else:
            result["Dividend_Continuity_Years"] = 0
    
    return result


# ============================================================
# Phase 1 新增：基礎統計工具函式
# ============================================================

def ols_slope(y_series, window: int = 20, min_periods: int = 15) -> pd.Series:
    """
    計算 rolling OLS 斜率（最小二乘法迴歸斜率）
    
    對 y_series 以 window 為滾動視窗，對每個視窗內的資料點
    (x=0,1,2,...,window-1, y=series_values) 做線性迴歸，
    取斜率作為該視窗的趨勢強度。
    
    Parameters:
        y_series: pd.Series, 要計算斜率的序列
        window: int, 滾動視窗大小（預設 20）
        min_periods: int, 最小資料點數（預設 15）
    
    Returns:
        pd.Series: 每個時間點的 OLS 斜率（NaN 表示資料不足）
    """
    import numpy as np
    
    def _slope(y):
        """對一個視窗內的 y 值計算 OLS 斜率"""
        y_clean = y[~np.isnan(y)]
        if len(y_clean) < min_periods:
            return np.nan
        x = np.arange(len(y_clean))
        # 使用 np.polyfit 計算斜率（degree=1 回傳 [slope, intercept]）
        try:
            slope, _ = np.polyfit(x, y_clean, 1)
            return slope
        except (np.linalg.LinAlgError, ValueError):
            return np.nan
    
    return y_series.rolling(window=window, min_periods=min_periods).apply(
        _slope, raw=False
    )


def cagr(y_series, period: int) -> pd.Series:
    """
    計算年複合成長率 CAGR
    
    CAGR = (current / past)^(1 / years) - 1
    
    Parameters:
        y_series: pd.Series, 要計算 CAGR 的序列（如月營收、季 EPS）
        period: int, 往回推的期數（月營收用 12, 季 EPS 用 4）
    
    Returns:
        pd.Series: CAGR 值（百分比，如 0.15 表示 15%）
                    分母 <= 0 時回傳 NaN
    """
    if period <= 0:
        return pd.Series(np.nan, index=y_series.index)
    
    past = y_series.shift(period)
    
    # 防禦：分母 <= 0 或 current <= 0 時回傳 NaN
    valid = (past > 0) & (y_series > 0)
    result = pd.Series(np.nan, index=y_series.index)
    result[valid] = (y_series[valid] / past[valid]) ** (1.0 / period) - 1
    
    # 限制極端值，避免 inf
    result = result.replace([np.inf, -np.inf], np.nan)
    
    return result


def cv(y_series) -> pd.Series:
    """
    計算變異係數 CV = σ / μ
    
    用 rolling window 計算，window 大小為序列長度的 1/4（至少 4 期）。
    
    Parameters:
        y_series: pd.Series, 要計算 CV 的序列
    
    Returns:
        pd.Series: CV 值（無單位比值）
                    若平均值絕對值 < 0.05 則回傳 NaN（防止分母過小災難）
    """
    import numpy as np
    
    n = len(y_series)
    window = max(4, n // 4)
    
    def _cv(y):
        y_clean = y[~np.isnan(y)]
        if len(y_clean) < 4:
            return np.nan
        mean = np.nanmean(y_clean)
        std = np.nanstd(y_clean, ddof=1)
        # 防禦：若平均值接近 0，回傳 NaN
        if abs(mean) < 0.05:
            return np.nan
        return std / mean
    
    return y_series.rolling(window=window, min_periods=4).apply(_cv, raw=False)


if __name__ == "__main__":
    print("metrics.py v4.2 - 含所有 v4.2 新增運算")
    print("  - ols_slope(): rolling OLS 斜率")
    print("  - cagr(): 年複合成長率")
    print("  - cv(): 變異係數")
