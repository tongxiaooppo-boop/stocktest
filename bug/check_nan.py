import pandas as pd, os

bug_dir = r'D:\TW Stock AI\taiwan-stock-analyzer-v3\bug'
files = [f for f in os.listdir(bug_dir) if f.endswith('.csv') and f != 'test_debug_from_csv.py' and f != 'check_csv.py' and f != 'check_nan.py']

for fname in sorted(files):
    fp = os.path.join(bug_dir, fname)
    df = pd.read_csv(fp)
    stock = fname.split('_')[0]
    print(f'=== {stock} ===')
    
    # Check Debt_Ratio_Trend - look at non-NaN values
    drt = df['Debt_Ratio_Trend'].dropna()
    print(f'  Debt_Ratio_Trend non-NaN count: {len(drt)}')
    if len(drt) > 0:
        print(f'  Debt_Ratio_Trend sample: {drt.head(3).tolist()}')
    else:
        # Check if Debt_Ratio column exists and has values
        dr = df['Debt_Ratio'].dropna()
        print(f'  Debt_Ratio non-NaN count: {len(dr)}')
        print(f'  Debt_Ratio unique: {sorted(dr.unique())[:10]}')
    
    # Check EPS_YoY
    ey = df['EPS_YoY'].dropna()
    print(f'  EPS_YoY non-NaN count: {len(ey)}')
    if len(ey) > 0:
        print(f'  EPS_YoY sample: {ey.head(3).tolist()}')
    else:
        # Check TTM_EPS
        te = df['TTM_EPS'].dropna()
        print(f'  TTM_EPS non-NaN count: {len(te)}')
        print(f'  TTM_EPS unique: {sorted(te.unique())[:10]}')
    
    # Check year_num distribution
    print(f'  year_num value_counts:')
    print(f'    {df["year_num"].value_counts().to_dict()}')
    
    # Check quarter_num distribution
    if 'quarter_num' in df.columns:
        qn = df['quarter_num'].dropna()
        print(f'  quarter_num unique: {sorted(qn.unique())}')
    
    print()
