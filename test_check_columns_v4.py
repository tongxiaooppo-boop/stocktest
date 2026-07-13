"""
test_check_columns_v4.py
盤點打分需要的欄位 vs 實際能產出的欄位（v4.0 完整版）
"""
import pandas as pd
import numpy as np

# ============================================================
# 打分需要的欄位（從 scorer.py 提取）
# ============================================================
NEEDED_COLUMNS = {
    # === 短線 ===
    "close": "收盤價",
    "MA_5": "5日均線",
    "MA_10": "10日均線",
    "MA_20": "20日均線",
    "MA_60": "60日均線",
    "MA_Alignment": "均線排列分數",
    "volume": "成交量",
    "Vol_MA_5": "5日均量",
    "Volume_Ratio": "量比",
    "RSI_6": "6日RSI",
    "High_5D": "5日高點",
    "High_10D": "10日高點",
    "High_20D": "20日高點",
    "Inst_5D_Net": "5日法人淨買超",
    "Inst_20D_Net": "20日法人淨買超",
    "Foreign_Net": "外資淨買超",
    "Trust_Net": "投信淨買超",
    "Margin_5D_Change": "5日融資變化",
    "Short_5D_Change": "5日融券變化",
    "SBL_5D_Change": "5日借券變化",
    "MA60_Bias": "60日乖離率",
    "ATR": "平均真實波幅",
    
    # === 波段 ===
    "Revenue_YoY": "營收年增率",
    "Revenue_MoM": "營收月增率",
    "Revenue_Accelerating": "營收加速次數",
    "Revenue_Momentum": "營收動能",
    "TTM_EPS": "TTM EPS",
    "TTM_EPS_Valid": "TTM EPS 有效性",
    "PE_Percentile": "PE百分位",
    "PB_Percentile": "PB百分位",
    "Inst_Consecutive_Days": "法人連續買超天數",
    
    # === 價值 ===
    "ROE_TTM": "TTM ROE",
    "ROA_TTM": "TTM ROA",
    "Gross_Margin": "毛利率",
    "Debt_Ratio": "負債比",
    "Current_Ratio": "流動比率",
    "TTM_FCF": "TTM自由現金流",
    "TTM_OCF": "TTM營業現金流",
    "dividend_yield": "殖利率",
    "cash_dividend_total": "現金股利",
    
    # === 定存 ===
    "Dividend_Continuity_Years": "連續配息年數",
    "Payout_Ratio": "配息率",
    "FCF_Coverage": "FCF覆蓋倍數",
    "Interest_Coverage": "利息保障倍數",
    "ROE_Stability": "ROE穩定性",
    "EPS_Stability": "EPS穩定性",
    
    # === 通用 ===
    "Data_Years_Available": "資料年數",
}

# ============================================================
# 現有 metrics.py 能產出的欄位（v4.0 更新後）
# ============================================================
METRICS_OUTPUT = {
    # calculate_technical_indicators
    "RSI_6", "MA_Alignment", "Volume_Ratio",
    "Foreign_Net", "Trust_Net", "Dealer_Net",
    "Inst_Net", "Inst_5D_Net", "Inst_20D_Net",
    "Chip_Divergence", "MA60_Bias",
    "Revenue_Accelerating", "Revenue_Momentum",
    "Price_Revenue_Divergence",
    "Margin_5D_Change", "Short_5D_Change",
    "SBL_5D_Change",  # 新增
    "ATR",             # 新增
    "Inst_Consecutive_Days",  # 新增
    "Above_MA_5", "Above_MA_10", "Above_MA_20", "Above_MA_60",
    "Bullish_MA", "Volume_Above_MA5",
    
    # calculate_financial_indicators
    "TTM_NetIncome", "ROE_TTM", "ROE_Stability",
    "Gross_Margin", "Gross_Margin_Stability",
    "Operating_Margin", "Debt_Ratio", "Debt_Ratio_Trend",
    "ROA_TTM",         # 新增
    "Current_Ratio",   # 新增
    "Interest_Coverage",  # 新增
    "EPS_Stability",   # 新增
    "Payout_Ratio", "Payout_Ratio_Stability",
    "FCF_Coverage", "FCF_vs_Dividend",
    "Dividend_Continuity_Years",
}

# ============================================================
# processor.py calculate_derived_columns 能產出的欄位（v4.0 更新後）
# ============================================================
PROCESSOR_OUTPUT = {
    "MA_5", "MA_10", "MA_20", "MA_60",
    "High_5D", "High_10D", "High_20D",  # 新增
    "Vol_MA_5",
    "Revenue_YoY", "Revenue_MoM",  # Revenue_MoM 新增
    "TTM_EPS", "TTM_EPS_Valid",
    "TTM_OperatingCF", "TTM_CAPEX", "TTM_FCF",
    "TTM_OCF",  # 新增 alias
    "cash_dividend_total",  # 新增
    "PE_Percentile", "PB_Percentile",
    "Data_Years_Available",
}

# ============================================================
# 原始數據源（fetcher）提供的欄位
# ============================================================
FETCHER_OUTPUT = {
    "close", "volume",  # 股價原始欄位
    "dividend_yield",   # FinMind PER 表提供
}

# ============================================================
# 盤點
# ============================================================
print("=" * 80)
print("打分欄位盤點 v4.0：需要 vs 可產出")
print("=" * 80)

all_produced = METRICS_OUTPUT | PROCESSOR_OUTPUT | FETCHER_OUTPUT

missing = []
available = []
for col, desc in sorted(NEEDED_COLUMNS.items()):
    if col in all_produced:
        available.append((col, desc))
    else:
        missing.append((col, desc))

print(f"\n✅ 可產出 ({len(available)}/{len(NEEDED_COLUMNS)}):")
for col, desc in available:
    sources = []
    if col in METRICS_OUTPUT:
        sources.append("metrics")
    if col in PROCESSOR_OUTPUT:
        sources.append("processor")
    if col in FETCHER_OUTPUT:
        sources.append("fetcher")
    print(f"  {col:35s} {desc:20s} ({'+'.join(sources)})")

print(f"\n❌ 缺少 ({len(missing)}/{len(NEEDED_COLUMNS)}):")
for col, desc in missing:
    print(f"  {col:35s} {desc}")

print(f"\n{'='*80}")
print(f"覆蓋率: {len(available)}/{len(NEEDED_COLUMNS)} = {len(available)/len(NEEDED_COLUMNS)*100:.0f}%")
print(f"{'='*80}")
