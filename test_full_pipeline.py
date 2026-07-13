"""
完整管線測試：從 fetcher → processor → metrics → scorer → advisor
測試 2330 台積電
"""
import sys
sys.path.insert(0, 'd:/AI股票程式參考/TW Stock AI/taiwan-stock-analyzer-v3')
from data.fetcher import (
    fetch_stock_price, fetch_month_revenue, fetch_financial_statements,
    fetch_balance_sheet, fetch_cash_flows, fetch_dividend, fetch_per_history,
    fetch_institutional_investors, fetch_margin_purchase, fetch_short_sale_balances
)
from data.processor import build_universal_base_table, calculate_derived_columns
from stock.metrics import calculate_technical_indicators, calculate_financial_indicators
from core.scorer import get_all_scores
from core.advisor import get_advice
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidG9uZ3hpYW8ub3Bwb0BnbWFpbC5jb20iLCJlbWFpbCI6InRvbmd4aWFvLm9wcG9AZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.Ie0ysfHneXOaClcxG96Gi0c0cV1AxAZzuwchBbwi0fs'
END = datetime.now().strftime('%Y-%m-%d')
START_1Y = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
START_10Y = (datetime.now() - timedelta(days=10*365)).strftime('%Y-%m-%d')

stock_id = '2330'
print(f"=== 測試 {stock_id} 完整管線 ===")

# Step 1: 撈取所有資料
print("\n[Step 1] 撈取資料...")
df_price = fetch_stock_price(stock_id, START_1Y, END, TOKEN)
df_rev = fetch_month_revenue(stock_id, START_10Y, END, TOKEN)
df_fin = fetch_financial_statements(stock_id, START_10Y, END, TOKEN)
df_bal = fetch_balance_sheet(stock_id, START_10Y, END, TOKEN)
df_cf = fetch_cash_flows(stock_id, START_10Y, END, TOKEN)
df_div = fetch_dividend(stock_id, START_10Y, END, TOKEN)
df_per = fetch_per_history(stock_id, START_1Y, END, TOKEN)
df_inst = fetch_institutional_investors(stock_id, START_1Y, END, TOKEN)
df_margin = fetch_margin_purchase(stock_id, START_1Y, END, TOKEN)
df_ss = fetch_short_sale_balances(stock_id, START_1Y, END, TOKEN)
print(f"  股價: {len(df_price)} 筆, 營收: {len(df_rev)} 筆, 損益: {len(df_fin)} 筆")
print(f"  資產負債: {len(df_bal)} 筆, 現金流: {len(df_cf)} 筆, 股利: {len(df_div)} 筆")
print(f"  PER: {len(df_per)} 筆, 法人: {len(df_inst)} 筆, 融資券: {len(df_margin)} 筆")

# Step 2: 建構母表
print("\n[Step 2] 建構母表...")
base = build_universal_base_table(
    df_price, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss
)
print(f"  母表大小: {base.shape}")

# Step 3: 計算衍生欄位
print("\n[Step 3] 計算衍生欄位...")
base = calculate_derived_columns(base)
print(f"  衍生後大小: {base.shape}")
print(f"  欄位: {list(base.columns)}")

# 檢查關鍵欄位
print("\n=== 關鍵欄位檢查（最新5筆） ===")
latest = base.tail(5)
for col in ['close', 'MA_5', 'MA_10', 'MA_20', 'MA_60', 'PE_Percentile', 'PB_Percentile', 'TTM_EPS', 'TTM_EPS_Valid', 'Data_Years_Available']:
    if col in latest.columns:
        val = latest[col].iloc[-1] if len(latest) > 0 else 'N/A'
        print(f"  {col}: {val}")

# Step 4: 計算技術指標
print("\n[Step 4] 計算技術指標...")
base = calculate_technical_indicators(base)
for col in ['Inst_5D_Net', 'Inst_20D_Net', 'MA60_Bias', 'Volume_Ratio', 'MA_Alignment']:
    if col in base.columns:
        val = base[col].iloc[-1] if len(base) > 0 else 'N/A'
        print(f"  {col}: {val}")

# Step 5: 計算財務指標
print("\n[Step 5] 計算財務指標...")
base = calculate_financial_indicators(base)
for col in ['ROE_TTM', 'Gross_Margin', 'Operating_Margin', 'Debt_Ratio', 'Payout_Ratio', 'Dividend_Continuity_Years']:
    if col in base.columns:
        val = base[col].iloc[-1] if len(base) > 0 else 'N/A'
        print(f"  {col}: {val}")

# Step 6: 打分
print("\n[Step 6] 四風格打分...")
scores = get_all_scores(base)
print(f"  分數: {scores}")

# Step 7: 建議
print("\n[Step 7] 基本建議...")
advice = get_advice(scores)
print(f"  建議: {advice}")

print("\n=== 測試完成 ===")
