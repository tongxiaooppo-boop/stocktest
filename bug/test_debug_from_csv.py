"""
test_debug_from_csv.py
從 CSV 匯出檔讀取數據，執行評分引擎，輸出詳細評分明細

用途：
- 不用重新撈取資料，直接對已匯出的 CSV 執行評分
- 查看每個子項的原始數據 → 五級評分 → 加權分數
- 檢查資料完整性（哪些欄位缺失）
- 修改 scoring_config.py 後，快速驗證評分變化

用法：
  python test_debug_from_csv.py
  python test_debug_from_csv.py --file "g:/test/2026-07-12T01-52_export.csv"
  python test_debug_from_csv.py --file "g:/test/2026-07-12T02-15_export.csv" --verbose
"""
import sys
import os
import argparse

# 設定 stdout 為 UTF-8（避免 cp950 無法處理 emoji）
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

# 加入專案根目錄（bug/ 的上層 taiwan-stock-analyzer-v3/）
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)  # bug/ 的上層
sys.path.insert(0, project_root)

from core.scorer import get_all_scores, get_style_label
from core.advisor import get_advice


# ============================================================
# 中英欄位對照表（用於顯示）
# ============================================================
FIELD_CN_MAP = {
    "close": "收盤價", "volume": "成交量",
    "MA_5": "5日均線", "MA_10": "10日均線", "MA_20": "20日均線", "MA_60": "60日均線",
    "High_5D": "5日最高價", "High_10D": "10日最高價", "High_20D": "20日最高價",
    "Vol_MA_5": "5日均量", "RSI_6": "6日RSI", "MA_Alignment": "均線排列",
    "Volume_Ratio": "量比", "MA60_Bias": "60日乖離率", "ATR": "平均真實波幅",
    "Above_MA_5": "站上5日線", "Above_MA_10": "站上10日線",
    "Above_MA_20": "站上20日線", "Above_MA_60": "站上60日線",
    "Bullish_MA": "多頭排列", "Volume_Above_MA5": "量站上5日均量",
    "Foreign_Net": "外資買賣超", "Trust_Net": "投信買賣超", "Dealer_Net": "自營商買賣超",
    "Inst_Net": "三大法人合計", "Inst_5D_Net": "法人5日累計", "Inst_20D_Net": "法人20日累計",
    "Chip_Divergence": "籌碼背離", "Margin_5D_Change": "融資5日變化",
    "Short_5D_Change": "融券5日變化", "SBL_5D_Change": "借券5日變化",
    "Inst_Consecutive_Days": "法人連續天數",
    "month_revenue": "月營收", "revenue_year": "營收年度", "revenue_month": "營收月份",
    "Revenue_YoY": "營收年增率", "Revenue_MoM": "營收月增率",
    "Revenue_Accelerating": "營收加速", "Revenue_Momentum": "營收動能",
    "Price_Revenue_Divergence": "價量背離",
    "TTM_EPS": "近四季EPS", "TTM_EPS_Valid": "EPS有效性",
    "TTM_FCF": "近四季自由現金流", "TTM_OCF": "近四季營業現金流",
    "TTM_OperatingCF": "近四季營業現金流", "TTM_CAPEX": "近四季資本支出",
    "TTM_NetIncome": "近四季稅後淨利",
    "ROE_TTM": "近四季ROE", "ROE_Stability": "ROE穩定度", "ROA_TTM": "近四季ROA",
    "Gross_Margin": "毛利率", "Gross_Margin_Stability": "毛利率穩定度",
    "Operating_Margin": "營業利益率", "Current_Ratio": "流動比率",
    "Interest_Coverage": "利息保障倍數", "EPS_Stability": "EPS穩定度",
    "Debt_Ratio": "負債比", "Debt_Ratio_Trend": "負債比趨勢",
    "PE_Percentile": "本益比百分位", "PB_Percentile": "股價淨值比百分位",
    "pe_ratio": "本益比", "pb_ratio": "股價淨值比",
    "dividend_yield": "殖利率", "cash_dividend_total": "現金股利總額",
    "cash_dividend": "現金股利", "cash_statutory": "法定盈餘公積",
    "Payout_Ratio": "配息率", "Payout_Ratio_Stability": "配息率穩定度",
    "FCF_Coverage": "FCF覆蓋率", "FCF_vs_Dividend": "FCF/股利比",
    "Dividend_Continuity_Years": "連續配息年數", "Data_Years_Available": "資料可用年數",
}

