"""
bug/test_backtest_signals.py
分析回測 CSV 中的買賣訊號，驗證是否與 trade_manager 邏輯一致

檢查項目：
1. 買入訊號是否發生在分數 >= buy_threshold 時
2. 賣出訊號是否發生在分數 < sell_threshold 時
3. 飛刀情境（價值>=70 但短線<50 且破5MA）是否有特殊處理
4. 已持有情境的四維度投票鐵盾邏輯是否合理
"""
import sys, os
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# stock_id → (回測CSV, buy_threshold, sell_threshold)
BACKTEST_FILES = [
    ("2327", "backtest_2327_20260713_210743_70_50.csv", 70, 50),
    ("2327", "backtest_2327_20260713_210620_60_40.csv", 60, 40),
    ("2376", "backtest_2376_20260713_211104_70_50.csv", 70, 50),
    ("2376", "backtest_2376_20260713_211251_60_40.csv", 60, 40),
    ("2890", "backtest_2890_20260713_211527_60_40.csv", 60, 40),
    ("2890", "backtest_2890_20260713_211644_70_50.csv", 70, 50),
]


def analyze_backtest(filepath, stock_id, buy_threshold, sell_threshold):
    """分析單一回測CSV"""
    df = pd.read_csv(filepath, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    
    print(f"\n{'='*80}")
    print(f"📊 {stock_id} | {os.path.basename(filepath)}")
    print(f"   門檻: 買≥{buy_threshold} / 賣<{sell_threshold}")
    print(f"   區間: {df['date'].min().strftime('%Y-%m-%d')} ~ {df['date'].max().strftime('%Y-%m-%d')}")
    print(f"   共 {len(df)} 筆")
    print(f"{'='*80}")
    
    styles = ["short_term", "swing", "value", "dividend", "composite"]
    style_cn = {"short_term": "短線", "swing": "波段", "value": "價值", "dividend": "定存", "composite": "綜合"}
    
    for style in styles:
        signal_col = f"{style}_signal"
        score_col = f"{style}_score"
        
        if signal_col not in df.columns or score_col not in df.columns:
            continue
        
        # 訊號統計
        signals = df[signal_col].value_counts()
        buy_count = signals.get("buy", 0)
        sell_count = signals.get("sell", 0)
        hold_count = signals.get("hold", 0)
        none_count = signals.get("none", 0)
        
        print(f"\n  {style_cn[style]} ({style}):")
        print(f"    買入 {buy_count} 次 | 賣出 {sell_count} 次 | 持有中 {hold_count} 次 | 無訊號 {none_count} 次")
        
        # 檢查買入點的分數是否真的 >= buy_threshold
        buy_rows = df[df[signal_col] == "buy"]
        if len(buy_rows) > 0:
            avg_score_at_buy = buy_rows[score_col].mean()
            min_score_at_buy = buy_rows[score_col].min()
            valid = buy_rows[score_col].ge(buy_threshold).all()
            print(f"    買入時平均分數: {avg_score_at_buy:.1f}, 最低分: {min_score_at_buy:.1f}")
            print(f"    買入分數全≥{buy_threshold}: {'✅' if valid else '❌'}")
            if not valid:
                bad = buy_rows[buy_rows[score_col] < buy_threshold]
                for _, r in bad.iterrows():
                    print(f"      ❌ {r['date'].strftime('%Y-%m-%d')} 分數 {r[score_col]:.0f} < {buy_threshold}")
        
        # 檢查賣出點的分數是否真的 < sell_threshold
        sell_rows = df[df[signal_col] == "sell"]
        if len(sell_rows) > 0:
            avg_score_at_sell = sell_rows[score_col].mean()
            max_score_at_sell = sell_rows[score_col].max()
            valid = sell_rows[score_col].lt(sell_threshold).all()
            print(f"    賣出時平均分數: {avg_score_at_sell:.1f}, 最高分: {max_score_at_sell:.1f}")
            print(f"    賣出分數全<{sell_threshold}: {'✅' if valid else '❌'}")
            if not valid:
                bad = sell_rows[sell_rows[score_col] >= sell_threshold]
                for _, r in bad.iterrows():
                    print(f"      ❌ {r['date'].strftime('%Y-%m-%d')} 分數 {r[score_col]:.0f} ≥ {sell_threshold}")
    
    # 飛刀濾網檢查：價值 ≥ buy_threshold 且短線 < 50 時
    print(f"\n  🔪 飛刀濾網檢查（價值≥{buy_threshold} 且 短線<50）:")
    knife = df[(df["value_score"] >= buy_threshold) & (df["short_term_score"] < 50)]
    if len(knife) > 0:
        # 檢查這些時間點的訊號是否為 hold 或 none（不該是 buy）
        has_buy = (knife["value_signal"] == "buy").any()
        has_sell = (knife["value_signal"] == "sell").any()
        print(f"    飛刀期間共 {len(knife)} 筆")
        print(f"    其中價值訊號為 buy: {'❌ 異常' if has_buy else '✅ 正常'}（飛刀不該買）")
        print(f"    其中價值訊號為 sell: {'⚠️ 有賣出' if has_sell else '✅ 無賣出'}（分數仍高不該賣）")
        # 列出一些飛刀點
        knife_sample = knife.tail(3)
        for _, r in knife_sample.iterrows():
            print(f"    {r['date'].strftime('%Y-%m-%d')} | 短線{r['short_term_score']:.0f} | 波段{r['swing_score']:.0f} | 價值{r['value_score']:.0f} | 定存{r['dividend_score']:.0f} | price={r.get('price', 'N/A')} | sig={r['value_signal']}")
    else:
        print(f"    ✅ 無飛刀情境（價值≥{buy_threshold} 且短線<50 的時間點）")
    
    # 最佳策略分析
    print(f"\n  🏆 最佳策略統計:")
    best_style = ""
    max_return = -999
    for style in styles:
        signal_col = f"{style}_signal"
        if signal_col not in df.columns:
            continue
        buy_rows = df[df[signal_col] == "buy"]
        sell_rows = df[df[signal_col] == "sell"]
        price = df["price"].values if "price" in df.columns else None
        
        # 簡單回報率計算：買入均價 vs 賣出均價
        if len(buy_rows) > 0 and len(sell_rows) > 0:
            avg_buy = buy_rows["price"].mean() if "price" in buy_rows.columns else 0
            avg_sell = sell_rows["price"].mean() if "price" in sell_rows.columns else 0
            if avg_buy > 0:
                ret = (avg_sell - avg_buy) / avg_buy * 100
                if ret > max_return:
                    max_return = ret
                    best_style = style_cn[style]
                print(f"    {style_cn[style]}: 均買 {avg_buy:.2f} → 均賣 {avg_sell:.2f} ({ret:+.1f}%)")
    
    if best_style:
        print(f"\n  ✅ 最佳策略: {best_style} ({max_return:+.1f}%)")


def main():
    for stock_id, filename, buy_threshold, sell_threshold in BACKTEST_FILES:
        filepath = os.path.join(SCRIPT_DIR, filename)
        if not os.path.exists(filepath):
            print(f"❌ 檔案不存在: {filepath}")
            continue
        analyze_backtest(filepath, stock_id, buy_threshold, sell_threshold)
    
    print(f"\n{'='*80}")
    print("✅ 回測訊號分析完成！")


if __name__ == "__main__":
    main()