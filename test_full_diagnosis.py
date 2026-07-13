# -*- coding: utf-8 -*-
"""
完整診斷腳本：輸出所有原始 vs 計算欄位
分析四支股票的股利、穩定性、趨勢等評分用數據
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
import glob
from stock.metrics import calculate_financial_indicators

bug_dir = r"D:\TW Stock AI\taiwan-stock-analyzer-v3\bug"
csv_files = glob.glob(os.path.join(bug_dir, "*_debug.csv"))

# ===== 原始欄位（來自 FinMind API，非計算衍生） =====
RAW_FINANCIAL_FIELDS = [
    "Revenue", "GrossProfit", "OperatingIncome", "IncomeAfterTaxes",
    "EPS", "Equity", "TotalAssets", "Liabilities",
    "CashFlowsFromOperatingActivities", "PropertyAndPlantAndEquipment",
    "CurrentAssets", "CurrentLiabilities", "InterestExpense",
]

RAW_DIVIDEND_FIELDS = [
    "cash_dividend", "cash_statutory", "cash_total", "year_num",
]

RAW_PRICE_FIELDS = [
    "date", "stock_id", "open", "high", "low", "close", "volume",
]

RAW_REVENUE_FIELDS = [
    "month_revenue", "revenue_year", "revenue_month",
]

RAW_PE_FIELDS = [
    "pe_ratio", "pb_ratio", "dividend_yield",
]

# ===== 計算衍生欄位（由系統計算） =====
DERIVED_FIELDS = {
    "TTM": ["TTM_EPS", "TTM_EPS_Valid", "TTM_NetIncome", "TTM_OperatingCF", "TTM_CAPEX", "TTM_FCF", "TTM_OCF"],
    "ROE": ["ROE_TTM", "ROE_Stability"],
    "Margin": ["Gross_Margin", "Gross_Margin_Stability", "Operating_Margin", "ROA_TTM"],
    "Debt": ["Debt_Ratio", "Debt_Ratio_Trend", "Current_Ratio", "Interest_Coverage"],
    "Dividend": ["cash_dividend_total", "Payout_Ratio", "Payout_Ratio_Stability", "Dividend_Continuity_Years", "FCF_Coverage", "FCF_vs_Dividend"],
    "EPS_Growth": ["EPS_YoY", "EPS_YoY_Reason"],
    "Revenue": ["Revenue_YoY", "Revenue_MoM", "Revenue_Accelerating", "Revenue_Momentum"],
    "Technical": ["MA_5", "MA_10", "MA_20", "MA_60", "RSI_6", "MA_Alignment", "Volume_Ratio", "ATR"],
    "Institutional": ["Foreign_Net", "Trust_Net", "Dealer_Net", "Inst_Net", "Inst_5D_Net", "Inst_20D_Net"],
    "Chip": ["Chip_Divergence", "Margin_5D_Change", "Short_5D_Change", "SBL_5D_Change"],
    "Percentile": ["PE_Percentile", "PB_Percentile"],
}

for fpath in sorted(csv_files):
    fname = os.path.basename(fpath)
    sid = fname.split("_")[0]
    
    df = pd.read_csv(fpath)
    df["date"] = pd.to_datetime(df["date"])
    
    print(f"\n{'='*70}")
    print(f"=== {sid} ({len(df)} 筆, {df['date'].min().date()} ~ {df['date'].max().date()}) ===")
    print(f"{'='*70}")
    
    latest = df.tail(1)
    
    # ---- 原始資料 ----
    print("\n【原始資料 - 來自 FinMind API】")
    print(f"  股價: close={latest['close'].values[0]}, volume={latest['volume'].values[0]}")
    
    for f in RAW_FINANCIAL_FIELDS:
        if f in df.columns:
            print(f"  {f}: {latest[f].values[0]}")
    
    for f in RAW_DIVIDEND_FIELDS:
        if f in df.columns:
            print(f"  {f}: {latest[f].values[0]}")
    
    for f in RAW_REVENUE_FIELDS:
        if f in df.columns:
            print(f"  {f}: {latest[f].values[0]}")
    
    for f in RAW_PE_FIELDS:
        if f in df.columns:
            print(f"  {f}: {latest[f].values[0]}")
    
    # ---- 計算衍生欄位（修正前） ----
    print("\n【計算衍生欄位 - 修正前（原始 CSV 中的值）】")
    for category, fields in DERIVED_FIELDS.items():
        vals = []
        for f in fields:
            if f in df.columns:
                v = latest[f].values[0]
                vals.append(f"{f}={v}")
        if vals:
            print(f"  [{category}] {', '.join(vals)}")
    
    # ---- 重新計算（修正後） ----
    result = calculate_financial_indicators(df)
    latest_new = result.tail(1)
    
    print("\n【計算衍生欄位 - 修正後（季度頻率重新計算）】")
    for category, fields in DERIVED_FIELDS.items():
        vals = []
        for f in fields:
            if f in result.columns:
                v = latest_new[f].values[0]
                # 標記 NaN
                if pd.isna(v):
                    vals.append(f"{f}=NaN")
                else:
                    vals.append(f"{f}={v}")
        if vals:
            print(f"  [{category}] {', '.join(vals)}")
    
    # ---- 股利問題分析 ----
    print("\n【股利問題分析】")
    if "year_num" in df.columns:
        years = df["year_num"].dropna().unique()
        print(f"  資料中的年份: {sorted(years)}")
        print(f"  年份數量: {len(years)}")
    
    if "cash_dividend_total" in df.columns:
        print(f"  cash_dividend_total: {latest['cash_dividend_total'].values[0]}")
    
    if "TTM_EPS" in df.columns:
        print(f"  TTM_EPS: {latest['TTM_EPS'].values[0]}")
        print(f"  TTM_EPS_Valid: {latest['TTM_EPS_Valid'].values[0]}")
    
    if "Payout_Ratio" in df.columns:
        print(f"  Payout_Ratio (修正前): {latest['Payout_Ratio'].values[0]}")
    
    if "Payout_Ratio" in result.columns:
        print(f"  Payout_Ratio (修正後): {latest_new['Payout_Ratio'].values[0]}")
    
    if "Dividend_Continuity_Years" in df.columns:
        print(f"  Dividend_Continuity_Years (修正前): {latest['Dividend_Continuity_Years'].values[0]}")
    
    if "Dividend_Continuity_Years" in result.columns:
        print(f"  Dividend_Continuity_Years (修正後): {latest_new['Dividend_Continuity_Years'].values[0]}")
    
    # ---- 六個關鍵欄位總結 ----
    print("\n【六個 Stability/Trend 欄位總結】")
    key_cols = ["ROE_Stability","Gross_Margin_Stability","EPS_Stability",
                "Debt_Ratio_Trend","Payout_Ratio_Stability","EPS_YoY"]
    for c in key_cols:
        old_val = latest[c].values[0] if c in df.columns else "MISSING"
        new_val = latest_new[c].values[0] if c in result.columns else "MISSING"
        print(f"  {c}: 修正前={old_val}  修正後={new_val}")
