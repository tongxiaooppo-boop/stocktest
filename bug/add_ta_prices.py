"""
bug/add_ta_prices.py
讀取回測 CSV + debug CSV → 跑 generate_trade_advice() → 輸出 *._ta.csv

買入規則：
- 回測說 buy + ta_action = 買進/加碼 → ta_trade_price = ta_entry_high
- 回測說 buy + ta_action = 觀望/不建議 → ta_trade_price = NaN（飛刀擋住）
- 持有中 → ta_trade_price 維持上次買入價
- 賣出 → ta_trade_price = 當天收盤價

產出：backtest_XXXX_YYYYMMDD_HHMMSS_70_50_ta.csv（積極）
       backtest_XXXX_YYYYMMDD_HHMMSS_60_40_ta.csv（保守）
       
策略辨識規則（從檔名）：
  - 包含 _70_50 或 _70_50 → 積極 active
  - 包含 _60_40 → 保守 conservative
  - 無策略後綴 → 沿用原始檔名（相容舊資料）
"""
import sys, os, glob, re
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from core.scorer import get_all_scores
from core.advisor import get_advice
from core.trade_manager import generate_trade_advice

# 回測 CSV → 對應的 debug CSV 規則
def find_debug_csv(bt_filename):
    """從回測檔名找出對應的 debug CSV"""
    stock_id = bt_filename.split('_')[1]  # backtest_2327_... → 2327
    for f in os.listdir(SCRIPT_DIR):
        if f.startswith(stock_id) and f.endswith('_debug.csv'):
            return os.path.join(SCRIPT_DIR, f)
    return None

def load_debug_csv(filepath):
    """讀取 debug CSV，回傳 {date: row_dict} 的 lookup table"""
    print(f"  讀取 debug: {os.path.basename(filepath)}")
    df = pd.read_csv(filepath, encoding="utf-8-sig", low_memory=False)
    if "date" not in df.columns:
        return {}
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    for col in df.columns:
        if col != "date":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    lookup = {}
    for _, row in df.iterrows():
        lookup[row["date"]] = row
    print(f"    {len(lookup)} 筆日期資料")
    return lookup

def get_tech_row(lookup, target_date):
    """從 lookup 中找 target_date 的技術指標（相容週/月頻率）"""
    if target_date in lookup:
        return lookup[target_date]
    # 找最近的前一天
    all_dates = sorted(lookup.keys())
    for d in reversed(all_dates):
        if d <= target_date:
            return lookup[d]
    return None

