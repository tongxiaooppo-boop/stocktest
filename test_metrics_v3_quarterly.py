# -*- coding: utf-8 -*-
"""
测试修正後的季度频率计算逻辑
用模拟的多季资料验证六栏位不再全部为 0.0
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from stock.metrics import (
    _compute_quarterly_stability,
    _compute_quarterly_trend,
    _compute_eps_yoy_quarterly,
    calculate_financial_indicators,
)

# ===== 模拟 8 季的日频母表 =====
# 每季有 60 个交易日，共 480 天
np.random.seed(42)
dates = pd.date_range("2024-01-01", periods=480, freq="B")  # 仅交易日

# 模拟 ROE_TTM：每季变化一次（forward-fill 效果）
roe_values = np.repeat([15.0, 16.5, 14.2, 17.8, 18.1, 15.5, 19.0, 20.2], 60)
roe_values = roe_values[:len(dates)]

# 模拟 Gross_Margin
gm_values = np.repeat([50.0, 52.0, 48.5, 51.0, 53.0, 49.5, 55.0, 54.0], 60)
gm_values = gm_values[:len(dates)]

# 模拟 TTM_EPS
ttm_eps_values = np.repeat([8.0, 8.5, 7.8, 9.2, 9.5, 8.8, 10.0, 10.5], 60)
ttm_eps_values = ttm_eps_values[:len(dates)]

# 模拟 Debt_Ratio
debt_values = np.repeat([45.0, 44.0, 43.5, 42.0, 41.0, 40.5, 39.0, 38.0], 60)
debt_values = debt_values[:len(dates)]

# 模拟 Payout_Ratio
payout_values = np.repeat([60.0, 62.0, 58.0, 65.0, 63.0, 61.0, 67.0, 66.0], 60)
payout_values = payout_values[:len(dates)]

# 模拟 EPS（单季）
eps_values = np.repeat([2.0, 2.2, 1.8, 2.5, 2.3, 2.0, 2.8, 2.6], 60)
eps_values = eps_values[:len(dates)]

df = pd.DataFrame({
    "date": dates,
    "ROE_TTM": roe_values,
    "Gross_Margin": gm_values,
    "TTM_EPS": ttm_eps_values,
    "Debt_Ratio": debt_values,
    "Payout_Ratio": payout_values,
    "EPS": eps_values,
})

print(f"模拟资料：{len(df)} 笔，{len(dates)//60} 季")

# ===== 测试 _compute_quarterly_stability =====
print("\n=== 测试 _compute_quarterly_stability ===")
roe_stab = _compute_quarterly_stability(df, "ROE_Stability", "ROE_TTM", 20, 4)
print(f"ROE_Stability 非 NaN: {roe_stab.notna().sum()}/{len(df)}")
print(f"ROE_Stability 最新值: {roe_stab.iloc[-1]:.4f}")
print(f"ROE_Stability 范围: {roe_stab.min():.4f} ~ {roe_stab.max():.4f}")

gm_stab = _compute_quarterly_stability(df, "Gross_Margin_Stability", "Gross_Margin", 20, 4)
print(f"Gross_Margin_Stability 最新值: {gm_stab.iloc[-1]:.4f}")

eps_stab = _compute_quarterly_stability(df, "EPS_Stability", "TTM_EPS", 20, 4)
print(f"EPS_Stability 最新值: {eps_stab.iloc[-1]:.4f}")

payout_stab = _compute_quarterly_stability(df, "Payout_Ratio_Stability", "Payout_Ratio", 20, 4)
print(f"Payout_Ratio_Stability 最新值: {payout_stab.iloc[-1]:.4f}")

# ===== 测试 _compute_quarterly_trend (lookback=4 季 = 1年) =====
print("\n=== 测试 _compute_quarterly_trend (lookback=4) ===")
debt_trend = _compute_quarterly_trend(df, "Debt_Ratio_Trend", "Debt_Ratio", 4)
print(f"Debt_Ratio_Trend 非 NaN: {debt_trend.notna().sum()}/{len(df)}")
print(f"Debt_Ratio_Trend 最新值: {debt_trend.iloc[-1]:.4f}")
print(f"Debt_Ratio_Trend 范围: {debt_trend.min():.4f} ~ {debt_trend.max():.4f}")

# ===== 测试 _compute_eps_yoy_quarterly =====
print("\n=== 测试 _compute_eps_yoy_quarterly ===")
eps_yoy = _compute_eps_yoy_quarterly(df, "EPS")
print(f"EPS_YoY 非 NaN: {eps_yoy.notna().sum()}/{len(df)}")
print(f"EPS_YoY 最新值: {eps_yoy.iloc[-1]:.4f}")
print(f"EPS_YoY 范围: {eps_yoy.min():.4f} ~ {eps_yoy.max():.4f}")

# ===== 验证：全部不应为 0.0 =====
print("\n=== 验证：全部不应为 0.0 ===")
checks = {
    "ROE_Stability": roe_stab.iloc[-1],
    "Gross_Margin_Stability": gm_stab.iloc[-1],
    "EPS_Stability": eps_stab.iloc[-1],
    "Debt_Ratio_Trend": debt_trend.iloc[-1],
    "Payout_Ratio_Stability": payout_stab.iloc[-1],
    "EPS_YoY": eps_yoy.iloc[-1],
}
all_ok = True
for name, val in checks.items():
    is_zero = abs(val) < 0.0001 if pd.notna(val) else False
    is_nan = pd.isna(val)
    status = "OK" if not is_zero and not is_nan else "FAIL"
    if is_zero or is_nan:
        all_ok = False
    print(f"  {name}: {val:.4f} [{status}]")

if all_ok:
    print("\n全部通过！修正後的季度频率计算逻辑正确。")
else:
    print("\n有栏位仍为 0.0 或 NaN，需要进一步检查。")