# 評分需要的欄位（用於完整性檢查）
NEEDED_COLUMNS = {
    # 短線
    "close": "收盤價", "MA_5": "5日均線", "MA_10": "10日均線", "MA_20": "20日均線",
    "MA_60": "60日均線", "MA_Alignment": "均線排列分數", "volume": "成交量",
    "Vol_MA_5": "5日均量", "Vol_MA_20": "20日均量", "Volume_Ratio": "量比", "RSI_6": "6日RSI",
    "High_5D": "5日高點", "High_10D": "10日高點", "High_20D": "20日高點",
    "Inst_5D_Net": "5日法人淨買超", "Inst_20D_Net": "20日法人淨買超",
    "Foreign_Net": "外資淨買超", "Trust_Net": "投信淨買超",
    "Margin_5D_Change": "5日融資變化", "Short_5D_Change": "5日融券變化",
    "SBL_5D_Change": "5日借券變化", "MA60_Bias": "60日乖離率", "ATR": "平均真實波幅",
    # v4.2 短線新增
    "MA_Med_Alignment": "中期均線排列", "MA20_Bias": "20MA乖離率",
    "Foreign_5D_Net": "外資5日買超", "Trust_5D_Net": "投信5日買超",
    "Inst_Sync_Buy": "外資投信同步天數", "Vol_MA_Bullish": "均量多頭排列",
    # 波段
    "Revenue_YoY": "營收年增率", "Revenue_MoM": "營收月增率",
    "Revenue_Accelerating": "營收加速次數", "Revenue_Momentum": "營收動能",
    "TTM_EPS": "TTM EPS", "TTM_EPS_Valid": "TTM EPS 有效性",
    "PE_Percentile": "PE百分位", "PB_Percentile": "PB百分位",
    "Inst_Consecutive_Days": "法人連續買超天數",
    # v4.2 波段新增
    "EPS_QoQ": "EPS季增率", "Revenue_3Y_CAGR": "營收3年CAGR",
    "OCF_to_Dividend": "OCF/股利比值", "OM_YoY_Change": "營益率年變動",
    "Operating_Margin_Stability": "營益率穩定度",
    # 價值
    "ROE_TTM": "TTM ROE", "ROA_TTM": "TTM ROA", "Gross_Margin": "毛利率",
    "Debt_Ratio": "負債比", "Current_Ratio": "流動比率",
    "TTM_FCF": "TTM自由現金流", "TTM_OCF": "TTM營業現金流",
    "dividend_yield": "殖利率", "cash_dividend_total": "現金股利",
    # v4.2 價值新增
    "FCF_Positive_Quarters": "FCF連續為正季度數",
    # 定存
    "Dividend_Continuity_Years": "連續配息年數", "Payout_Ratio": "配息率",
    "FCF_Coverage": "FCF覆蓋倍數", "Interest_Coverage": "利息保障倍數",
    "ROE_Stability": "ROE穩定性", "EPS_Stability": "EPS穩定性",
    # 通用
    "Data_Years_Available": "資料年數",
}


def cn(val: str) -> str:
    """將英文欄位名稱轉為中文"""
    return FIELD_CN_MAP.get(val, val)


def load_csv(filepath: str) -> pd.DataFrame:
    """
    讀取 CSV 匯出檔，自動判斷格式
    
    支援三種格式：
    1. 格式A: 欄位,值（第一欄英文名，第二欄值）
    2. 格式B: 欄位名稱（英文）,中文對照,值（三欄）
    3. 格式C: 標準 DataFrame 格式（第一行英文欄位名，每列一筆資料）
    """
    if not os.path.exists(filepath):
        print(f"❌ 檔案不存在: {filepath}")
        sys.exit(1)
    
    # 先讀取前幾行判斷格式
    df_raw = pd.read_csv(filepath, encoding="utf-8-sig", nrows=3)
    cols = list(df_raw.columns)
    
    if len(cols) == 2:
        # 格式A: 欄位,值
        print(f"📄 偵測到格式A（2欄: 欄位, 值）")
        df = pd.read_csv(filepath, encoding="utf-8-sig")
        data = {}
        for _, row in df.iterrows():
            field = str(row.iloc[0]).strip()
            val = row.iloc[1]
            data[field] = val
        return pd.DataFrame([data])
    
    elif len(cols) == 3:
        # 格式B: 欄位名稱（英文）,中文對照,值
        print(f"📄 偵測到格式B（3欄: 英文, 中文, 值）")
        df = pd.read_csv(filepath, encoding="utf-8-sig")
        data = {}
        for _, row in df.iterrows():
            field = str(row.iloc[0]).strip()
            val = row.iloc[2]
            data[field] = val
        return pd.DataFrame([data])
    
    else:
        # 格式C: 標準 DataFrame 格式（多欄，第一行是英文欄位名）
        print(f"📄 偵測到格式C（{len(cols)}欄: 標準 DataFrame 格式）")
        df = pd.read_csv(filepath, encoding="utf-8-sig")
        # 嘗試轉數值型態
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        print(f"   ✅ 讀取 {len(df)} 行 x {len(df.columns)} 欄")
        return df


