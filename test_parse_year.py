"""測試 year 欄位解析邏輯"""
import sys
sys.path.insert(0, 'd:/AI股票程式參考/TW Stock AI/taiwan-stock-analyzer-v3')
from data.fetcher import fetch_dividend
from datetime import datetime, timedelta
import pandas as pd
import re

TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidG9uZ3hpYW8ub3Bwb0BnbWFpbC5jb20iLCJlbWFpbCI6InRvbmd4aWFvLm9wcG9AZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.Ie0ysfHneXOaClcxG96Gi0c0cV1AxAZzuwchBbwi0fs'
END = datetime.now().strftime('%Y-%m-%d')
START_10Y = (datetime.now() - timedelta(days=10*365)).strftime('%Y-%m-%d')

df = fetch_dividend('2330', START_10Y, END, TOKEN)
print('=== year 欄位唯一值 ===')
print(df['year'].unique())

# 測試 _parse_year 邏輯
def _parse_year(val):
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    matches = re.findall(r'\d+', val_str)
    if not matches:
        return None
    num = int(matches[0])
    if num <= 150:
        return num + 1911  # 民國年轉西元
    else:
        return num  # 已經是西元年

print('\n=== 解析測試 ===')
for v in df['year'].unique()[:30]:
    print(f'  {v} -> {_parse_year(v)}')
