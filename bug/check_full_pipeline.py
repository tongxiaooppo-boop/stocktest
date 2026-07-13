import sys, os
sys.path.insert(0, r'D:\TW Stock AI\taiwan-stock-analyzer-v3')
sys.stdout.reconfigure(encoding='utf-8')

from data.fetcher import fetch_financial_statements, fetch_balance_sheet, fetch_cash_flows, fetch_stock_price, fetch_month_revenue, fetch_dividend, fetch_per_history, fetch_institutional_investors, fetch_margin_purchase, fetch_short_sale_balances
from data.processor import build_universal_base_table, calculate_derived_columns
from stock.metrics import calculate_financial_indicators
from datetime import datetime, timedelta

T = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidG9uZ3hpYW8ub3Bwb0BnbWFpbC5jb20iLCJlbWFpbCI6InRvbmd4aWFvLm9wcG9AZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.Ie0ysfHneXOaClcxG96Gi0c0cV1AxAZzuwchBbwi0fs"
e = datetime.now().strftime("%Y-%m-%d")
st = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
st3 = (datetime.now() - timedelta(days=3*365)).strftime("%Y-%m-%d")
st10 = (datetime.now() - timedelta(days=10*365)).strftime("%Y-%m-%d")

# 三支不同產業股票
stocks = {
    "2317": "鴻海（電子代工）",
    "2002": "中鋼（鋼鐵）",
    "1216": "統一（食品）",
}

for s, name in stocks.items():
    print(f"\n{'='*60}")
    print(f"Stock: {s} {name}")
    print(f"{'='*60}")
    print(f"Price range: {st3} ~ {e} (3年)")
    print(f"Fin range: {st10} ~ {e} (10年)")

    df_price = fetch_stock_price(s, st3, e, T)
    print(f"Price: {len(df_price)} rows")

    df_rev = fetch_month_revenue(s, st10, e, T)
    print(f"Revenue: {len(df_rev)} rows")

    df_fin = fetch_financial_statements(s, st10, e, T)
    print(f"Financial: {len(df_fin)} rows")

    df_bal = fetch_balance_sheet(s, st10, e, T)
    print(f"Balance: {len(df_bal)} rows")

    df_cf = fetch_cash_flows(s, st10, e, T)
    print(f"CashFlow: {len(df_cf)} rows")

    df_div = fetch_dividend(s, st10, e, T)
    print(f"Dividend: {len(df_div)} rows")

    df_per = fetch_per_history(s, st, e, T)
    print(f"PER: {len(df_per)} rows")

    df_inst = fetch_institutional_investors(s, st, e, T)
    print(f"Inst: {len(df_inst)} rows")

    df_margin = fetch_margin_purchase(s, st, e, T)
    print(f"Margin: {len(df_margin)} rows")

    df_ss = fetch_short_sale_balances(s, st, e, T)
    print(f"ShortSale: {len(df_ss)} rows")

    print("\nBuilding base table...")
    base = build_universal_base_table(df_price, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss)
    print(f"Base: {len(base)} rows, {base['date'].min()} ~ {base['date'].max()}")

    print("Calculating derived columns...")
    base = calculate_derived_columns(base)

    print("Calculating financial indicators...")
    base = calculate_financial_indicators(base)

    print(f"\nFinal: {len(base)} rows")

    # 檢查關鍵欄位
    checks = [
        ("Debt_Ratio_Trend", "負債比趨勢"),
        ("EPS_YoY", "EPS年成長率"),
        ("ROE_Stability", "ROE穩定度"),
        ("Gross_Margin_Stability", "毛利率穩定度"),
        ("EPS_Stability", "EPS穩定度"),
        ("Payout_Ratio_Stability", "配息率穩定度"),
    ]
    
    all_ok = True
    for col, cn_name in checks:
        if col in base.columns:
            vals = base[col].dropna()
            status = "✅" if len(vals) > 0 else "❌"
            if len(vals) == 0:
                all_ok = False
            print(f"  {status} {cn_name} ({col}): {len(vals)} non-null")
            if len(vals) > 0:
                print(f"     Sample: {vals.head(3).tolist()}")
    
    if all_ok:
        print(f"\n  ✅ {s} {name}：全部欄位都有值！")
    else:
        print(f"\n  ❌ {s} {name}：有欄位為空！")
