import pandas as pd, os

bug_dir = r'D:\TW Stock AI\taiwan-stock-analyzer-v3\bug'
files = [f for f in os.listdir(bug_dir) if f.endswith('.csv') and f != 'test_debug_from_csv.py' and f != 'check_csv.py']

for fname in sorted(files):
    fp = os.path.join(bug_dir, fname)
    df = pd.read_csv(fp)
    stock = fname.split('_')[0]
    print(f'=== {stock} ===')
    print(f'  rows: {len(df)}')
    print(f'  date: {df["date"].iloc[0]} ~ {df["date"].iloc[-1]}')
    years = sorted(df['year_num'].dropna().unique())
    print(f'  year_num: {years}')
    last = df.iloc[-1]
    checks = ['EPS','ROE_TTM','Gross_Margin','Debt_Ratio','TTM_EPS','ROE_Stability','Gross_Margin_Stability','EPS_Stability','Debt_Ratio_Trend','Payout_Ratio_Stability','EPS_YoY','Dividend_Continuity_Years','Payout_Ratio','cash_dividend_total']
    vals = []
    for c in checks:
        if c in df.columns:
            v = last[c]
            vals.append(f'{c}={v:.4f}' if pd.notna(v) else f'{c}=NaN')
    print('  last: ' + ' | '.join(vals))
    print()
