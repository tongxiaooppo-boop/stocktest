"""快速診斷：檢查財報欄位名稱"""
import sys
sys.path.insert(0, 'd:/AI股票程式參考/TW Stock AI/taiwan-stock-analyzer-v3')
from data.fetcher import *
from datetime import datetime, timedelta

TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidG9uZ3hpYW8ub3Bwb0BnbWFpbC5jb20iLCJlbWFpbCI6InRvbmd4aWFvLm9wcG9AZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.Ie0ysfHneXOaClcxG96Gi0c0cV1AxAZzuwchBbwi0fs'
END = datetime.now().strftime('%Y-%m-%d')
START_1Y = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
START_10Y = (datetime.now() - timedelta(days=10*365)).strftime('%Y-%m-%d')

stock_id = '2330'

# 只撈財報三表和股利
df_fin = fetch_financial_statements(stock_id, START_10Y, END, TOKEN)
df_bal = fetch_balance_sheet(stock_id, START_10Y, END, TOKEN)
df_cf = fetch_cash_flows(stock_id, START_10Y, END, TOKEN)
df_div = fetch_dividend(stock_id, START_10Y, END, TOKEN)
df_per = fetch_per_history(stock_id, START_1Y, END, TOKEN)

print('=== 資產負債表 type 唯一值 ===')
print(df_bal['type'].unique()[:30])

print('\n=== 現金流量表 type 唯一值 ===')
print(df_cf['type'].unique()[:30])

print('\n=== 股利欄位 ===')
print(list(df_div.columns))
print(df_div[['date','year','CashEarningsDistribution','AnnouncementDate']].head(10))

print('\n=== PER 欄位 ===')
print(list(df_per.columns))
print(df_per.head(3))

# 檢查 TotalAssets 和 TotalLiabilities 是否存在
print('\n=== 檢查 TotalAssets/TotalLiabilities ===')
bal_types = df_bal['type'].unique()
for t in ['TotalAssets', 'TotalLiabilities', 'TotalEquity', 'CurrentAssets', 'CurrentLiabilities']:
    print(f'  {t}: {t in bal_types}')

# 檢查 EPS
fin_types = df_fin['type'].unique()
print(f'\n=== 檢查 EPS ===')
print(f'  EPS: {"EPS" in fin_types}')
print(f'  IncomeAfterTaxes: {"IncomeAfterTaxes" in fin_types}')
print(f'  Revenue: {"Revenue" in fin_types}')
print(f'  GrossProfit: {"GrossProfit" in fin_types}')

# 檢查現金流
cf_types = df_cf['type'].unique()
print(f'\n=== 檢查現金流 ===')
for t in ['CashFlowsFromOperatingActivities', 'AcquisitionOfPPE', 'FreeCashFlow']:
    print(f'  {t}: {t in cf_types}')
