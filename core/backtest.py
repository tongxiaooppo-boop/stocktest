"""
core/backtest.py
回測分析模組 — 結合 walk-forward 評分與買賣訊號解析

提供：
1. run_backtest()：執行完整回測，產出五種策略（短線/波段/價值/定存/綜合）的交易記錄
2. run_dual_backtest()：同時跑積極(70/50)與保守(60/40)兩種策略，並存檔
3. 買賣訊號：基於分數 threshold 交叉，獨立於 trade_manager
4. 綜合策略：≥2 種 ≥ buy_threshold 買入，≥2 種 < sell_threshold 賣出，加權平均成本
5. 雙彈夾策略：50/50 分批建倉 + 加碼 + 全數出場
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime, date
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# 引入雙軌建議價計算
from core.trade_manager import _calc_dual_entry_prices


# ============================================================
# 資料結構
# ============================================================

@dataclass
class TradeRecord:
    """單筆交易記錄"""
    entry_date: object       # 買入日期
    entry_price: float       # 買入價格
    exit_date: object = None # 賣出日期
    exit_price: float = None # 賣出價格
    style: str = ""          # 風格
    status: str = "持有中"   # 持有中 / 已出清
    return_pct: float = 0.0  # 報酬率（已實現或未實現）
    # 雙彈夾專用
    entry_price_2: float = None  # 第二發進場價（有加碼才有）
    avg_cost: float = None       # 加權平均成本（有加碼才有）


@dataclass
class BacktestResult:
    """回測結果"""
    stock_id: str = ""
    start_date: str = ""
    end_date: str = ""
    freq: str = "W"
    buy_threshold: int = 70
    sell_threshold: int = 50
    strategy: str = ""  # "active" 或 "conservative"
    
    # 五種策略各自的交易記錄
    styles: dict = field(default_factory=lambda: {
        "short_term": {"trades": [], "total_return_pct": 0.0, "win_rate": 0.0, "trade_count": 0},
        "swing": {"trades": [], "total_return_pct": 0.0, "win_rate": 0.0, "trade_count": 0},
        "value": {"trades": [], "total_return_pct": 0.0, "win_rate": 0.0, "trade_count": 0},
        "dividend": {"trades": [], "total_return_pct": 0.0, "win_rate": 0.0, "trade_count": 0},
        "composite": {"trades": [], "total_return_pct": 0.0, "win_rate": 0.0, "trade_count": 0},
        "dual_bullet": {"trades": [], "total_return_pct": 0.0, "win_rate": 0.0, "trade_count": 0},
    })
    
    # 各風格歷史狀態（每個時間點的分數 + 訊號）
    signal_history: pd.DataFrame = field(default_factory=pd.DataFrame)


# ============================================================
# 核心回測
# ============================================================

def run_backtest(
    df: pd.DataFrame,
    stock_id: str,
    start_date: str = None,
    end_date: str = None,
    freq: str = 'W',
    buy_threshold: int = 70,
    sell_threshold: int = 50,
    strategy: str = "",
    dual_bullet: bool = False,
    dual_bullet_mode: str = "dip",
    dual_bullet_drop_pct: float = -8.0,
    use_sell_score: bool = False,
) -> BacktestResult:
    """
    執行完整回測
    
    Parameters:
        df: 母表 DataFrame
        stock_id: 股票代號
        start_date: 回測起始日
        end_date: 回測結束日
        freq: 頻率（D/W/M/Q）
        buy_threshold: 買入門檻分數（預設 70）
        sell_threshold: 賣出門檻分數（預設 50）
        strategy: 策略名稱
        dual_bullet: 是否啟用雙彈夾分批建倉
        dual_bullet_mode: 加碼模式（dip=下跌加碼, breakout=順勢突破）
        dual_bullet_drop_pct: 下跌加碼門檻（預設 -8%）
        use_sell_score: 若 True，短線/波段賣出使用獨立賣出評分（total_sell）
    
    Returns:
        BacktestResult: 完整回測結果
    """
    from core.scorer import get_historical_scores
    
    # 自動判斷策略名稱
    if not strategy:
        if buy_threshold >= 70 and sell_threshold <= 50:
            strategy = "active"
        elif buy_threshold >= 60 and sell_threshold <= 40:
            strategy = "conservative"
        else:
            strategy = f"b{buy_threshold}s{sell_threshold}"
    
    # === 1. 取得歷史分數 ===
    hist_df = get_historical_scores(
        df=df,
        start_date=start_date,
        end_date=end_date,
        freq=freq,
    )
    
    if hist_df.empty:
        return BacktestResult(
            stock_id=stock_id,
            start_date=str(start_date) if start_date else "",
            end_date=str(end_date) if end_date else "",
            freq=freq,
            buy_threshold=buy_threshold,
            sell_threshold=sell_threshold,
            strategy=strategy,
        )
    
    # 確保 date 是 datetime
    hist_df = hist_df.copy()
    if not pd.api.types.is_datetime64_any_dtype(hist_df["date"]):
        hist_df["date"] = pd.to_datetime(hist_df["date"])
    hist_df = hist_df.sort_values("date").reset_index(drop=True)
    
    # 合併價格資料（優先使用 adj_close 避免分割/減資造成的價格斷層）
    price_col = "adj_close" if "adj_close" in df.columns else "close"
    if price_col in df.columns and "date" in df.columns:
        price_df = df[["date", price_col]].copy()
        price_df = price_df.rename(columns={price_col: "close"})  # 統一命名為 close，讓 _parse_trades 等函式相容
        price_df["date"] = pd.to_datetime(price_df["date"])
        price_df = price_df.sort_values("date").drop_duplicates(subset=["date"])
        hist_df = pd.merge_asof(
            hist_df.sort_values("date"),
            price_df.sort_values("date"),
            on="date", direction="nearest",
        )
    else:
        hist_df["close"] = np.nan
    
    style_keys = ["short_term", "swing", "value", "dividend"]
    style_scores = {
        "short_term": "short_term_score",
        "swing": "swing_score",
        "value": "value_score",
        "dividend": "dividend_score",
    }
    
    result = BacktestResult(
        stock_id=stock_id,
        start_date=hist_df["date"].min().strftime("%Y-%m-%d") if len(hist_df) > 0 else "",
        end_date=hist_df["date"].max().strftime("%Y-%m-%d") if len(hist_df) > 0 else "",
        freq=freq,
        buy_threshold=buy_threshold,
        sell_threshold=sell_threshold,
        strategy=strategy,
    )
    
    # === 2. 五種策略各自解析買賣訊號 ===
    
    # 四種風格獨立策略
    for style in style_keys:
        score_col = style_scores[style]
        # 若啟用賣出評分雙軌制，短線/波段使用獨立賣出分數欄位
        sell_score_col = None
        if use_sell_score and style in ("short_term", "swing"):
            sell_score_col = f"{style}_score_sell"
        trades = _parse_trades(
            hist_df, score_col, style,
            buy_threshold, sell_threshold,
            sell_score_col=sell_score_col,
        )
        result.styles[style]["trades"] = trades
        result.styles[style]["trade_count"] = len(trades)
        result.styles[style]["total_return_pct"] = _calc_total_return(trades)
        result.styles[style]["win_rate"] = _calc_win_rate(trades)
    
    # 綜合策略（若啟用賣出評分，短線/波段賣出使用獨立賣出分數）
    composite_sell_scores = None
    if use_sell_score:
        composite_sell_scores = {
            "short_term": "short_term_score_sell",
            "swing": "swing_score_sell",
        }
    composite_trades = _parse_composite_trades(
        hist_df, style_scores,
        buy_threshold, sell_threshold,
        sell_style_scores=composite_sell_scores,
    )
    result.styles["composite"]["trades"] = composite_trades
    result.styles["composite"]["trade_count"] = len(composite_trades)
    result.styles["composite"]["total_return_pct"] = _calc_total_return(composite_trades)
    result.styles["composite"]["win_rate"] = _calc_win_rate(composite_trades)
    
    # 雙彈夾策略（如果啟用）
    if dual_bullet:
        # 用 short_term_score 作為主要訊號源
        bullet_trades = _parse_dual_bullet_trades(
            hist_df, style_scores,
            buy_threshold, sell_threshold,
            mode=dual_bullet_mode,
            drop_pct=dual_bullet_drop_pct,
        )
        result.styles["dual_bullet"]["trades"] = bullet_trades
        result.styles["dual_bullet"]["trade_count"] = len(bullet_trades)
        result.styles["dual_bullet"]["total_return_pct"] = _calc_total_return(bullet_trades)
        result.styles["dual_bullet"]["win_rate"] = _calc_win_rate(bullet_trades)
    
    # === 3. 訊號歷史（給 CSV 輸出和圖表用） ===
    tech_cols = ["MA_5", "MA_10", "MA_20", "MA_60", "pe_ratio", "PE_Percentile",
                 "pb_ratio", "PB_Percentile", "Inst_Net", "dividend_yield"]
    df_tech = df[["date"] + [c for c in tech_cols if c in df.columns]].copy() if "date" in df.columns else pd.DataFrame()
    if not df_tech.empty:
        df_tech["date"] = pd.to_datetime(df_tech["date"])
        df_tech = df_tech.sort_values("date").drop_duplicates(subset=["date"])
    
    # 對齊 high/low（用於判斷建議價區間是否可成交）
    price_cols = ["high", "low", "close"]
    df_price_ext = df[["date"] + [c for c in price_cols if c in df.columns]].copy() if "date" in df.columns else pd.DataFrame()
    if not df_price_ext.empty:
        df_price_ext["date"] = pd.to_datetime(df_price_ext["date"])
        df_price_ext = df_price_ext.sort_values("date").drop_duplicates(subset=["date"])
    
    signal_records = []
    for i, row in hist_df.iterrows():
        record = {
            "date": row["date"],
            "price": row.get("adj_close", row.get("close", np.nan)),
        }
        # 對齊技術指標
        if not df_tech.empty:
            tech_row = df_tech[df_tech["date"] == row["date"]]
            if tech_row.empty:
                idx = (df_tech["date"] - row["date"]).abs().idxmin()
                tech_row = df_tech.loc[[idx]]
            if not tech_row.empty:
                for c in tech_cols:
                    if c in tech_row.columns:
                        record[c] = tech_row[c].iloc[0]
        
        # 對齊 high/low
        day_high = np.nan
        day_low = np.nan
        if not df_price_ext.empty:
            pr_row = df_price_ext[df_price_ext["date"] == row["date"]]
            if pr_row.empty:
                idx = (df_price_ext["date"] - row["date"]).abs().idxmin()
                pr_row = df_price_ext.loc[[idx]]
            if not pr_row.empty:
                day_high = pr_row["high"].iloc[0] if "high" in pr_row.columns else np.nan
                day_low = pr_row["low"].iloc[0] if "low" in pr_row.columns else np.nan
        record["high"] = day_high
        record["low"] = day_low
        
        # 計算雙軌建議價（使用 adj_close 避免分割/減資造成的價格斷層）
        close_price = row.get("adj_close", row.get("close", np.nan))
        ma_20_val = record.get("MA_20", np.nan)
        ma_5_val = record.get("MA_5", np.nan)
        pe_pct_val = record.get("PE_Percentile", np.nan)
        
        # 取當日各風格最高分作為 best_score（對應 trade_manager 的邏輯）
        scores_today = [row.get(sc, 0) for sc in style_scores.values()]
        scores_today = [s if pd.notna(s) else 0 for s in scores_today]
        best_score_today = max(scores_today) if scores_today else 0
        
        if pd.notna(close_price) and pd.notna(ma_5_val) and best_score_today > 0:
            agg_c, agg_l, agg_h, cons_c, cons_l, cons_h = _calc_dual_entry_prices(
                close_price, pe_pct_val if pd.notna(pe_pct_val) else None,
                ma_20_val if pd.notna(ma_20_val) else None,
                ma_5_val if pd.notna(ma_5_val) else None,
                best_score_today,
            )
            record["agg_low"] = agg_l
            record["agg_high"] = agg_h
            record["cons_low"] = cons_l
            record["cons_high"] = cons_h
            
            # price_in_range：當日 low~high 範圍與積極或保守區間有交集即 True
            in_range = False
            if pd.notna(day_high) and pd.notna(day_low):
                if agg_h is not None and agg_l is not None:
                    if day_low <= agg_h and day_high >= agg_l:
                        in_range = True
                if not in_range and cons_h is not None and cons_l is not None:
                    if day_low <= cons_h and day_high >= cons_l:
                        in_range = True
            record["price_in_range"] = in_range
        else:
            record["agg_low"] = np.nan
            record["agg_high"] = np.nan
            record["cons_low"] = np.nan
            record["cons_high"] = np.nan
            record["price_in_range"] = False
        for style in style_keys:
            score_col = style_scores[style]
            record[score_col] = row.get(score_col, np.nan)
            # 產出賣出評分欄位（供分數走勢圖顯示賣出線）
            sell_col = f"{style}_score_sell"
            record[sell_col] = row.get(sell_col, np.nan)
            
            trades_for_style = result.styles[style]["trades"]
            buy_signal = False
            sell_signal = False
            for t in trades_for_style:
                if t.entry_date == row["date"]:
                    buy_signal = True
                if t.exit_date is not None and t.exit_date == row["date"]:
                    sell_signal = True
            
            if buy_signal:
                record[f"{style}_signal"] = "buy"
            elif sell_signal:
                record[f"{style}_signal"] = "sell"
            else:
                holding = False
                for t in trades_for_style:
                    if t.status == "持有中":
                        holding = True
                if holding:
                    record[f"{style}_signal"] = "hold"
                else:
                    record[f"{style}_signal"] = "none"
        
        signal_records.append(record)
    
    result.signal_history = pd.DataFrame(signal_records)
    
    return result


# ============================================================
# 雙策略回測（積極 + 保守同時跑）
# ============================================================

def run_dual_backtest(
    df: pd.DataFrame,
    stock_id: str,
    start_date: str = None,
    end_date: str = None,
    freq: str = 'W',
    output_dir: str = None,
    dual_bullet: bool = False,
    dual_bullet_mode: str = "dip",
    dual_bullet_drop_pct: float = -8.0,
) -> Tuple[BacktestResult, BacktestResult]:
    """
    同時執行積極(70/50)和保守(60/40)兩種策略的回測
    
    Parameters:
        df: 母表 DataFrame
        stock_id: 股票代號
        start_date: 回測起始日
        end_date: 回測結束日
        freq: 頻率（D/W/M/Q）
        output_dir: 輸出目錄，若指定則自動存檔
    
    Returns:
        (active_result, conservative_result): 兩種策略的回測結果
    """
    # 積極策略：買≥70 / 賣<50
    result_active = run_backtest(
        df=df, stock_id=stock_id,
        start_date=start_date, end_date=end_date,
        freq=freq,
        buy_threshold=70, sell_threshold=50,
        strategy="active",
        dual_bullet=dual_bullet,
        dual_bullet_mode=dual_bullet_mode,
        dual_bullet_drop_pct=dual_bullet_drop_pct,
    )
    
    # 保守策略：買≥60 / 賣<40
    result_conservative = run_backtest(
        df=df, stock_id=stock_id,
        start_date=start_date, end_date=end_date,
        freq=freq,
        buy_threshold=60, sell_threshold=40,
        strategy="conservative",
        dual_bullet=dual_bullet,
        dual_bullet_mode=dual_bullet_mode,
        dual_bullet_drop_pct=dual_bullet_drop_pct,
    )
    
    # 若指定輸出目錄，則自動存檔
    if output_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_dir = output_dir
        os.makedirs(save_dir, exist_ok=True)
        
        # 積極
        active_path = os.path.join(save_dir, f"backtest_{stock_id}_{timestamp}_70_50.csv")
        _save_to_csv(result_active, active_path)
        
        # 保守
        conservative_path = os.path.join(save_dir, f"backtest_{stock_id}_{timestamp}_60_40.csv")
        _save_to_csv(result_conservative, conservative_path)
        
        print(f"  積極 → {os.path.basename(active_path)}")
        print(f"  保守 → {os.path.basename(conservative_path)}")
    
    return result_active, result_conservative


def _save_to_csv(result: BacktestResult, filepath: str):
    """將回測結果的 signal_history 存成 CSV"""
    if result.signal_history.empty:
        return
    
    df_out = result.signal_history.copy()
    # date 轉字串
    if not df_out.empty and "date" in df_out.columns:
        df_out["date"] = df_out["date"].dt.strftime("%Y-%m-%d")
    
    # 確保欄位順序
    cols = ["date", "price", "high", "low",
            "MA_5", "MA_10", "MA_20", "MA_60",
            "pe_ratio", "PE_Percentile", "pb_ratio", "PB_Percentile",
            "Inst_Net", "dividend_yield",
            "agg_low", "agg_high",
            "cons_low", "cons_high",
            "price_in_range",
            "short_term_score", "short_term_signal",
            "swing_score", "swing_signal",
            "value_score", "value_signal",
            "dividend_score", "dividend_signal",
            "composite_signal"]
    exist_cols = [c for c in cols if c in df_out.columns]
    
    df_out.to_csv(filepath, index=False, encoding="utf-8-sig", 
                  columns=exist_cols)


# ============================================================
# 買賣訊號解析（內部函數）
# ============================================================

def _parse_trades(
    hist_df: pd.DataFrame,
    score_col: str,
    style_name: str,
    buy_threshold: int = 70,
    sell_threshold: int = 50,
    sell_score_col: str = None,
) -> List[TradeRecord]:
    """
    解析單一風格的買賣訊號
    
    買入：分數首次 ≥ buy_threshold
    賣出：分數跌破 sell_threshold
    
    Parameters:
        sell_score_col: 若指定，則賣出時使用該分數欄位（雙軌制）
    """
    trades = []
    holding = False
    entry_price = 0.0
    entry_date = None
    
    for i, row in hist_df.iterrows():
        score = row.get(score_col, 0)
        if pd.isna(score):
            score = 0
        
        if not holding:
            if score >= buy_threshold:
                holding = True
                entry_price = row.get("close", np.nan)
                entry_date = row["date"]
        else:
            # 賣出判斷：若指定 sell_score_col 則使用賣出評分，否則沿用買入評分
            if sell_score_col is not None:
                sell_score = row.get(sell_score_col, 0)
                if pd.isna(sell_score):
                    sell_score = 0
                should_sell = sell_score < sell_threshold
            else:
                should_sell = score < sell_threshold
            
            if should_sell:
                holding = False
                exit_price = row.get("close", np.nan)
                if pd.notna(entry_price) and pd.notna(exit_price) and entry_price > 0:
                    ret = (exit_price - entry_price) / entry_price * 100
                else:
                    ret = 0.0
                trades.append(TradeRecord(
                    entry_date=entry_date,
                    entry_price=entry_price,
                    exit_date=row["date"],
                    exit_price=exit_price,
                    style=style_name,
                    status="已出清",
                    return_pct=round(ret, 2),
                ))
    
    if holding:
        last_row = hist_df.iloc[-1]
        last_price = last_row.get("close", np.nan)
        if pd.notna(entry_price) and pd.notna(last_price) and entry_price > 0:
            ret = (last_price - entry_price) / entry_price * 100
        else:
            ret = 0.0
        trades.append(TradeRecord(
            entry_date=entry_date,
            entry_price=entry_price,
            exit_date=None,
            exit_price=None,
            style=style_name,
            status="持有中",
            return_pct=round(ret, 2),
        ))
    
    return trades


def _parse_composite_trades(
    hist_df: pd.DataFrame,
    style_scores: dict,
    buy_threshold: int = 70,
    sell_threshold: int = 50,
    sell_style_scores: dict = None,
) -> List[TradeRecord]:
    """
    解析綜合策略的買賣訊號
    
    買入：≥2 種風格分數 ≥ buy_threshold
    賣出：≥2 種風格分數 < sell_threshold
    成本：加權平均
    
    Parameters:
        sell_style_scores: 若指定，賣出時使用該分數欄位（雙軌制）
                          例如 {"short_term": "short_term_score_sell", "swing": "swing_score_sell"}
                          未指定的風格仍沿用買入評分
    """
    trades = []
    holding = False
    total_shares = 0.0
    total_cost = 0.0
    entry_date = None
    style_keys = list(style_scores.keys())
    
    for i, row in hist_df.iterrows():
        # 買入：永遠使用買入評分
        buy_scores = {}
        for style in style_keys:
            score = row.get(style_scores[style], 0)
            buy_scores[style] = 0 if pd.isna(score) else score
        
        if not holding:
            buy_count = sum(1 for s in buy_scores.values() if s >= buy_threshold)
            if buy_count >= 2:
                holding = True
                entry_price = row.get("close", np.nan)
                entry_date = row["date"]
                total_shares = 1.0
                total_cost = entry_price * total_shares
        else:
            # 賣出：若有指定賣出評分欄位則使用之
            sell_scores = {}
            for style in style_keys:
                if sell_style_scores is not None and style in sell_style_scores:
                    sc = row.get(sell_style_scores[style], 0)
                    sell_scores[style] = 0 if pd.isna(sc) else sc
                else:
                    sc = row.get(style_scores[style], 0)
                    sell_scores[style] = 0 if pd.isna(sc) else sc
            sell_count = sum(1 for s in sell_scores.values() if s < sell_threshold)
            if sell_count >= 2:
                holding = False
                exit_price = row.get("close", np.nan)
                if total_shares > 0:
                    avg_cost = total_cost / total_shares
                    ret = (exit_price - avg_cost) / avg_cost * 100
                else:
                    ret = 0.0
                trades.append(TradeRecord(
                    entry_date=entry_date,
                    entry_price=round(total_cost / total_shares, 2) if total_shares > 0 else 0,
                    exit_date=row["date"],
                    exit_price=exit_price,
                    style="composite",
                    status="已出清",
                    return_pct=round(ret, 2),
                ))
                total_shares = 0.0
                total_cost = 0.0
    
    if holding and total_shares > 0:
        last_row = hist_df.iloc[-1]
        last_price = last_row.get("close", np.nan)
        avg_cost = total_cost / total_shares
        if pd.notna(last_price) and avg_cost > 0:
            ret = (last_price - avg_cost) / avg_cost * 100
        else:
            ret = 0.0
        trades.append(TradeRecord(
            entry_date=entry_date,
            entry_price=round(avg_cost, 2),
            exit_date=None,
            exit_price=None,
            style="composite",
            status="持有中",
            return_pct=round(ret, 2),
        ))
    
    return trades


# ============================================================
# 雙彈夾 50/50 分批建倉策略
# ============================================================

def _parse_dual_bullet_trades(
    hist_df: pd.DataFrame,
    style_scores: dict,
    buy_threshold: int = 70,
    sell_threshold: int = 50,
    mode: str = "dip",
    drop_pct: float = -8.0,
) -> List[TradeRecord]:
    """
    50/50 雙彈夾分批建倉策略
    
    狀態機：
      state=0: 空手
      state=1: 持第一發（50%資金）
      state=2: 滿倉（兩發皆打）
    
    Args:
        hist_df: 歷史分數 DataFrame
        style_scores: 風格分數欄位對照
        buy_threshold: 買入門檻
        sell_threshold: 賣出門檻
        mode: 加碼模式（"dip"=下跌加碼, "breakout"=順勢突破）
        drop_pct: 下跌加碼門檻（如 -8.0 表示跌8%加碼）
    
    Returns:
        List[TradeRecord]: 雙彈夾交易記錄
    """
    trades = []
    state = 0       # 0=空手, 1=一發, 2=滿倉
    entry_1 = 0.0    # 第一發進場價
    entry_1_date = None
    entry_2 = 0.0    # 第二發進場價（若有加碼）
    entry_2_date = None
    avg_cost = 0.0   # 加權平均成本
    
    # 取四種風格分數的最高分作為綜合判斷
    score_cols = list(style_scores.values())
    
    for i, row in hist_df.iterrows():
        # 取當日最高分
        scores_today = [row.get(sc, 0) for sc in score_cols]
        scores_today = [s if pd.notna(s) else 0 for s in scores_today]
        best_score = max(scores_today) if scores_today else 0
        price = row.get("close", np.nan)
        
        if pd.isna(price):
            continue
        
        if state == 0:  # 空手
            if best_score >= buy_threshold:
                # 第一發進場
                state = 1
                entry_1 = price
                entry_1_date = row["date"]
                entry_2 = 0.0
                entry_2_date = None
                avg_cost = price  # 單一成本
        
        elif state == 1:  # 持第一發
            # 檢查是否應該賣出
            if best_score < sell_threshold:
                # 全數賣出
                ret = (price - entry_1) / entry_1 * 100 if entry_1 > 0 else 0.0
                trades.append(TradeRecord(
                    entry_date=entry_1_date,
                    entry_price=entry_1,
                    exit_date=row["date"],
                    exit_price=price,
                    style="dual_bullet",
                    status="已出清",
                    return_pct=round(ret, 2),
                ))
                state = 0
                continue
            
            # 檢查是否要加碼
            should_add = False
            if mode == "dip":
                # 下跌加碼：價格相較第一發跌超過 drop_pct%
                pct_change = (price / entry_1 - 1) * 100
                if pct_change <= drop_pct:
                    should_add = True
            elif mode == "breakout":
                # 順勢突破：分數創近期新高
                if best_score >= buy_threshold + 10:  # 比分數門檻高10分
                    should_add = True
            
            if should_add:
                # 第二發加碼
                state = 2
                entry_2 = price
                entry_2_date = row["date"]
                avg_cost = (entry_1 + entry_2) / 2
        
        elif state == 2:  # 滿倉
            if best_score < sell_threshold:
                # 全數賣出
                if avg_cost > 0:
                    ret = (price - avg_cost) / avg_cost * 100
                else:
                    ret = 0.0
                trades.append(TradeRecord(
                    entry_date=entry_1_date,
                    entry_price=entry_1,
                    entry_price_2=entry_2 if entry_2 > 0 else None,
                    avg_cost=avg_cost,
                    exit_date=row["date"],
                    exit_price=price,
                    style="dual_bullet",
                    status="已出清",
                    return_pct=round(ret, 2),
                ))
                state = 0
                entry_1 = 0.0
                entry_2 = 0.0
                avg_cost = 0.0
    
    # 期末仍持有
    if state == 1:
        last_price = hist_df.iloc[-1].get("close", np.nan)
        ret = (last_price - entry_1) / entry_1 * 100 if (entry_1 > 0 and pd.notna(last_price)) else 0.0
        trades.append(TradeRecord(
            entry_date=entry_1_date,
            entry_price=entry_1,
            exit_date=None,
            exit_price=None,
            style="dual_bullet",
            status="持有中",
            return_pct=round(ret, 2),
        ))
    elif state == 2:
        last_price = hist_df.iloc[-1].get("close", np.nan)
        ret = (last_price - avg_cost) / avg_cost * 100 if (avg_cost > 0 and pd.notna(last_price)) else 0.0
        trades.append(TradeRecord(
            entry_date=entry_1_date,
            entry_price=entry_1,
            entry_price_2=entry_2,
            avg_cost=avg_cost,
            exit_date=None,
            exit_price=None,
            style="dual_bullet",
            status="持有中",
            return_pct=round(ret, 2),
        ))
    
    return trades


# ============================================================
# 績效計算
# ============================================================

def _calc_total_return(trades: List[TradeRecord]) -> float:
    """計算總報酬率（已出清平均，無則取持有中）"""
    closed = [t for t in trades if t.status == "已出清"]
    if closed:
        total = sum(t.return_pct for t in closed)
        avg = total / len(closed)
        return round(avg, 2)
    holding = [t for t in trades if t.status == "持有中"]
    if holding:
        return round(holding[-1].return_pct, 2)
    return 0.0


def _calc_win_rate(trades: List[TradeRecord]) -> float:
    """計算勝率，無已出清交易時回傳 None"""
    closed = [t for t in trades if t.status == "已出清"]
    if not closed:
        return None
    wins = sum(1 for t in closed if t.return_pct > 0)
    return round(wins / len(closed) * 100, 1)


def _calc_realized_return_sum(trades: List[TradeRecord]) -> float:
    """已實現報酬率總和（已出清交易報酬率加總）"""
    closed = [t for t in trades if t.status == "已出清"]
    if not closed:
        return 0.0
    return round(sum(t.return_pct for t in closed), 2)


def _calc_unrealized_return(trades: List[TradeRecord]) -> Optional[float]:
    """未實現報酬率（最後一筆持有中交易的報酬率）"""
    holding = [t for t in trades if t.status == "持有中"]
    if not holding:
        return None
    return round(holding[-1].return_pct, 2)


# ============================================================
# 命令列輔助
# ============================================================

def print_summary(result: BacktestResult):
    """印出回測摘要"""
    buy_sell = f"買≥{result.buy_threshold}/賣<{result.sell_threshold}"
    strategy_label = {
        "active": f"積極({buy_sell})",
        "conservative": f"保守({buy_sell})",
    }.get(result.strategy, f"{result.strategy}({buy_sell})")
    
    print(f"\n{'='*60}")
    print(f"📊 {result.stock_id} | {strategy_label}")
    print(f"   區間: {result.start_date} ~ {result.end_date}")
    print(f"{'='*60}")
    
    for sk, sc in [("short_term", "短線"), ("swing", "波段"),
                   ("value", "價值"), ("dividend", "定存"), ("composite", "綜合")]:
        info = result.styles[sk]
        count = info["trade_count"]
        ret = info["total_return_pct"]
        wr = info["win_rate"]
        wr_str = f"{wr:.1f}%" if wr is not None else "N/A"
        print(f"  {sc}: {count}筆交易 | 報酬 {ret:+.2f}% | 勝率 {wr_str}")


if __name__ == "__main__":
    print("backtest.py — 回測分析模組完成")
    print("  可用函數:")
    print("    run_backtest(df, stock_id, ...) — 單一回測")
    print("    run_dual_backtest(df, stock_id, ..., output_dir=...) — 同時跑積極+保守")
    print("    _parse_dual_bullet_trades(...) — 50/50 雙彈夾分批建倉策略")