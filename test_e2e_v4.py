"""
test_e2e_v4.py
端到端測試：真實資料 → 打分 → AI 解說

執行完整 pipeline（不含 Streamlit UI）：
1. 撈取真實資料（2330 台積電）
2. 建構母表 + 計算衍生欄位 + 技術/財務指標
3. 四風格打分
4. Advisor 建議
5. AI 解說（Explain Engine）
6. 輸出結果

用法：
  python test_e2e_v4.py
  python test_e2e_v4.py --stock 2317  (指定股票)
  python test_e2e_v4.py --api-key sk-xxx  (指定 DeepSeek API Key)
"""
import sys
import os
import argparse
from datetime import datetime, timedelta

# 設定 stdout 為 UTF-8（避免 cp950 無法處理 emoji）
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.fetcher import (
    fetch_stock_price, fetch_month_revenue, fetch_financial_statements,
    fetch_balance_sheet, fetch_cash_flows, fetch_dividend, fetch_per_history,
    fetch_institutional_investors, fetch_margin_purchase, fetch_short_sale_balances,
    fetch_stock_info,
)
from data.processor import build_universal_base_table, calculate_derived_columns
from stock.metrics import calculate_technical_indicators, calculate_financial_indicators
from core.scorer import get_all_scores
from core.advisor import get_advice
from ai.analyzer import analyze_with_deepseek


