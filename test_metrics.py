"""
Test Checkpoints 5 (Technical Indicators) and 6 (Financial Indicators)
"""
import sys
sys.path.insert(0, 'd:/AI股票程式參考/TW Stock AI/taiwan-stock-analyzer-v3')
from data.fetcher import *
from data.processor import build_universal_base_table, calculate_derived_columns
from stock.metrics import calculate_technical_indicators, calculate_financial_indicators
from datetime import datetime, timedelta

TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidG9uZ3hpYW8ub3Bwb0BnbWFpbC5jb20iLCJlbWFpbCI6InRvbmd4aWFvLm9wcG9AZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.Ie0ysfHneXOaClcxG96Gi0c0cV1AxAZzuwchBbwi0fs'
STOCK = '2330'
END = datetime.now().strftime('%Y-%m-%d')
START_1Y = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
START_3Y = (datetime.now() - timedelta(days=3*365)).strftime('%Y-%m-%d')

print("=== Step 1: Fetch data ===")
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

print("=== Step 2: Build base table ===")
base = build_universal_base_table(df_price, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss)
result = calculate_derived_columns(base)
print(f"Base shape: {result.shape}")

print("\n=== Step 3: Technical indicators (Checkpoint 5) ===")
tech = calculate_technical_indicators(result)
print(f"After tech indicators: {tech.shape}")

tech_cols = [c for c in tech.columns if c not in result.columns]
print(f"New tech columns ({len(tech_cols)}): {tech_cols}")

print("\nLast 3 rows of tech indicators:")
tech_display = ['date', 'close', 'RSI_14', 'Foreign_Net', 'Foreign_5D_Sum',
                'Institutional_Net', 'Institutional_5D_Sum',
                'Margin_5D_Change', 'Short_5D_Change',
                'Bullish_MA', 'Volume_Above_MA5']
available = [c for c in tech_display if c in tech.columns]
print(tech[available].tail(3).to_string(index=False))

rsi_valid = tech['RSI_14'].dropna()
if len(rsi_valid) > 0:
    print(f"\nRSI range: {rsi_valid.min():.1f} ~ {rsi_valid.max():.1f}")
    assert rsi_valid.min() >= 0, "RSI < 0!"
    assert rsi_valid.max() <= 100, "RSI > 100!"
    print("[PASS] RSI in 0-100 range")

print("\n=== Step 4: Financial indicators (Checkpoint 6) ===")
fin = calculate_financial_indicators(tech)
print(f"After fin indicators: {fin.shape}")

fin_cols = [c for c in fin.columns if c not in tech.columns]
print(f"New fin columns ({len(fin_cols)}): {fin_cols}")

print("\nLast 3 rows of fin indicators:")
fin_display = ['date', 'close', 'ROE', 'Gross_Margin', 'Operating_Margin',
               'Debt_Ratio', 'Payout_Ratio', 'Dividend_Coverage',
               'Consecutive_Dividend_Years', 'Revenue_Accelerating']
available_fin = [c for c in fin_display if c in fin.columns]
print(fin[available_fin].tail(3).to_string(index=False))

roe_valid = fin['ROE'].dropna()
if len(roe_valid) > 0:
    print(f"\nROE range: {roe_valid.min():.1f}% ~ {roe_valid.max():.1f}%")
    if 10 < roe_valid.iloc[-1] < 50:
        print(f"[PASS] ROE ({roe_valid.iloc[-1]:.1f}%) in reasonable range")
    else:
        print(f"[WARN] ROE ({roe_valid.iloc[-1]:.1f}%) may be abnormal")

print("\n=== Test complete! ===")
