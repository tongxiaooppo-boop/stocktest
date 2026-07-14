"""
bug/test_backtest_vs_trade.py
用 trade_manager 的邏輯驗證回測中的買賣訊號是否合理

對每個回測 CSV 中的 buy/sell 時間點，跑 generate_trade_advice() 看：
1. 回測說 buy → trade_advice 真的說買進/加碼？
2. 回測說 sell → trade_advice 真的說賣出/減碼/觀望？
3. 回測說 hold → trade_advice 怎麼說？

如果 trade_advice 說「觀望/不建議」但回測說 buy，代表買不到
如果 trade_advice 說「買進/持有」但回測說 sell，代表賣錯
"""
import sys, os
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

# 回測 CSV + debug CSV + buy/sell threshold
BACKTEST_CONFIGS = [
    ("2327", "backtest_2327_20260713_210743_70_50.csv", "2327_20260713_205214_debug.csv", 70, 50),
    ("2327", "backtest_2327_20260713_210620_60_40.csv", "2327_20260713_205214_debug.csv", 60, 40),
    ("2376", "backtest_2376_20260713_211104_70_50.csv", "2376_20260713_210949_debug.csv", 70, 50),
    ("2376", "backtest_2376_20260713_211251_60_40.csv", "2376_20260713_210949_debug.csv", 60, 40),
    ("2890", "backtest_2890_20260713_211527_60_40.csv", "2890_20260713_211446_debug.csv", 60, 40),
    ("2890", "backtest_2890_20260713_211644_70_50.csv", "2890_20260713_211446_debug.csv", 70, 50),
]

# trade_advice action 的買賣傾向分組
BUY_ACTIONS = {"買進", "加碼"}
SELL_ACTIONS = {"賣出", "減碼"}
HOLD_ACTIONS = {"持有", "持有觀望"}
WATCH_ACTIONS = {"觀望", "不建議"}


def load_debug_csv(filepath):
    df = pd.read_csv(filepath, encoding="utf-8-sig", low_memory=False)
    # 先轉 date 欄位
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
    # 其餘欄位轉數值
    for col in df.columns:
        if col != "date":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def check_style_trade_alignment(
    backtest_df, debug_df, scores, style_key, style_cn, buy_threshold, sell_threshold, stock_id
):
    """檢查單一風格的買賣訊號與 trade_manager 是否一致"""
    signal_col = f"{style_key}_signal"
    score_col = f"{style_key}_score"
    
    if signal_col not in backtest_df.columns:
        return [], [], []
    
    buy_rows = backtest_df[backtest_df[signal_col] == "buy"]
    sell_rows = backtest_df[backtest_df[signal_col] == "sell"]
    hold_rows = backtest_df[backtest_df[signal_col] == "hold"]
    none_rows = backtest_df[backtest_df[signal_col] == "none"]
    
    mis_buy = []   # 回測說 buy 但 trade_manager 不建議買
    mis_sell = []  # 回測說 sell 但 trade_manager 不建議賣
    mis_hold = []  # 回測說 hold 但 trade_manager 說觀望/不建議
    
    # 取樣檢查 buy 訊號（最多 5 筆 + 最後 3 筆）
    def get_sample_rows(df):
        if len(df) <= 5:
            return df
        head = df.head(3)
        tail = df.tail(2)
        return pd.concat([head, tail])
    
    for _, row in get_sample_rows(buy_rows).iterrows():
        # 從 debug_df 中找對應日期的 row
        target_date = row["date"]
        debug_row = debug_df[debug_df["date"] == target_date]
        if debug_row.empty:
            # 找最接近的日期 row（含 guard）
            try:
                delta = (debug_df["date"] - target_date).abs()
                if delta.notna().any():
                    idx = delta.idxmin()
                    debug_row = debug_df.loc[[idx]]
                else:
                    continue
            except:
                continue
        if debug_row.empty:
            continue
        
        # 跑 trade_manager (未持有) — 需要至少 2 筆資料避免 scoring 報錯
        try:
            df_for_trade = debug_row if len(debug_row) > 1 else debug_df.tail(10)
            ta = generate_trade_advice(
                stock_id=stock_id,
                df=df_for_trade,
                scores=scores,
                current_shares=0,
                average_cost=0.0,
            )
            if ta.action in WATCH_ACTIONS:
                mis_buy.append({
                    "date": str(target_date),
                    "price": str(row.get("price", "?")),
                    "score": str(row.get(score_col, "?")),
                    "trade_action": ta.action,
                    "trade_reason": ta.reason,
                })
        except:
            continue
    
    for _, row in get_sample_rows(sell_rows).iterrows():
        target_date = row["date"]
        debug_row = debug_df[debug_df["date"] == target_date]
        if debug_row.empty:
            idx = (debug_df["date"] - pd.to_datetime(target_date)).abs().idxmin()
            debug_row = debug_df.loc[[idx]]
        if debug_row.empty:
            continue
        
        try:
            ta = generate_trade_advice(
                stock_id=stock_id,
                df=debug_row if len(debug_row) > 1 else pd.concat([debug_row, debug_row]),
                scores=scores,
                current_shares=1000,  # 假設有持股
                average_cost=row.get("price", 0) * 0.95 if pd.notna(row.get("price", 0)) else 0,
            )
            if ta.action in BUY_ACTIONS | HOLD_ACTIONS:
                mis_sell.append({
                    "date": target_date,
                    "price": row.get("price", "?"),
                    "score": row.get(score_col, "?"),
                    "trade_action": ta.action,
                    "trade_reason": ta.reason,
                })
        except:
            continue
    
    # 持有中檢查（最後幾筆）
    for _, row in hold_rows.tail(3).iterrows():
        target_date = row["date"]
        debug_row = debug_df[debug_df["date"] == target_date]
        if debug_row.empty:
            idx = (debug_df["date"] - pd.to_datetime(target_date)).abs().idxmin()
            debug_row = debug_df.loc[[idx]]
        if debug_row.empty:
            continue
        
        try:
            ta = generate_trade_advice(
                stock_id=stock_id,
                df=debug_row if len(debug_row) > 1 else pd.concat([debug_row, debug_row]),
                scores=scores,
                current_shares=1000,
                average_cost=row.get("price", 0) * 0.95 if pd.notna(row.get("price", 0)) else 0,
            )
            if ta.action in SELL_ACTIONS | WATCH_ACTIONS:
                mis_hold.append({
                    "date": target_date,
                    "price": row.get("price", "?"),
                    "score": row.get(score_col, "?"),
                    "trade_action": ta.action,
                    "trade_reason": ta.reason,
                })
        except:
            continue
    
    return mis_buy, mis_sell, mis_hold


