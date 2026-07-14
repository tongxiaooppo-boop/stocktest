"""
bug/test_trade_vs_backtest_full.py
用回測 CSV 中的歷史分數 + trade_manager 邏輯，逐筆判斷是否有 miss

對回測 CSV 中每個時間點：
1. 根據當期分數跑 trade_manager 邏輯（未持有）
2. 記下 trade_advice 的動作
3. 與回測的 buy/sell/hold 比較
4. 計算總 miss 次數
"""
import sys, os
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

BACKTEST_CONFIGS = [
    ("2327", "backtest_2327_20260713_210743_70_50.csv", 70, 50),
    ("2327", "backtest_2327_20260713_210620_60_40.csv", 60, 40),
    ("2376", "backtest_2376_20260713_211104_70_50.csv", 70, 50),
    ("2376", "backtest_2376_20260713_211251_60_40.csv", 60, 40),
    ("2890", "backtest_2890_20260713_211527_60_40.csv", 60, 40),
    ("2890", "backtest_2890_20260713_211644_70_50.csv", 70, 50),
]


ACTION_MAP = {
    "買進": "buy", "加碼": "buy",
    "持有": "hold", "持有觀望": "hold",
    "觀望": "none", "不建議": "none",
    "賣出": "sell", "減碼": "sell",
}

STYLE_KEYS = ["short_term", "swing", "value", "dividend"]
STYLE_CN = {"short_term": "短線", "swing": "波段", "value": "價值", "dividend": "定存"}


def simulate_trade_advice(scores_dict: dict) -> dict:
    """
    模擬 generate_trade_advice 的分數優先級邏輯（不跑真正的 df）
    
    Parameters:
        scores_dict: {"short_term": 40, "swing": 57, "value": 74, "dividend": 69}
    
    Returns:
        {"action": "觀望", "style": "value"}
    """
    short_score = scores_dict.get("short_term", 0)
    swing_score = scores_dict.get("swing", 0)
    value_score = scores_dict.get("value", 0)
    dividend_score = scores_dict.get("dividend", 0)
    
    all_scores = {"swing": swing_score, "short_term": short_score, "value": value_score, "dividend": dividend_score}
    max_style = max(all_scores, key=all_scores.get)
    max_score = all_scores[max_style]
    
    style_names = {"swing": "波段", "short_term": "短線", "value": "價值", "dividend": "定存"}
    buy_threshold = 70
    
    # P1: max_score < 50
    if max_score < 50:
        return {"action": "不建議", "style": "無"}
    
    # P2: 波段 >= buy_threshold
    if swing_score >= buy_threshold:
        return {"action": "買進", "style": "波段"}
    
    # P3: 短線 >= buy_threshold
    if short_score >= buy_threshold:
        return {"action": "買進", "style": "短線"}
    
    # P4: 價值或定存 >= buy_threshold → 飛刀濾網
    if value_score >= buy_threshold or dividend_score >= buy_threshold:
        # 飛刀條件：短線 < 50 且股價破 5MA（這裡只能比分數）
        if short_score < 50:
            return {"action": "觀望", "style": "價值" if value_score >= dividend_score else "定存"}
        else:
            return {"action": "買進", "style": "價值" if value_score >= dividend_score else "定存"}
    
    # P5: 50 <= max_score < buy_threshold
    if 50 <= max_score < buy_threshold:
        return {"action": "觀望", "style": style_names.get(max_style, "無")}
    
    return {"action": "觀望", "style": "無"}


def simulate_held_advice(scores_dict: dict, current_price: float, avg_cost: float) -> dict:
    """
    模擬已持有狀態的四維度投票（簡化版，不跑完整 df）
    """
    short_score = scores_dict.get("short_term", 0)
    swing_score = scores_dict.get("swing", 0)
    value_score = scores_dict.get("value", 0)
    dividend_score = scores_dict.get("dividend", 0)
    
    votes = 0
    if short_score >= 50:
        votes += 1
    if swing_score >= 55:
        votes += 1
    if value_score >= 70:
        votes += 1
    elif value_score >= 50:
        votes += 1
    if dividend_score >= 50:
        votes += 1
    
    # 鐵盾
    is_iron_shield = False
    if (value_score > 70 or dividend_score > 70) and current_price >= (avg_cost * 0.95):
        is_iron_shield = True
    
    if votes >= 4 and swing_score > 65:
        return {"action": "加碼"}
    if votes == 3:
        return {"action": "持有"}
    if votes == 2:
        return {"action": "持有觀望"}
    if votes == 1:
        return {"action": "減碼" if not is_iron_shield else "持有觀望"}
    # votes == 0
    return {"action": "賣出" if not is_iron_shield else "持有觀望"}


