"""檢查 PE_Percentile 和 TTM_EPS 是否正確"""
import sys
sys.path.insert(0, 'd:/AI股票程式參考/TW Stock AI/taiwan-stock-analyzer-v3')
from data.fetcher import *
from data.processor import build_universal_base_table, calculate_derived_columns
from datetime import datetime, timedelta

TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidG9uZ3hpYW8ub3Bwb0BnbWFpbC5jb20iLCJlbWFpbCI6InRvbmd4aWFvLm9wcG9AZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.Ie0ysfHneXOaClcxG96Gi0c0cV1AxAZzuwchBbwi0fs'
STOCK = '2330'
END = datetime.now().strftime('%Y-%m-%d')
START_1Y = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
START_3Y = (datetime.now() - timedelta(days=3*365)).strftime('%Y-%m-%d')

print("Fetching data...")
df_price = fetch_stock_price(STOCK, START_1Y, END, TOKEN)
df_rev = fetch_month_revenue(STOCK, START_3Y, END, TOKEN)
df_fin = fetch_financial_statements(STOCK, START_3Y, END, TOKEN)
df_bal = fetch_balance_sheet(STOCK, START_3Y, END, TOKEN)
df_cf = fetch_cash_flows(STOCK, START_3Y, END, TOKEN)
df_div = fetch_dividend(STOCK, START_3Y, END, TOKEN)
df_per = fetch_per_history(STOCK, START_1Y, END, TOKEN)
df_inst = fetch_institutional_investors(STOCK, START_1Y, END, TOKEN)
df_margin = fetch_margin_purchase(STOCK, START_1Y, END, TOKEN)
df_ss = fetch_short_sale_balances(STOCK, START_1Y, END, TOKEN)

print("Building base table...")
base = build_universal_base_table(df_price, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss)
print(f"Base shape: {base.shape}")

print("Calculating derived columns...")
result = calculate_derived_columns(base)
print(f"Result shape: {result.shape}")

print(f"\nPE_Percentile non-null: {result['PE_Percentile'].notna().sum()}")
print(f"PB_Percentile non-null: {result['PB_Percentile'].notna().sum()}")
print(f"TTM_EPS_Valid True: {result['TTM_EPS_Valid'].sum()}")
print(f"Data_Years_Available: {result['Data_Years_Available'].iloc[0]}")

print(f"\nLast 5 rows PE/PB:")
print(result[['date','close','pe_ratio','pb_ratio','PE_Percentile','PB_Percentile','TTM_EPS','TTM_EPS_Valid']].tail(5).to_string(index=False))

print(f"\nFirst 5 rows PE/PB:")
print(result[['date','close','pe_ratio','pb_ratio','PE_Percentile','PB_Percentile','TTM_EPS','TTM_EPS_Valid']].head(5).to_string(index=False))

print("\n*** Check complete ***")
