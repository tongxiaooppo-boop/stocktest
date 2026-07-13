import sys
sys.path.insert(0, 'd:/AI股票程式參考/TW Stock AI/taiwan-stock-analyzer-v3')
from data.fetcher import fetch_balance_sheet
TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidG9uZ3hpYW8ub3Bwb0BnbWFpbC5jb20iLCJlbWFpbCI6InRvbmd4aWFvLm9wcG9AZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.Ie0ysfHneXOaClcxG96Gi0c0cV1AxAZzuwchBbwi0fs'
df = fetch_balance_sheet('2330', '2024-01-01', '2024-12-31', TOKEN)
latest = df.tail(1)
print("=== 最新一筆資產負債表 ===")
for col in df.columns:
    if col not in ['date', 'stock_id']:
        val = latest[col].values[0] if len(latest) > 0 else 'N/A'
        print(f'{col}: {val}')
print(f"\n=== 所有欄位名稱 ===")
for col in df.columns:
    print(col)
