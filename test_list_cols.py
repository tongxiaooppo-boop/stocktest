"""列出母表所有欄位"""
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

base = build_universal_base_table(df_price, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss)
result = calculate_derived_columns(base)

for i, c in enumerate(result.columns):
    print(f'{i:3d}: {c}')