def check_data_completeness(df: pd.DataFrame):
    """檢查資料完整性：評分需要的欄位是否都存在"""
    print(f"\n{'='*70}")
    print("📋 資料完整性檢查")
    print(f"{'='*70}")
    
    available = []
    missing = []
    for col, desc in sorted(NEEDED_COLUMNS.items()):
        if col in df.columns:
            available.append(col)
        else:
            missing.append((col, desc))
    
    print(f"\n✅ 存在 ({len(available)}/{len(NEEDED_COLUMNS)}):")
    for col in available:
        val = df[col].iloc[0]
        val_str = f"{val:.4f}" if isinstance(val, float) else str(val)
        print(f"  {col:35s} ({cn(col):12s}) = {val_str}")
    
    if missing:
        print(f"\n❌ 缺少 ({len(missing)}/{len(NEEDED_COLUMNS)}):")
        for col, desc in missing:
            print(f"  {col:35s} ({desc})")
    
    print(f"\n📊 覆蓋率: {len(available)}/{len(NEEDED_COLUMNS)} = {len(available)/len(NEEDED_COLUMNS)*100:.0f}%")


def print_score_detail(style_key: str, style_cn: str, icon: str, scores: dict, verbose: bool = False):
    """輸出單一風格的詳細評分明細"""
    score_data = scores.get(style_key, {})
    total = score_data.get("total", 0)
    breakdown = score_data.get("breakdown", {})
    details = score_data.get("details", {})
    modifiers = score_data.get("modifiers", {})
    
    # 子項中文對照
    breakdown_labels = {
        "short_term": {
            "trend_structure": ("趨勢結構", 20),
            "momentum": ("動能強度", 20),
            "volume": ("成交量結構", 20),
            "institutional": ("法人籌碼", 15),
            "chip": ("籌碼健康", 15),
            "risk": ("波動風險", 10),
        },
        "swing": {
            "revenue_momentum": ("營收動能", 25),
            "mid_trend": ("中期趨勢", 20),
            "institutional_trend": ("籌碼趨勢", 20),
            "earnings_growth": ("獲利成長", 15),
            "valuation": ("估值位置", 10),
            "catalyst": ("催化因子", 10),
        },
        "value": {
            "valuation_safety": ("估值安全", 25),
            "profit_quality": ("獲利品質", 20),
            "growth_ability": ("成長能力", 20),
            "financial_safety": ("財務安全", 15),
            "cash_flow_quality": ("現金流品質", 10),
            "shareholder_return": ("股東報酬", 10),
        },
        "dividend": {
            "dividend_record": ("配息紀錄", 25),
            "dividend_quality": ("配息品質", 20),
            "cash_flow": ("現金流", 20),
            "financial_safety": ("財務安全", 15),
            "profit_stability": ("獲利穩定", 10),
            "long_term_growth": ("長期成長", 10),
        },
    }
    
    print(f"\n{'='*70}")
    print(f"{icon} {style_cn} 評分明細 — 總分: {total}/100")
    print(f"{'='*70}")
    
    labels = breakdown_labels.get(style_key, {})
    for sub_key, sub_val in breakdown.items():
        info = labels.get(sub_key)
        if info:
            cn_name, weight = info
            pct = sub_val / 100.0
            if sub_val >= 80:
                emoji = "🟢"
            elif sub_val >= 60:
                emoji = "🟡"
            elif sub_val >= 30:
                emoji = "🟠"
            else:
                emoji = "🔴"
            
            weighted = sub_val * weight / 100
            print(f"\n{emoji} {cn_name}（權重 {weight}%）")
            print(f"   子項分數: {sub_val}/100 → 加權貢獻: {weighted:.1f} 分")
            
            # 顯示原始數據和評分細項
            sub_details = details.get(sub_key, {})
            if sub_details:
                raw_items = []
                score_items = []
                for dk, dv in sub_details.items():
                    if dv is not None and not (isinstance(dv, float) and pd.isna(dv)):
                        dk_cn = cn(dk)
                        if isinstance(dv, float):
                            text = f"{dk_cn}: {dv:.4f}"
                        else:
                            text = f"{dk_cn}: {dv}"
                        if "_score" in dk:
                            score_items.append(text)
                        else:
                            raw_items.append(text)
                
                if raw_items:
                    print(f"   📊 原始數據:")
                    for item in raw_items:
                        print(f"      {item}")
                if score_items:
                    print(f"   📋 評分結果:")
                    for item in score_items:
                        print(f"      {item}")
        else:
            print(f"\n  ⚪ {sub_key}: {sub_val}/100")
    
    # 調整因子
    if modifiers:
        print(f"\n   ⚙️ 調整因子:")
        for mod_key, mod_val in modifiers.items():
            if isinstance(mod_val, dict):
                for mk, mv in mod_val.items():
                    print(f"      {mod_key}_{mk}: {mv}")
            else:
                print(f"      {mod_key}: {mod_val}")


