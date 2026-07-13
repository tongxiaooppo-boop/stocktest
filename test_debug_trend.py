# -*- coding: utf-8 -*-
"""Debug Debt_Ratio_Trend quarterly diff"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

# 模拟 8 季
dates = pd.date_range("2024-01-01", periods=480, freq="B")
debt_values = np.repeat([45.0, 44.0, 43.5, 42.0, 41.0, 40.5, 39.0, 38.0], 60)
debt_values = debt_values[:len(dates)]

df = pd.DataFrame({"date": dates, "Debt_Ratio": debt_values})

# 找出变化点
s = df["Debt_Ratio"]
is_new = pd.Series(False, index=df.index)
is_new = is_new | (s.diff().abs() > 1e-8)
if pd.notna(s.iloc[0]):
    is_new.iloc[0] = True

quarterly = df.loc[is_new, ["date", "Debt_Ratio"]].dropna(subset=["Debt_Ratio"]).copy()
print(f"季度资料点: {len(quarterly)}")
print(quarterly.head(10))

quarterly = quarterly.sort_values("date")
quarterly["_trend"] = quarterly["Debt_Ratio"].diff(4)
print(f"\n趋势值 (diff(4)):")
print(quarterly[["date", "Debt_Ratio", "_trend"]])

# merge_asof backward
result_with_date = df[["date"]].copy()
result_with_date = pd.merge_asof(
    result_with_date.sort_values("date"),
    quarterly[["date", "_trend"]].sort_values("date"),
    on="date",
    direction="backward",
)
print(f"\nmerge_asof 後非 NaN: {result_with_date['_trend'].notna().sum()}/{len(result_with_date)}")
print(f"最新值: {result_with_date['_trend'].iloc[-1]}")