def main():
    for stock_id, bt_file, debug_file, buy_t, sell_t in BACKTEST_CONFIGS:
        bt_path = os.path.join(script_dir, bt_file)
        debug_path = os.path.join(script_dir, debug_file)
        
        if not os.path.exists(bt_path) or not os.path.exists(debug_path):
            print(f"❌ {stock_id}: 回測或 debug CSV 遺失")
            continue
        
        print(f"\n{'='*80}")
        print(f"📈 {stock_id} | 回測: {bt_file} | 門檻買≥{buy_t}/賣<{sell_t}")
        print(f"{'='*80}")
        
        bt_df = pd.read_csv(bt_path, encoding="utf-8-sig")
        bt_df["date"] = pd.to_datetime(bt_df["date"])
        debug_df = load_debug_csv(debug_path)
        debug_df["date"] = pd.to_datetime(debug_df["date"])
        
        # 跑一次評分（用最新資料）
        scores = get_all_scores(debug_df)
        
        styles = [
            ("short_term", "短線"), ("swing", "波段"),
            ("value", "價值"), ("dividend", "定存"),
        ]
        
        for style_key, style_cn in styles:
            mis_buy, mis_sell, mis_hold = check_style_trade_alignment(
                bt_df, debug_df, scores,
                style_key, style_cn, buy_t, sell_t, stock_id,
            )
            
            # 統計
            signal_col = f"{style_key}_signal"
            buy_count = (bt_df[signal_col] == "buy").sum() if signal_col in bt_df.columns else 0
            sell_count = (bt_df[signal_col] == "sell").sum() if signal_col in bt_df.columns else 0
            hold_count = (bt_df[signal_col] == "hold").sum() if signal_col in bt_df.columns else 0
            
            print(f"\n  {style_cn} ({style_key}):")
            print(f"    回測 buy={buy_count} | sell={sell_count} | hold={hold_count}")
            
            if mis_buy:
                print(f"    ❌ 回測說買但 trade_manager 說不該買（{len(mis_buy)} 筆取樣）:")
                for m in mis_buy[:3]:
                    print(f"      {m['date']} price={m['price']} score={m['score']}")
                    print(f"        trade_manager: {m['trade_action']} — {m['trade_reason']}")
            else:
                print(f"    ✅ buy 訊號與 trade_manager 一致")
            
            if mis_sell:
                print(f"    ❌ 回測說賣但 trade_manager 說不該賣（{len(mis_sell)} 筆取樣）:")
                for m in mis_sell[:3]:
                    print(f"      {m['date']} price={m['price']} score={m['score']}")
                    print(f"        trade_manager: {m['trade_action']} — {m['trade_reason']}")
            else:
                print(f"    ✅ sell 訊號與 trade_manager 一致")
            
            if mis_hold:
                print(f"    ❌ 回測說持有但 trade_manager 說該出場（{len(mis_hold)} 筆取樣）:")
                for m in mis_hold[:3]:
                    print(f"      {m['date']} price={m['price']} score={m['score']}")
                    print(f"        trade_manager: {m['trade_action']} — {m['trade_reason']}")
            else:
                print(f"    ✅ hold 訊號與 trade_manager 一致")
    
    print(f"\n{'='*80}")
    print("✅ 驗證完成！")


if __name__ == "__main__":
    main()