def main():
    for stock_id, filename, buy_t, sell_t in BACKTEST_CONFIGS:
        filepath = os.path.join(SCRIPT_DIR, filename)
        if not os.path.exists(filepath):
            continue
        
        df = pd.read_csv(filepath, encoding="utf-8-sig")
        df["date"] = pd.to_datetime(df["date"])
        
        print(f"\n{'='*80}")
        print(f"📈 {stock_id} | {filename} | 門檻買≥{buy_t}/賣<{sell_t}")
        print(f"{'='*80}")
        
        for style in STYLE_KEYS:
            signal_col = f"{style}_signal"
            score_col = f"{style}_score"
            
            if signal_col not in df.columns:
                continue
            
            miss_buy = []    # 回測說 buy 但 trade 說不該
            miss_sell = []   # 回測說 sell 但 trade 說不該賣
            miss_hold = []   # 回測說 hold 但 trade 說該出場
            hit_buy = 0      # 兩者一致
            hit_sell = 0
            hit_hold = 0
            
            for _, row in df.iterrows():
                scores_dict = {
                    "short_term": row["short_term_score"],
                    "swing": row["swing_score"],
                    "value": row["value_score"],
                    "dividend": row["dividend_score"],
                }
                signal = row[signal_col]
                price = row.get("price", 0)
                price = 0 if pd.isna(price) else price
                
                # 未持有模擬
                ta = simulate_trade_advice(scores_dict)
                ta_action = ACTION_MAP.get(ta["action"], "none")
                
                # 已持有模擬（只有 hold 時才跑）
                if signal == "hold":
                    avg_cost = price * 0.95 if price > 0 else 0
                    held = simulate_held_advice(scores_dict, price, avg_cost)
                    held_action = ACTION_MAP.get(held["action"], "none")
                else:
                    held_action = None
                
                # buy 檢查
                if signal == "buy":
                    if ta_action in ("buy",):
                        hit_buy += 1
                    else:
                        miss_buy.append({
                            "date": row["date"].strftime("%Y-%m-%d"),
                            "price": price,
                            "score": row[score_col],
                            "trade_says": ta["action"],
                            "trade_style": ta["style"],
                        })
                
                # sell 檢查
                if signal == "sell":
                    if ta_action in ("sell",) or (held_action in ("sell", "none")):
                        hit_sell += 1
                    else:
                        miss_sell.append({
                            "date": row["date"].strftime("%Y-%m-%d"),
                            "price": price,
                            "score": row[score_col],
                            "trade_says": ta["action"],
                            "held_says": held_action if held_action else ta_action,
                        })
                
                # hold 檢查
                if signal == "hold":
                    if held_action in ("hold", "加碼"):
                        hit_hold += 1
                    elif held_action in ("sell", "減碼"):
                        miss_hold.append({
                            "date": row["date"].strftime("%Y-%m-%d"),
                            "price": price,
                            "score": row[score_col],
                            "held_says": held_action,
                        })
                    # held_action="持有觀望" 算邊緣，不計 miss
            
            cn = STYLE_CN[style]
            total_buy = hit_buy + len(miss_buy)
            total_sell = hit_sell + len(miss_sell)
            total_hold = hit_hold + len(miss_hold)
            
            print(f"\n  {cn} ({style}):")
            print(f"    buy: {hit_buy}/{total_buy} 一致" + (f" | ❌ {len(miss_buy)} miss" if miss_buy else ""))
            print(f"    sell: {hit_sell}/{total_sell} 一致" + (f" | ❌ {len(miss_sell)} miss" if miss_sell else ""))
            print(f"    hold: {hit_hold}/{total_hold} 一致" + (f" | ❌ {len(miss_hold)} miss" if miss_hold else ""))
            
            if miss_buy:
                print(f"    ❌ buy miss 範例（最多 3 筆）:")
                for m in miss_buy[:3]:
                    print(f"      {m['date']} price={m['price']:.2f} score={m['score']:.0f} → trade: {m['trade_says']}({m['trade_style']})")
            
            if miss_sell:
                print(f"    ❌ sell miss 範例:")
                for m in miss_sell[:3]:
                    print(f"      {m['date']} price={m['price']:.2f} score={m['score']:.0f} → trade: {m['trade_says']} held: {m['held_says']}")
            
            if miss_hold:
                print(f"    ❌ hold miss 範例:")
                for m in miss_hold[:3]:
                    print(f"      {m['date']} price={m['price']:.2f} score={m['score']:.0f} → held: {m['held_says']}（回測說持有但 trade 說該出貨）")


if __name__ == "__main__":
    main()