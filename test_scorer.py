"""
測試斷點 7（scorer 四風格打分）和斷點 8（advisor 規則建議）
"""
import sys
sys.path.insert(0, 'd:/AI股票程式參考/TW Stock AI/taiwan-stock-analyzer-v3')
from data.fetcher import *
from data.processor import build_universal_base_table, calculate_derived_columns
from stock.metrics import calculate_technical_indicators, calculate_financial_indicators
from core.scorer import get_all_scores
from core.advisor import get_advice, get_style_label
from datetime import datetime, timedelta

TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidG9uZ3hpYW8ub3Bwb0BnbWFpbC5jb20iLCJlbWFpbCI6InRvbmd4aWFvLm9wcG9AZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.Ie0ysfHneXOaClcxG96Gi0c0cV1AxAZzuwchBbwi0fs'
END = datetime.now().strftime('%Y-%m-%d')
START_1Y = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
START_3Y = (datetime.now() - timedelta(days=3*365)).strftime('%Y-%m-%d')

def run_full_pipeline(stock_id, label):
    """跑完整管線並回傳分數與建議"""
    print(f"\n{'='*60}")
    print(f"=== {label} ({stock_id}) ===")
    print(f"{'='*60}")
    
    # Fetch
    df_price = fetch_stock_price(stock_id, START_1Y, END, TOKEN)
    if df_price.empty:
        print(f"[SKIP] {stock_id}: 無股價資料")
        return None
    
    df_rev = fetch_month_revenue(stock_id, START_3Y, END, TOKEN)
    df_fin = fetch_financial_statements(stock_id, START_3Y, END, TOKEN)
    df_bal = fetch_balance_sheet(stock_id, START_3Y, END, TOKEN)
    df_cf = fetch_cash_flows(stock_id, START_3Y, END, TOKEN)
    df_div = fetch_dividend(stock_id, START_3Y, END, TOKEN)
    df_per = fetch_per_history(stock_id, START_1Y, END, TOKEN)
    df_inst = fetch_institutional_investors(stock_id, START_1Y, END, TOKEN)
    df_margin = fetch_margin_purchase(stock_id, START_1Y, END, TOKEN)
    df_ss = fetch_short_sale_balances(stock_id, START_1Y, END, TOKEN)
    
    # Process
    base = build_universal_base_table(df_price, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss)
    result = calculate_derived_columns(base)
    
    # Metrics
    tech = calculate_technical_indicators(result)
    fin = calculate_financial_indicators(tech)
    
    # Score
    scores = get_all_scores(fin)
    print(f"\n四維度分數:")
    for style, score in scores.items():
        print(f"  {get_style_label(style):4s}: {score:5.1f}")
    
    # Advice
    advice = get_advice(scores)
    print(f"\n基本建議: {advice['advice']}")
    print(f"最適合風格: {get_style_label(advice['best_style'])} ({advice['best_score']:.1f}分)")
    
    return scores

# 測試 2330（台積電 - 權值股）
scores_2330 = run_full_pipeline("2330", "台積電")

# 測試 2317（鴻海 - 大型股）
scores_2317 = run_full_pipeline("2317", "鴻海")

# 測試 2454（聯發科 - IC設計）
scores_2454 = run_full_pipeline("2454", "聯發科")

# 測試 0050（元大台灣50 - ETF）
scores_0050 = run_full_pipeline("0050", "元大台灣50")

print(f"\n{'='*60}")
print("=== 驗收檢查 ===")
print(f"{'='*60}")

for name, scores in [("2330台積電", scores_2330), ("2317鴻海", scores_2317), 
                      ("2454聯發科", scores_2454), ("0050台灣50", scores_0050)]:
    if scores:
        print(f"\n{name}:")
        for style, score in scores.items():
            assert 0 <= score <= 100, f"{name} {style} 分數 {score} 超出範圍!"
            print(f"  {get_style_label(style)}: {score:.1f} ✓")
        
        # 確認分數有區分度（不是全部一模一樣）
        unique_scores = set(scores.values())
        if len(unique_scores) < 2:
            print(f"  [WARN] 所有風格分數相同 ({unique_scores})，可能缺乏區分度")

print(f"\n{'='*60}")
print("=== 測試完成! ===")
print(f"{'='*60}")
