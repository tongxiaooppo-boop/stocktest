import sys, os
sys.path.insert(0, r'D:\TW Stock AI\taiwan-stock-analyzer-v3')
from data.fetcher import fetch_financial_statements as f1, fetch_balance_sheet as f2, fetch_cash_flows as f3
from datetime import datetime, timedelta

T = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidG9uZ3hpYW8ub3Bwb0BnbWFpbC5jb20iLCJlbWFpbCI6InRvbmd4aWFvLm9wcG9AZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.Ie0ysfHneXOaClcxG96Gi0c0cV1AxAZzuwchBbwi0fs"
s = "1101"
e = datetime.now().strftime("%Y-%m-%d")
st = (datetime.now() - timedelta(days=3650)).strftime("%Y-%m-%d")

print(f"Range: {st} ~ {e}")
print("=" * 60)

for name, func in [("Income", f1), ("Balance", f2), ("CashFlow", f3)]:
    d = func(s, st, e, T)
    if d is None or d.empty:
        print(f"{name}: NO DATA")
        continue
    dates = sorted(d["date"].unique())
    print(f"{name}: {len(d)} rows, {len(dates)} unique dates")
    print(f"  Earliest: {dates[0]}, Latest: {dates[-1]}")
    print(f"  All dates: {dates}")
    if "type" in d.columns:
        print(f"  Types: {list(d['type'].unique())}")
