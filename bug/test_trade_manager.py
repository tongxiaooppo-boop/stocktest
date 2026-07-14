"""
bug/test_trade_manager.py
使用 bug/ 目錄下的 debug CSV，模擬新的 trade_manager.py 輸出

用法：
  python bug/test_trade_manager.py
"""
import sys
import os

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from core.scorer import get_all_scores
from core.advisor import get_advice
from core.trade_manager import generate_trade_advice


STOCK_FILES = [
    ("2327", os.path.join(script_dir, "2327_20260713_205214_debug.csv")),
    ("2376", os.path.join(script_dir, "2376_20260713_210949_debug.csv")),
    ("2890", os.path.join(script_dir, "2890_20260713_211446_debug.csv")),
]


def load_debug_csv(filepath: str) -> pd.DataFrame:
    """讀取 debug CSV（格式C: 標準 DataFrame）"""
    print(f"📥 讀取: {os.path.basename(filepath)}")
    df = pd.read_csv(filepath, encoding="utf-8-sig", low_memory=False)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    print(f"   {len(df)} 行 x {len(df.columns)} 欄")
    return df


def main():
    for stock_id, filepath in STOCK_FILES:
        if not os.path.exists(filepath):
            print(f"❌ {stock_id}: 檔案不存在 {filepath}")
            continue

        print(f"\n{'='*80}")
        print(f"📈 股票 {stock_id}")
        print(f"{'='*80}")

        df = load_debug_csv(filepath)

        # 4. 🎯 評分
        scores = get_all_scores(df)
        advice = get_advice(scores)

        style_names = {"short_term": "短線", "swing": "波段", "value": "價值", "dividend": "定存"}
        print(f"\n📊 四維度分數:")
        for sk, scn in style_names.items():
            total = scores.get(sk, {}).get("total", 0)
            print(f"  {scn}: {total}/100")

        best_style = advice.get("best_style", "")
        best_score = advice.get("best_score", 0)
        best_cn = style_names.get(best_style, best_style)
        print(f"\n💡 基本建議: {advice.get('advice', 'N/A')}（最佳 {best_cn} {best_score}/100）")

        # 5. 🎯 simulate generate_trade_advice (未持有)
        close = df["close"].iloc[-1] if "close" in df.columns else None
        print(f"\n📋 最新收盤價: {close:.2f}" if close else "N/A")

        try:
            ta = generate_trade_advice(
                stock_id=stock_id,
                df=df,
                scores=scores,
                current_shares=0,
                average_cost=0.0,
            )

            print(f"\n🎯 持倉建議:")
            print(f"  動作: {ta.action}")
            print(f"  風格: {ta.style}")
            print(f"  風險: {ta.risk_level}")
            print(f"  理由: {ta.reason}")

            if ta.entry_price is not None:
                if ta.entry_price_low and ta.entry_price_high:
                    print(f"  主導價區間: {ta.entry_price_low:.2f} ~ {ta.entry_price_high:.2f} 元（核心 {ta.entry_price:.2f}）")
                else:
                    print(f"  建議價: {ta.entry_price:.2f}")

            agg = getattr(ta, 'agg_entry', None)
            cons = getattr(ta, 'cons_entry', None)
            if agg is not None:
                note = " ⚠️ 高於現價，等站回5MA" if (close is not None and agg > close) else ""
                print(f"  ⚡ 積極型: {ta.agg_entry_low:.2f}~{ta.agg_entry_high:.2f}（核心 {agg:.2f}）{note}")
            if cons is not None:
                note = " ⚠️ 高於現價" if (close is not None and cons > close) else ""
                print(f"  🛡️ 保守型: {ta.cons_entry_low:.2f}~{ta.cons_entry_high:.2f}（核心 {cons:.2f}）{note}")

            if ta.stop_loss:
                print(f"  停損: {ta.stop_loss:.2f}")

            print(f"\n📝 訊息:")
            for line in ta.message.split('\n'):
                print(f"  {line}")

        except Exception as e:
            print(f"\n❌ generate_trade_advice 錯誤: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*80}")
    print("✅ 全部完成！")


if __name__ == "__main__":
    main()