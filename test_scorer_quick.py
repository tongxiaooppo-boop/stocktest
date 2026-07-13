"""
快速測試斷點 7（scorer）和斷點 8（advisor）
只測 2330 和 2317
"""
import sys, time
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

def run_one(stock_id, label):
    t0 = time.time()
    print(f"\n{'='*50}")
    print(f"=== {label} ({stock_id}) ===")
    
    df_price = fetch_stock_price(stock_id, START_1Y, END, TOKEN)
    if df_price.empty:
        print(f"[SKIP] 無股價資料")
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
    
    base = build_universal_base_table(df_price, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss)
    result = calculate_derived_columns(base)
    tech = calculate_technical_indicators(result)
    fin = calculate_financial_indicators(tech)
    
    scores = get_all_scores(fin)
    advice = get_advice(scores)
    
    print(f"四維度分數:")
    for s, v in scores.items():
        print(f"  {get_style_label(s):4s}: {v:5.1f}")
    print(f"基本建議: {advice['advice']}")
    print(f"最適合風格: {get_style_label(advice['best_style'])} ({advice['best_score']:.1f}分)")
    print(f"耗時: {time.time()-t0:.1f}秒")
    
    # 驗收
    for s, v in scores.items():
        assert 0 <= v <= 100, f"{s} 分數 {v} 超出範圍!"
    print("[PASS] 所有分數在 0-100 範圍內")
    
    return scores

s1 = run_one("2330", "台積電")
s2 = run_one("2317", "鴻海")

if s1 and s2:
    print(f"\n{'='*50}")
    print("=== 區分度檢查 ===")
    for style in s1:
        diff = abs(s1[style] - s2[style])
        print(f"  {get_style_label(style)}: 台積電={s1[style]:.1f}, 鴻海={s2[style]:.1f}, 差距={diff:.1f}")
        if diff < 1:
            print(f"    [WARN] 兩者分數幾乎相同，可能缺乏區分度")

print(f"\n{'='*50}")
print("=== 測試完成! ===")
