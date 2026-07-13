"""
test_scorer_v4.py
測試 v4.0 評分模型
"""
import pandas as pd
import numpy as np
from core.scorer import get_all_scores, five_level_score, get_data_quality_modifier, apply_risk_modifier

# 測試 five_level_score
print('=== 測試 five_level_score ===')
print(f'正向評分 25: {five_level_score(25, {"_excellent": 20, "_good": 15, "_normal": 10, "_weak": 5})}')  # 100
print(f'正向評分 12: {five_level_score(12, {"_excellent": 20, "_good": 15, "_normal": 10, "_weak": 5})}')  # 60
print(f'正向評分 3: {five_level_score(3, {"_excellent": 20, "_good": 15, "_normal": 10, "_weak": 5})}')   # 0
print(f'反向評分 15: {five_level_score(15, {"_excellent": 20, "_good": 40, "_normal": 60, "_weak": 80}, reverse=True)}')  # 100
print(f'反向評分 50: {five_level_score(50, {"_excellent": 20, "_good": 40, "_normal": 60, "_weak": 80}, reverse=True)}')  # 60

# 測試 Data Quality Modifier
print()
print('=== 測試 Data Quality Modifier ===')
print(f'10年資料: {get_data_quality_modifier(10)}')  # 1.00
print(f'5年資料: {get_data_quality_modifier(5)}')    # 0.95
print(f'3年資料: {get_data_quality_modifier(3)}')    # 0.85
print(f'1年資料: {get_data_quality_modifier(1)}')    # 0.70

# 測試 get_all_scores 用模擬資料
print()
print('=== 測試 get_all_scores ===')
mock_data = {
    'close': 150.0, 'MA_5': 148.0, 'MA_10': 145.0, 'MA_20': 140.0, 'MA_60': 135.0,
    'volume': 5000000, 'Vol_MA_5': 3000000, 'Volume_Ratio': 1.67,
    'RSI_6': 65.0, 'MA_Alignment': 3,
    'High_5D': 152.0, 'High_10D': 155.0, 'High_20D': 158.0,
    'Inst_5D_Net': 2000000, 'Inst_20D_Net': 5000000,
    'Foreign_Net': 1000000, 'Trust_Net': 500000,
    'Margin_5D_Change': -3, 'Short_5D_Change': 2, 'SBL_5D_Change': -50000,
    'MA60_Bias': 0.02, 'ATR': 3.0,
    'Revenue_YoY': 25.0, 'Revenue_MoM': 3.0, 'Revenue_Accelerating': 2,
    'Revenue_Momentum': 1,
    'TTM_EPS': 12.0, 'TTM_EPS_Valid': True,
    'PE_Percentile': 35.0, 'PB_Percentile': 40.0,
    'ROE_TTM': 18.0, 'ROA_TTM': 8.0, 'Gross_Margin': 45.0,
    'Debt_Ratio': 35.0, 'Current_Ratio': 2.2,
    'TTM_FCF': 5000000000, 'TTM_OCF': 8000000000,
    'dividend_yield': 3.5, 'cash_dividend_total': 5.0,
    'Dividend_Continuity_Years': 8,
    'Payout_Ratio': 55.0, 'FCF_Coverage': 1.8,
    'Interest_Coverage': 8.0,
    'ROE_Stability': 4.0, 'EPS_Stability': 3.0,
    'Data_Years_Available': 8,
    'Inst_Consecutive_Days': 3,
}

df = pd.DataFrame([mock_data])
scores = get_all_scores(df)

for style, data in scores.items():
    print(f'{style}: total={data["total"]}, breakdown={data["breakdown"]}')
    if 'modifiers' in data and data['modifiers']:
        print(f'  modifiers: {data["modifiers"]}')

print()
print('=== 測試完成 ===')
