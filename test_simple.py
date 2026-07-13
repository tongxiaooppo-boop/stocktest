"""簡單測試 processor 核心功能"""
import sys
sys.path.insert(0, 'd:/AI股票程式參考/TW Stock AI/taiwan-stock-analyzer-v3')
from data.fetcher import fetch_stock_price
from data.processor import build_universal_base_table, calculate_derived_columns
from datetime import datetime, timedelta

t = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidG9uZ3hpYW8ub3Bwb0BnbWFpbC5jb20iLCJlbWFpbCI6InRvbmd4aWFvLm9wcG9AZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.Ie0ysfHneXOaClcxG96Gi0c0cV1AxAZzuwchBbwi0fs'
e = datetime.now().strftime('%Y-%m-%d')
s = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')

print('Fetching price...')
df = fetch_stock_price('2330', s, e, t)
print(f'price: {len(df)} rows')

print('Building base table...')
base = build_universal_base_table(df_price=df)
print(f'base: {base.shape}')

print('Calculating derived columns...')
result = calculate_derived_columns(base)
print(f'result: {result.shape}')
print(result[['date','close','MA_5','MA_10','MA_20']].tail(3).to_string(index=False))
print('DONE')
