"""
測試腳本：測試 processor 母表對齊邏輯
使用真實 FinMind API 資料 - 逐步測試
"""
import sys
sys.path.insert(0, 'd:/AI股票程式參考/TW Stock AI/taiwan-stock-analyzer-v3')
from data.fetcher import *
from data.processor import build_universal_base_table, calculate_derived_columns, _pivot_financial_statements
from datetime import datetime, timedelta
import pandas as pd

TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidG9uZ3hpYW8ub3Bwb0BnbWFpbC5jb20iLCJlbWFpbCI6InRvbmd4aWFvLm9wcG9AZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.Ie0ysfHneXOaClcxG96Gi0c0cV1AxAZzuwchBbwi0fs'
STOCK = '2330'
END = datetime.now().strftime('%Y-%m-%d')
START_1Y = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
START_3Y = (datetime.now() - timedelta(days=3*365)).strftime('%Y-%m-%d')

print('=== 步驟 1：測試 pivot 財報長格式 ===')
df_fin = fetch_financial_statements(STOCK, START_3Y, END, TOKEN)
print(f'損益表原始: {len(df_fin)} 筆')
if not df_fin.empty:
    print(f'type 範例: {df_fin["type"].unique()[:10]}')
    df_pivot = _pivot_financial_statements(df_fin)
    print(f'pivot 後: {df_pivot.shape}')
    print(f'pivot 欄位: {list(df_pivot.columns[:10])}...')

print('\n=== 步驟 2：測試股價 + 營收對齊 ===')
df_price = fetch_stock_price(STOCK, START_1Y, END, TOKEN)
print(f'股價: {len(df_price)} 筆')
df_revenue = fetch_month_revenue(STOCK, START_3Y, END, TOKEN)
print(f'月營收: {len(df_revenue)} 筆')

base = build_universal_base_table(
    df_price=df_price,
    df_month_revenue=df_revenue,
)
print(f'母表大小: {base.shape}')
print(f'欄位: {list(base.columns)}')

print('\n=== 步驟 3：測試衍生欄位 ===')
result = calculate_derived_columns(base)
print(f'衍生後欄位: {list(result.columns)}')
print(f'最近3筆:')
print(result[['date','close','MA_5','MA_10','MA_20','MA_60','Vol_MA_5']].tail(3).to_string(index=False))

print('\n=== 步驟 4：檢查營收對齊 ===')
rev_data = result[result['month_revenue'].notna()]
if not rev_data.empty:
    print(f'有營收的日期: {rev_data["date"].dt.date.tolist()}')
    print(f'營收值: {rev_data["month_revenue"].tolist()}')

print('\n=== 步驟 5：測試完整母表（含所有資料） ===')
df_bal = fetch_balance_sheet(STOCK, START_3Y, END, TOKEN)
print(f'資產負債表: {len(df_bal)} 筆')
df_cf = fetch_cash_flows(STOCK, START_3Y, END, TOKEN)
print(f'現金流量表: {len(df_cf)} 筆')
df_div = fetch_dividend(STOCK, START_3Y, END, TOKEN)
print(f'股利: {len(df_div)} 筆')
df_per = fetch_per_history(STOCK, START_1Y, END, TOKEN)
print(f'本益比: {len(df_per)} 筆')
df_inst = fetch_institutional_investors(STOCK, START_1Y, END, TOKEN)
print(f'法人: {len(df_inst)} 筆')
df_margin = fetch_margin_purchase(STOCK, START_1Y, END, TOKEN)
print(f'融資券: {len(df_margin)} 筆')
df_ss = fetch_short_sale_balances(STOCK, START_1Y, END, TOKEN)
print(f'借券: {len(df_ss)} 筆')

base_full = build_universal_base_table(
    df_price=df_price,
    df_month_revenue=df_revenue,
    df_financial=df_fin,
    df_balance=df_bal,
    df_cash_flow=df_cf,
    df_dividend=df_div,
    df_per=df_per,
    df_institutional=df_inst,
    df_margin=df_margin,
    df_short_sale=df_ss,
)
print(f'\n完整母表: {base_full.shape}')
print(f'總欄位數: {len(base_full.columns)}')

result_full = calculate_derived_columns(base_full)
print(f'衍生後總欄位數: {len(result_full.columns)}')

# 檢查 TTM EPS
eps_cols = [c for c in result_full.columns if 'EPS' in c.upper()]
print(f'EPS 相關欄位: {eps_cols}')

# 檢查 PE Percentile
per_cols = [c for c in result_full.columns if 'Percentile' in c or 'pe_ratio' in c or 'pb_ratio' in c]
print(f'PE/PB 相關欄位: {per_cols}')

# 檢查法人
inst_cols = [c for c in result_full.columns if 'Foreign' in c or 'Investment' in c or 'Dealer' in c]
print(f'法人相關欄位: {inst_cols}')

print('\n*** 測試完成！ ***')
