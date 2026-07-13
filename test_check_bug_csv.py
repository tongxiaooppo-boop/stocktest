# -*- coding: utf-8 -*-
"""Read bug/ CSV files, check 6 stability columns (BEFORE vs AFTER fix)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import glob
from stock.metrics import calculate_financial_indicators

bug_dir = r"D:\TW Stock AI\taiwan-stock-analyzer-v3\bug"
csv_files = glob.glob(os.path.join(bug_dir, "*_debug.csv"))

cols = ["ROE_Stability","Gross_Margin_Stability","EPS_Stability",
        "Debt_Ratio_Trend","Payout_Ratio_Stability","EPS_YoY"]

for fpath in sorted(csv_files):
    fname = os.path.basename(fpath)
    sid = fname.split("_")[0]
    
    df = pd.read_csv(fpath)
    df["date"] = pd.to_datetime(df["date"])
    latest = df.tail(1)
    
    print(f"\n{'='*60}")
    print(f"=== {sid} ({len(df)} 筆, {df['date'].min().date()} ~ {df['date'].max().date()}) ===")
    
    # 原始值
    print("\n[修正前] 原始六欄位最新值：")
    for c in cols:
        if c in df.columns:
            val = latest[c].values[0]
            print(f"  {c}: {val}")
        else:
            print(f"  {c}: (MISSING)")
    
    # 重新計算
    result = calculate_financial_indicators(df)
    latest_new = result.tail(1)
    
    print("\n[修正後] 重新計算六欄位最新值：")
    all_ok = True
    for c in cols:
        if c in result.columns:
            val = latest_new[c].values[0]
            is_zero = abs(val) < 0.0001 if pd.notna(val) else True
            status = "OK" if pd.notna(val) and not is_zero else ("ZERO" if is_zero else "NAN")
            if status != "OK":
                all_ok = False
            print(f"  {c}: {val} [{status}]")
        else:
            print(f"  {c}: (MISSING)")
    
    # 非 NaN 比例
    print(f"\n  非 NaN 比例：")
    for c in cols:
        if c in result.columns:
            notna = result[c].notna().sum()
            print(f"    {c}: {notna}/{len(result)} ({notna/len(result)*100:.1f}%)")
    
    # 股利相關欄位
    print(f"\n  股利相關：")
    for c in ["cash_dividend_total", "Payout_Ratio", "Dividend_Continuity_Years", "year_num"]:
        if c in result.columns:
            val = latest_new[c].values[0]
            print(f"    {c}: {val}")
        else:
            print(f"    {c}: (MISSING)")
    
    if all_ok:
        print(f"\n  >>> {sid}: 全部通過！六欄位不再為 0.0")
    else:
        print(f"\n  >>> {sid}: 部分欄位仍有問題")