def process_backtest_csv(bt_path):
    """處理單一回測 CSV"""
    filename = os.path.basename(bt_path)
    stock_id = filename.split('_')[1]
    
    print(f"\n{'='*70}")
    print(f"📊 {filename}")
    print(f"{'='*70}")
    
    # 找對應 debug CSV
    debug_path = find_debug_csv(filename)
    if not debug_path or not os.path.exists(debug_path):
        print(f"  ❌ 找不到 debug CSV for {stock_id}，跳過")
        return
    lookup = load_debug_csv(debug_path)
    if not lookup:
        print(f"  ❌ debug CSV 為空，跳過")
        return
    
    # 讀取回測 CSV
    bt_df = pd.read_csv(bt_path, encoding="utf-8-sig")
    bt_df["date"] = pd.to_datetime(bt_df["date"])
    print(f"  回測共 {len(bt_df)} 筆")
    
    # 讀取 debug CSV（完整資料，供 generate_trade_advice 使用）
    debug_full = pd.read_csv(debug_path, encoding="utf-8-sig", low_memory=False)
    if "date" in debug_full.columns:
        debug_full["date"] = pd.to_datetime(debug_full["date"], errors="coerce")
        debug_full = debug_full.dropna(subset=["date"])
    for col in debug_full.columns:
        if col != "date":
            debug_full[col] = pd.to_numeric(debug_full[col], errors="coerce")
    
    # ---- 先從回測 CSV 判斷各風格何時買/賣 ----
    # 記錄每個風格當前是否持有
    style_holding = {}
    style_entry_prices = {}
    for sk in ["short_term", "swing", "value", "dividend", "composite"]:
        style_holding[sk] = False
        style_entry_prices[sk] = None
    
    def get_any_holding():
        """是否任一風格持有中"""
        return any(style_holding.values())
    
    def get_any_entry_price():
        """取第一個有持倉風格的買入價（優先波段>價值>短線>定存）"""
        for sk in ["swing", "value", "short_term", "dividend", "composite"]:
            if style_holding[sk] and style_entry_prices[sk] is not None:
                return style_entry_prices[sk]
        return None
    
    # 逐筆處理
    ta_actions = []
    ta_entry_prices = []
    ta_entry_lows = []
    ta_entry_highs = []
    ta_agg_entries = []
    ta_cons_entries = []
    ta_trade_prices = []
    ta_knifes = []
    ta_styles = []
    ta_risks = []
    ta_reasons = []
    ta_best_signals = []
    
    current_hold_price = None  # ta_trade_price 用的持倉均價
    
    for idx, row in bt_df.iterrows():
        target_date = row["date"]
        tech = get_tech_row(lookup, target_date)
        
        # 更新各風格的持有狀態（根據回測的 buy/sell 訊號）
        for sk in ["short_term", "swing", "value", "dividend"]:
            sig_col = f"{sk}_signal"
            if sig_col in row.index:
                sig = row[sig_col]
                if sig == "buy" and not style_holding[sk]:
                    style_holding[sk] = True
                    style_entry_prices[sk] = row.get("price", None)
                elif sig == "sell" and style_holding[sk]:
                    style_holding[sk] = False
                    style_entry_prices[sk] = None
        
        # 綜合策略
        if "composite_signal" in row.index:
            csig = row["composite_signal"]
            if csig == "buy" and not style_holding["composite"]:
                style_holding["composite"] = True
                style_entry_prices["composite"] = row.get("price", None)
            elif csig == "sell" and style_holding["composite"]:
                style_holding["composite"] = False
                style_entry_prices["composite"] = None
        
        # 找出當前哪個風格在持有中（用來決定 current_shares / average_cost）
        has_any = get_any_holding()
        entry_p = get_any_entry_price()
        current_shares_val = 1000 if has_any else 0
        avg_cost_val = entry_p if entry_p is not None else 0.0
        
        if tech is None:
            ta_actions.append("N/A")
            ta_entry_prices.append(None)
            ta_entry_lows.append(None)
            ta_entry_highs.append(None)
            ta_agg_entries.append(None)
            ta_cons_entries.append(None)
            ta_trade_prices.append(None)
            ta_knifes.append(False)
            ta_styles.append("")
            ta_risks.append("")
            ta_reasons.append("無對應日期")
            ta_best_signals.append("")
            continue
        
        # 用當期分數建 score dict（取代固定的 scores_base）
        scores_here = {
            "short_term": {"total": row.get("short_term_score", 0), "breakdown": {}, "details": {}},
            "swing": {"total": row.get("swing_score", 0), "breakdown": {}, "details": {}},
            "value": {"total": row.get("value_score", 0), "breakdown": {}, "details": {}},
            "dividend": {"total": row.get("dividend_score", 0), "breakdown": {}, "details": {}},
        }
        # 切片出截至 target_date 的歷史，確保飛刀判斷使用正確的 iloc[-1]
        df_slice = debug_full[debug_full["date"] <= target_date].copy()
        if len(df_slice) < 10:
            df_slice = debug_full.tail(10).copy()
        try:
            ta = generate_trade_advice(
                stock_id=stock_id,
                df=df_slice,
                scores=scores_here,
                current_shares=current_shares_val,
                average_cost=avg_cost_val,
            )
        except Exception as e:
            ta = None
        
        if ta is None:
            action = "N/A"
            entry = None; entry_low = None; entry_high = None
            agg = None; cons = None; knife = False
            style = ""; risk = ""; reason = "trade_advice 異常"
        else:
            action = ta.action
            entry = ta.entry_price
            entry_low = ta.entry_price_low
            entry_high = ta.entry_price_high
            agg = getattr(ta, 'agg_entry', None)
            cons = getattr(ta, 'cons_entry', None)
            knife = (action == "觀望" and "飛刀" in ta.reason)
            style = ta.style; risk = ta.risk_level
            reason = ta.reason
        
        ta_actions.append(action)
        ta_entry_prices.append(entry)
        ta_entry_lows.append(entry_low)
        ta_entry_highs.append(entry_high)
        ta_agg_entries.append(agg)
        ta_cons_entries.append(cons)
        ta_knifes.append(knife)
        ta_styles.append(style)
        ta_risks.append(risk)
        ta_reasons.append(reason)
        
        # 決定 ta_trade_price
        price = row.get("price", None)
        price = None if pd.isna(price) else price
        
        if action in ("買進", "加碼"):
            if entry_high is not None:
                ta_trade_prices.append(entry_high)
                current_hold_price = entry_high
            elif price is not None:
                ta_trade_prices.append(price)
                current_hold_price = price
            else:
                ta_trade_prices.append(None)
        elif action in ("賣出", "減碼"):
            ta_trade_prices.append(price)
            current_hold_price = None
        elif action in ("持有", "持有觀望"):
            ta_trade_prices.append(current_hold_price)
        else:
            ta_trade_prices.append(None)
        
        # 記錄最佳訊號風格（方便對照）
        best_sig = ""
        for sk in ["swing", "value", "short_term", "dividend"]:
            if style_holding.get(sk, False):
                best_sig = sk
                break
        ta_best_signals.append(best_sig)
    
    # 加入新欄位
    bt_df["ta_action"] = ta_actions
    bt_df["ta_entry"] = ta_entry_prices
    bt_df["ta_entry_low"] = ta_entry_lows
    bt_df["ta_entry_high"] = ta_entry_highs
    bt_df["ta_agg_entry"] = ta_agg_entries
    bt_df["ta_cons_entry"] = ta_cons_entries
    bt_df["ta_trade_price"] = ta_trade_prices
    bt_df["ta_knife"] = ta_knifes
    bt_df["ta_style"] = ta_styles
    bt_df["ta_risk"] = ta_risks
    bt_df["ta_reason"] = ta_reasons
    
    # 輸出 CSV
    base_name = filename.replace('.csv', '_ta.csv')
    out_path = os.path.join(SCRIPT_DIR, base_name)
    bt_df.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f"  ✅ 輸出: {base_name}（{len(bt_df)} 行 x {len(bt_df.columns)} 欄）")
    
    # 簡單統計
    buy_count = sum(1 for a in ta_actions if a in ("買進", "加碼"))
    watch_count = sum(1 for a in ta_actions if a in ("觀望", "不建議"))
    hold_count = sum(1 for a in ta_actions if a in ("持有", "持有觀望"))
    sell_count = sum(1 for a in ta_actions if a in ("賣出", "減碼"))
    knife_count = sum(ta_knifes)
    traded = [p for p in ta_trade_prices if p is not None]
    avg_price = sum(traded) / len(traded) if traded else 0
    
    print(f"  統計: 買{ buy_count} 觀{watch_count} 持{hold_count} 賣{sell_count} | 飛刀{knife_count} | 均價{avg_price:.2f}")

def main():
    # 自動找 bug/ 目錄下所有回測 CSV
    bt_files = sorted(glob.glob(os.path.join(SCRIPT_DIR, "backtest_*.csv")))
    bt_files = [f for f in bt_files if not f.endswith('_ta.csv')]  # 跳過已處理的
    
    if not bt_files:
        print("❌ bug/ 目錄下沒有回測 CSV")
        return
    
    print(f"找到 {len(bt_files)} 個回測 CSV")
    for f in bt_files:
        process_backtest_csv(f)
    
    print(f"\n{'='*70}")
    print("✅ 全部完成！")


if __name__ == "__main__":
    main()