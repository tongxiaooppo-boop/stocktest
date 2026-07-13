# -*- coding: utf-8 -*-
"""
抽样检查六个 Stability/Trend 栏位的最新值
抽查 20 档不同产业、不同资料完整度的股票
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from data.fetcher import (
    fetch_stock_price, fetch_month_revenue, fetch_financial_statements,
    fetch_balance_sheet, fetch_cash_flows, fetch_dividend, fetch_per_history,
    fetch_institutional_investors, fetch_margin_purchase, fetch_short_sale_balances,
)
from data.processor import build_universal_base_table, calculate_derived_columns
from stock.metrics import calculate_technical_indicators, calculate_financial_indicators

# 20 档不同产业的股票
STOCKS = [
    # 大型权值股（资料应完整）
    "2330",  # 台积电（半导体）
    "2317",  # 鸿海（电子代工）
    "2454",  # 联发科（IC设计）
    "2412",  # 中华电（电信）
    "2308",  # 台达电（电源供应）
    # 金融股
    "2881",  # 富邦金
    "2882",  # 国泰金
    "2891",  # 中信金
    # 传产龙头
    "2002",  # 中钢（钢铁）
    "1301",  # 台塑（塑胶）
    "1326",  # 台化（塑胶）
    "1216",  # 统一（食品）
    # 中小型/高成长
    "3037",  # 欣兴（PCB）
    "2376",  # 技嘉（电脑）
    "2382",  # 广达（电脑）
    # 可能资料较少的
    "6531",  # 爱普（IC设计，2014上市）
    "1597",  # 直得（传产，2012上市）
    "8433",  # 弘帆（传产，2012上市）
    "6477",  # 安集（太阳能，2016上市）
    "6799",  # 来颉（IC设计，2021上市）
]

# 从环境变量或直接输入取得 Token
TOKEN = os.environ.get("FINMIND_TOKEN", "")
if not TOKEN:
    print("请输入 FinMind API Token:")
    TOKEN = input().strip()
    if not TOKEN:
        print("错误：未提供 Token")
        sys.exit(1)

end_str = datetime.now().strftime("%Y-%m-%d")
start_str = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
start_10y = (datetime.now() - timedelta(days=10*365)).strftime("%Y-%m-%d")

TARGET_COLS = [
    "ROE_Stability",
    "Gross_Margin_Stability",
    "EPS_Stability",
    "Debt_Ratio_Trend",
    "Payout_Ratio_Stability",
    "EPS_YoY",
]

results = []

for sid in STOCKS:
    print(f"\n=== {sid} ===")
    try:
        df_price = fetch_stock_price(sid, start_str, end_str, TOKEN)
        if df_price.empty:
            print(f"  [NO_PRICE] 无股价资料")
            results.append({"stock_id": sid, "status": "NO_PRICE"})
            continue
        
        df_rev = fetch_month_revenue(sid, start_10y, end_str, TOKEN)
        df_fin = fetch_financial_statements(sid, start_10y, end_str, TOKEN)
        df_bal = fetch_balance_sheet(sid, start_10y, end_str, TOKEN)
        df_cf = fetch_cash_flows(sid, start_10y, end_str, TOKEN)
        df_div = fetch_dividend(sid, start_10y, end_str, TOKEN)
        df_per = fetch_per_history(sid, start_str, end_str, TOKEN)
        df_inst = fetch_institutional_investors(sid, start_str, end_str, TOKEN)
        df_margin = fetch_margin_purchase(sid, start_str, end_str, TOKEN)
        df_ss = fetch_short_sale_balances(sid, start_str, end_str, TOKEN)
        
        base = build_universal_base_table(
            df_price, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss
        )
        base = calculate_derived_columns(base)
        base = calculate_technical_indicators(base)
        base = calculate_financial_indicators(base)
        
        latest = base.tail(1).iloc[0]
        
        row = {"stock_id": sid, "status": "OK"}
        for col in TARGET_COLS:
            val = latest.get(col, None)
            if pd.isna(val):
                row[col] = None
                row[f"{col}_is_zero"] = False
            else:
                row[col] = round(float(val), 4)
                row[f"{col}_is_zero"] = abs(float(val)) < 0.0001
        
        # 额外资讯
        row["data_years"] = round(latest.get("Data_Years_Available", 0), 1)
        row["ttm_eps"] = round(latest.get("TTM_EPS", 0), 2) if pd.notna(latest.get("TTM_EPS")) else None
        row["roe"] = round(latest.get("ROE_TTM", 0), 2) if pd.notna(latest.get("ROE_TTM")) else None
        row["debt_ratio"] = round(latest.get("Debt_Ratio", 0), 2) if pd.notna(latest.get("Debt_Ratio")) else None
        row["payout_ratio"] = round(latest.get("Payout_Ratio", 0), 2) if pd.notna(latest.get("Payout_Ratio")) else None
        row["gross_margin"] = round(latest.get("Gross_Margin", 0), 2) if pd.notna(latest.get("Gross_Margin")) else None
        
        results.append(row)
        
        # 印出摘要
        print(f"  Data_Years: {row['data_years']}")
        for col in TARGET_COLS:
            v = row[col]
            if v is None:
                print(f"  {col}: NaN")
            else:
                print(f"  {col}: {v}")
        print(f"  TTM_EPS={row['ttm_eps']}, ROE={row['roe']}, Debt={row['debt_ratio']}, Payout={row['payout_ratio']}, GM={row['gross_margin']}")
        
    except Exception as e:
        print(f"  [ERROR] {e}")
        results.append({"stock_id": sid, "status": f"ERROR: {str(e)[:80]}"})

# ===== 统计 =====
print("\n\n========== 统计结果 ==========")
print(f"共抽查 {len(results)} 档股票")

ok_results = [r for r in results if r.get("status") == "OK"]
print(f"成功取得资料: {len(ok_results)} 档")

for col in TARGET_COLS:
    zero_count = sum(1 for r in ok_results if r.get(f"{col}_is_zero", False))
    nan_count = sum(1 for r in ok_results if r.get(col) is None)
    valid_count = sum(1 for r in ok_results if r.get(col) is not None)
    print(f"\n{col}:")
    print(f"  为 0.0: {zero_count}/{len(ok_results)} ({zero_count/len(ok_results)*100:.0f}%)")
    print(f"  为 NaN: {nan_count}/{len(ok_results)} ({nan_count/len(ok_results)*100:.0f}%)")
    print(f"  有值:   {valid_count}/{len(ok_results)} ({valid_count/len(ok_results)*100:.0f}%)")

# 详细表格
print("\n\n========== 详细数值表 ==========")
df_result = pd.DataFrame(ok_results)
display_cols = ["stock_id", "data_years"] + TARGET_COLS + ["ttm_eps", "roe", "debt_ratio", "payout_ratio", "gross_margin"]
available_cols = [c for c in display_cols if c in df_result.columns]
df_display = df_result[available_cols]
print(df_display.to_string(index=False))
