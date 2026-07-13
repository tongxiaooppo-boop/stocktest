"""
診斷腳本：檢查母表欄位名稱，找出 Debt_Ratio=100% 和 ROE_TTM=0% 的原因
不重新撈 API，直接從已存在的資料分析
"""
import sys, time
sys.path.insert(0, 'd:/AI股票程式參考/TW Stock AI/taiwan-stock-analyzer-v3')
from data.fetcher import *
from data.processor import build_universal_base_table, calculate_derived_columns
from stock.metrics import calculate_technical_indicators, calculate_financial_indicators
from datetime import datetime, timedelta

TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidG9uZ3hpYW8ub3Bwb0BnbWFpbC5jb20iLCJlbWFpbCI6InRvbmd4aWFvLm9wcG9AZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.Ie0ysfHneXOaClcxG96Gi0c0cV1AxAZzuwchBbwi0fs'
END = datetime.now().strftime('%Y-%m-%d')
START_1Y = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
START_10Y = (datetime.now() - timedelta(days=10*365)).strftime('%Y-%m-%d')

stock_id = "2330"

print("="*60)
print("=== 診斷：檢查財報欄位名稱與資料 ===")
print("="*60)

# 撈取財報三表（10年）
print("\n【1. 損益表原始欄位】")
df_fin = fetch_financial_statements(stock_id, START_10Y, END, TOKEN)
print(f"   筆數: {len(df_fin)}")
print(f"   欄位: {list(df_fin.columns)}")
print(f"   type 唯一值: {df_fin['type'].unique()[:20]}")

print("\n【2. 資產負債表原始欄位】")
df_bal = fetch_balance_sheet(stock_id, START_10Y, END, TOKEN)
print(f"   筆數: {len(df_bal)}")
print(f"   欄位: {list(df_bal.columns)}")
print(f"   type 唯一值: {df_bal['type'].unique()[:20]}")

print("\n【3. 現金流量表原始欄位】")
df_cf = fetch_cash_flows(stock_id, START_10Y, END, TOKEN)
print(f"   筆數: {len(df_cf)}")
print(f"   欄位: {list(df_cf.columns)}")
print(f"   type 唯一值: {df_cf['type'].unique()[:20]}")

print("\n【4. 股利原始欄位】")
df_div = fetch_dividend(stock_id, START_10Y, END, TOKEN)
print(f"   筆數: {len(df_div)}")
print(f"   欄位: {list(df_div.columns)}")

print("\n【5. PER 原始欄位】")
df_per = fetch_per_history(stock_id, START_1Y, END, TOKEN)
print(f"   筆數: {len(df_per)}")
print(f"   欄位: {list(df_per.columns)}")
if not df_per.empty:
    print(f"   前3筆: {df_per.head(3).to_dict('records')}")

# 建構母表
print("\n【6. 母表建構後欄位（財報相關）】")
df_price = fetch_stock_price(stock_id, START_1Y, END, TOKEN)
df_rev = fetch_month_revenue(stock_id, START_10Y, END, TOKEN)
df_inst = fetch_institutional_investors(stock_id, START_1Y, END, TOKEN)
df_margin = fetch_margin_purchase(stock_id, START_1Y, END, TOKEN)
df_ss = fetch_short_sale_balances(stock_id, START_1Y, END, TOKEN)

base = build_universal_base_table(df_price, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss)
result = calculate_derived_columns(base)
tech = calculate_technical_indicators(result)
fin = calculate_financial_indicators(tech)

# 列出所有財報相關欄位
fin_cols = [c for c in fin.columns if any(k in c.upper() for k in 
    ['REVENUE', 'GROSS', 'PROFIT', 'INCOME', 'EARN', 'EPS', 'ASSET', 'LIAB', 'EQUITY', 
     'CASH', 'FCF', 'DEBT', 'ROE', 'DIVIDEND', 'PAYOUT', 'COVERAGE', 'MARGIN'])]
print(f"   財報相關欄位 ({len(fin_cols)} 個):")
for c in fin_cols:
    print(f"     - {c}")

# 檢查最新一筆的關鍵值
latest = fin.iloc[-1]
print(f"\n【7. 最新交易日關鍵值】")
print(f"   date: {latest.get('date', 'N/A')}")
print(f"   close: {latest.get('close', 'N/A')}")
print(f"   MA_60: {latest.get('MA_60', 'N/A')}")
print(f"   MA60_Bias: {latest.get('MA60_Bias', 'N/A')}")
print(f"   Revenue_YoY: {latest.get('Revenue_YoY', 'N/A')}")
print(f"   Revenue_Momentum: {latest.get('Revenue_Momentum', 'N/A')}")

# 檢查 EPS 相關
for col in fin.columns:
    if 'EPS' in col.upper():
        print(f"   {col}: {latest.get(col, 'N/A')}")

# 檢查 ROE 相關
for col in fin.columns:
    if 'ROE' in col.upper():
        print(f"   {col}: {latest.get(col, 'N/A')}")

# 檢查負債比相關
for col in fin.columns:
    if 'DEBT' in col.upper() or 'LIAB' in col.upper() or 'ASSET' in col.upper() or 'EQUITY' in col.upper():
        print(f"   {col}: {latest.get(col, 'N/A')}")

# 檢查股利相關
for col in fin.columns:
    if 'DIVIDEND' in col.upper() or 'PAYOUT' in col.upper() or 'CASH' in col.upper():
        print(f"   {col}: {latest.get(col, 'N/A')}")

# 檢查 PER/PBR
for col in fin.columns:
    if 'PE' in col.upper() or 'PB' in col.upper() or 'PER' in col.upper():
        print(f"   {col}: {latest.get(col, 'N/A')}")

# 檢查 Data_Years_Available
print(f"   Data_Years_Available: {latest.get('Data_Years_Available', 'N/A')}")

# 檢查 TTM_EPS_Valid
print(f"   TTM_EPS_Valid: {latest.get('TTM_EPS_Valid', 'N/A')}")

print("\n" + "="*60)
print("=== 診斷完成 ===")
print("="*60)
