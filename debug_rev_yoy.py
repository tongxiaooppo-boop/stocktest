"""
debug_rev_yoy.py
測試 Revenue_YoY 計算邏輯
"""
import pandas as pd
import numpy as np

# 模擬真實情況：從母表取出的 rev_data
# 假設有 241 筆日頻資料，month_revenue 在每個月公告日後都一樣
dates = pd.date_range('2025-07-12', '2026-07-12', freq='D')
np.random.seed(42)

# 模擬月營收：每個月一個值
rev_values = {}
for d in dates:
    month_key = (d.year, d.month)
    if month_key not in rev_values:
        rev_values[month_key] = np.random.randint(50000, 80000)

# 建立 DataFrame
data = []
for d in dates:
    month_key = (d.year, d.month)
    data.append({
        'date': d,
        'month_revenue': rev_values[month_key],
        'revenue_year': d.year,
        'revenue_month': d.month,
    })

df = pd.DataFrame(data)
print(f'總筆數: {len(df)}')
print(f'唯一月份數: {df[["revenue_year", "revenue_month"]].drop_duplicates().shape[0]}')

# 測試 YoY 計算邏輯（與 processor.py 完全一致）
rev_mask = df['month_revenue'].notna() & df['revenue_year'].notna() & df['revenue_month'].notna()
rev_data = df.loc[rev_mask, ['date', 'month_revenue', 'revenue_year', 'revenue_month']].copy()
rev_data['revenue_year'] = rev_data['revenue_year'].astype(int)
rev_data['revenue_month'] = rev_data['revenue_month'].astype(int)
rev_data['last_year_key'] = (rev_data['revenue_year'] - 1).astype(str) + '_' + rev_data['revenue_month'].astype(str)
rev_data['this_year_key'] = rev_data['revenue_year'].astype(str) + '_' + rev_data['revenue_month'].astype(str)

last_year_rev = rev_data.set_index('this_year_key')['month_revenue'].to_dict()
print(f'lookup dict 大小: {len(last_year_rev)}')
print(f'範例 keys: {list(last_year_rev.keys())[:5]}')

rev_data['last_year_revenue'] = rev_data['last_year_key'].map(last_year_rev)
rev_data['Revenue_YoY'] = (rev_data['month_revenue'] - rev_data['last_year_revenue']) / rev_data['last_year_revenue']

print(f'Revenue_YoY 非空值數: {rev_data["Revenue_YoY"].notna().sum()} / {len(rev_data)}')
print(f'Revenue_YoY 前 10 筆:')
print(rev_data[['date', 'month_revenue', 'last_year_revenue', 'Revenue_YoY']].head(10))
print()

# 問題分析：因為每天都有 month_revenue，所以 last_year_key 和 this_year_key 每天都不一樣
# 但 lookup dict 只存了最後一天的 key（因為 set_index 會覆蓋重複 key）
# 所以只有最後一天的 key 能找到對應值！
print("=== 問題分析 ===")
print(f"rev_data 筆數: {len(rev_data)}")
print(f"唯一 this_year_key 數: {rev_data['this_year_key'].nunique()}")
print(f"lookup dict 大小: {len(last_year_rev)}")
print(f"lookup dict 和唯一 key 數相同: {len(last_year_rev) == rev_data['this_year_key'].nunique()}")
print()

# 解法：先取唯一月份再計算 YoY，然後 merge_asof 回母表
print("=== 解法測試 ===")
rev_unique = rev_data[['revenue_year', 'revenue_month', 'month_revenue']].drop_duplicates(subset=['revenue_year', 'revenue_month']).copy()
rev_unique['last_year_key'] = (rev_unique['revenue_year'] - 1).astype(str) + '_' + rev_unique['revenue_month'].astype(str)
rev_unique['this_year_key'] = rev_unique['revenue_year'].astype(str) + '_' + rev_unique['revenue_month'].astype(str)
last_year_rev2 = rev_unique.set_index('this_year_key')['month_revenue'].to_dict()
rev_unique['last_year_revenue'] = rev_unique['last_year_key'].map(last_year_rev2)
rev_unique['Revenue_YoY'] = (rev_unique['month_revenue'] - rev_unique['last_year_revenue']) / rev_unique['last_year_revenue']
print(f'唯一月份數: {len(rev_unique)}')
print(f'Revenue_YoY 非空值數: {rev_unique["Revenue_YoY"].notna().sum()} / {len(rev_unique)}')
print(rev_unique[['revenue_year', 'revenue_month', 'month_revenue', 'last_year_revenue', 'Revenue_YoY']].head(12))