def main():
    parser = argparse.ArgumentParser(description="從 CSV 匯出檔執行評分引擎")
    parser.add_argument("--file", default="",
                        help="CSV 檔案路徑（預設: 自動找 g:/test/ 最新的 CSV）")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="顯示更詳細的資訊")
    args = parser.parse_args()
    
    # 決定檔案路徑
    filepath = args.file
    if not filepath:
        # 自動找 g:/test/ 最新的 CSV
        test_dir = "g:/test"
        if os.path.exists(test_dir):
            csv_files = [f for f in os.listdir(test_dir) if f.endswith(".csv")]
            if csv_files:
                csv_files.sort(reverse=True)
                filepath = os.path.join(test_dir, csv_files[0])
                print(f"📂 自動選取最新 CSV: {filepath}")
    
    if not filepath:
        print("❌ 請指定 CSV 檔案路徑（--file）")
        print("   例如: python test_debug_from_csv.py --file \"g:/test/2026-07-12T01-52_export.csv\"")
        sys.exit(1)
    
    # 讀取 CSV
    print(f"📥 讀取 CSV: {filepath}")
    df = load_csv(filepath)
    
    # 轉換數值型態（處理布林字串、百分比等）
    for col in df.columns:
        # 先嘗試轉數值
        numeric_col = pd.to_numeric(df[col], errors="coerce")
        # 如果大部分都能轉成數值，就採用數值版本
        if numeric_col.notna().sum() > len(df) * 0.5:
            df[col] = numeric_col
        else:
            # 處理特殊字串
            str_val = str(df[col].iloc[0]).strip().lower()
            if str_val in ["true", "false"]:
                df[col] = 1 if str_val == "true" else 0
    
    print(f"✅ 讀取完成: {len(df)} 行 x {len(df.columns)} 欄")
    
    # 資料完整性檢查
    check_data_completeness(df)
    
    # 執行評分
    print(f"\n{'='*70}")
    print("🎯 執行評分引擎...")
    print(f"{'='*70}")
    
    scores = get_all_scores(df)
    advice = get_advice(scores)
    
    # 輸出基本建議
    advice_text = advice.get("advice", "持有")
    best_style = advice.get("best_style", "")
    best_score = advice.get("best_score", 0)
    style_names = {"short_term": "短線", "swing": "波段", "value": "價值", "dividend": "定存"}
    best_style_name = style_names.get(best_style, best_style)
    
    print(f"\n💡 基本建議: {advice_text}")
    print(f"   最佳風格: {best_style_name}（{best_score}/100）")
    
    # 四風格總分一覽
    print(f"\n{'='*70}")
    print("📊 四風格總分一覽")
    print(f"{'='*70}")
    
    style_labels = [
        ("short_term", "短線", "🔴"),
        ("swing", "波段", "🟠"),
        ("value", "價值", "🔵"),
        ("dividend", "定存", "🟢"),
    ]
    
    for key, label, icon in style_labels:
        total = scores.get(key, {}).get("total", 0)
        if total >= 70:
            mark = "⬆️ 佳"
        elif total >= 50:
            mark = "➡️ 普通"
        else:
            mark = "⬇️ 待加強"
        print(f"  {icon} {label}: {total}/100 {mark}")
    
    # 各風格詳細評分明細
    for key, label, icon in style_labels:
        print_score_detail(key, label, icon, scores, args.verbose)
    
    # 輸出摘要
    print(f"\n{'='*70}")
    print("✅ 評分完成！")
    print(f"{'='*70}")
    print(f"\n📝 摘要:")
    print(f"  檔案: {filepath}")
    print(f"  建議: {advice_text}")
    print(f"  最佳風格: {best_style_name}（{best_score}/100）")
    print(f"\n💡 提示: 修改 scoring_config.py 後，重新執行此腳本即可看到評分變化")


if __name__ == "__main__":
    main()