def main():
    parser = argparse.ArgumentParser(description="端到端測試 v4.0")
    parser.add_argument("--stock", default="2330", help="股票代號 (預設 2330)")
    parser.add_argument("--api-key", default="", help="DeepSeek API Key (選填)")
    parser.add_argument("--token", default="", help="FinMind API Token (選填)")
    args = parser.parse_args()

    stock_id = args.stock
    api_key = args.api_key
    token = args.token or os.environ.get("FINMIND_TOKEN", "")

    if not token:
        print("⚠️  未提供 FinMind Token，請用 --token 或設定 FINMIND_TOKEN 環境變數")
        print("   測試將繼續，但資料撈取可能失敗")

    end_str = datetime.now().strftime("%Y-%m-%d")
    start_str = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    start_10y = (datetime.now() - timedelta(days=10*365)).strftime("%Y-%m-%d")

    print(f"\n{'='*70}")
    print(f"📈 端到端測試 v4.0 — {stock_id}")
    print(f"{'='*70}\n")

    # ===== Step 1: 撈取資料 =====
    print("📥 Step 1: 撈取資料...")

    print("  - 股價...", end=" ")
    df_price = fetch_stock_price(stock_id, start_str, end_str, token)
    print(f"{len(df_price)} 筆")

    print("  - 營收...", end=" ")
    df_rev = fetch_month_revenue(stock_id, start_10y, end_str, token)
    print(f"{len(df_rev)} 筆")

    print("  - 財報...", end=" ")
    df_fin = fetch_financial_statements(stock_id, start_10y, end_str, token)
    print(f"{len(df_fin)} 筆")

    print("  - 資產負債表...", end=" ")
    df_bal = fetch_balance_sheet(stock_id, start_10y, end_str, token)
    print(f"{len(df_bal)} 筆")

    print("  - 現金流量表...", end=" ")
    df_cf = fetch_cash_flows(stock_id, start_10y, end_str, token)
    print(f"{len(df_cf)} 筆")

    print("  - 股利...", end=" ")
    df_div = fetch_dividend(stock_id, start_10y, end_str, token)
    print(f"{len(df_div)} 筆")

    print("  - 本益比...", end=" ")
    df_per = fetch_per_history(stock_id, start_str, end_str, token)
    print(f"{len(df_per)} 筆")

    print("  - 法人...", end=" ")
    df_inst = fetch_institutional_investors(stock_id, start_str, end_str, token)
    print(f"{len(df_inst)} 筆")

    print("  - 融資...", end=" ")
    df_margin = fetch_margin_purchase(stock_id, start_str, end_str, token)
    print(f"{len(df_margin)} 筆")

    print("  - 融券...", end=" ")
    df_ss = fetch_short_sale_balances(stock_id, start_str, end_str, token)
    print(f"{len(df_ss)} 筆")

    if df_price.empty:
        print(f"\n❌ 無法取得股票 {stock_id} 的資料")
        return

    # ===== Step 2: 建構母表 =====
    print("\n🔄 Step 2: 建構母表...")
    base = build_universal_base_table(
        df_price, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss
    )
    print(f"  - 母表: {base.shape[0]} 行 x {base.shape[1]} 欄")

    # ===== Step 3: 衍生欄位 =====
    print("\n📊 Step 3: 計算衍生欄位...")
    base = calculate_derived_columns(base)
    print(f"  - 衍生後: {base.shape[0]} 行 x {base.shape[1]} 欄")

    # ===== Step 4: 技術 + 財務指標 =====
    print("\n📈 Step 4: 計算技術指標...")
    base = calculate_technical_indicators(base)
    print(f"  - 技術指標後: {base.shape[0]} 行 x {base.shape[1]} 欄")

    print("\n📋 Step 4b: 計算財務指標...")
    base = calculate_financial_indicators(base)
    print(f"  - 最終: {base.shape[0]} 行 x {base.shape[1]} 欄")

    # ===== Step 5: 打分 =====
    print("\n🎯 Step 5: 四風格打分...")
    scores = get_all_scores(base)
    for style_key in ["short_term", "swing", "value", "dividend"]:
        s = scores.get(style_key, {})
        total = s.get("total", 0)
        breakdown = s.get("breakdown", {})
        modifiers = s.get("modifiers", {})
        print(f"  - {style_key}: {total}/100")
        for k, v in breakdown.items():
            print(f"      {k}: {v}")
        if modifiers:
            for mk, mv in modifiers.items():
                print(f"      [{mk}]: {mv}")

    # ===== Step 6: Advisor =====
    print("\n💡 Step 6: Advisor 建議...")
    advice = get_advice(scores)
    print(f"  - 建議: {advice.get('advice', 'N/A')}")
    print(f"  - 最佳風格: {advice.get('best_style', 'N/A')} ({advice.get('best_score', 0)}/100)")

    # ===== Step 7: AI 解說 =====
    print("\n🤖 Step 7: AI 解說...")
    if api_key:
        print("  - 使用 DeepSeek API...")
    else:
        print("  - 無 API Key，使用降級回應...")

    ai_result = analyze_with_deepseek(
        stock_id=stock_id,
        stock_name=stock_id,
        scores=scores,
        advice=advice,
        has_position=False,
        avg_price=0.0,
        shares=0,
        api_key=api_key,
    )

    explanation = ai_result.get("explanation", {})
    print(f"\n{'='*70}")
    print(f"📝 AI 解說結果")
    print(f"{'='*70}")
    print(f"\n📝 總結: {explanation.get('summary', 'N/A')}")

    print(f"\n✅ 加分原因 (Top3):")
    for s in explanation.get("strengths", []):
        print(f"  {s.get('rank')}. [{s.get('style')}] {s.get('item')} ({s.get('score')}分)")
        print(f"     {s.get('reason')}")

    print(f"\n❌ 扣分原因 (Top3):")
    for w in explanation.get("weaknesses", []):
        print(f"  {w.get('rank')}. [{w.get('style')}] {w.get('item')} ({w.get('score')}分)")
        print(f"     {w.get('reason')}")

    print(f"\n👥 適合族群: {explanation.get('suitable_for', 'N/A')}")
    print(f"\n⚠️ 風險提醒: {explanation.get('risk_warning', 'N/A')}")

    print(f"\n🔍 後續觀察重點:")
    for item in explanation.get("watch_items", []):
        print(f"  - {item}")

    # Evidence JSON
    evidence = ai_result.get("evidence", {})
    print(f"\n📋 Evidence JSON:")
    import json
    print(json.dumps(evidence, ensure_ascii=False, indent=2))

    print(f"\n{'='*70}")
    print(f"✅ 端到端測試完成！")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
