"""
core/backtest.py v1.0
回測分析模組 — 結合 walk-forward 評分與買賣訊號解析

提供：
1. run_backtest()：執行完整回測，產出五種策略（短線/波段/價值/定存/綜合）的交易記錄
2. 買賣訊號：基於分數 threshold 交叉，獨立於 trade_manager
3. 綜合策略：任一 ≥70 買入，≥2 種 <50 賣出，加權平均成本
"""
import pandas as pd
import numpy as np
from datetime import datetime, date
from dataclasses import dataclass, field
from typing import List, Optional


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

@dataclass
class BacktestResult:
    """回測結果"""
    stock_id: str = ""
    start_date: str = ""
    end_date: str = ""
    freq: str = "W"
    buy_threshold: int = 70
    sell_threshold: int = 50
    
    # 五種策略各自的交易記錄
    styles: dict = field(default_factory=lambda: {
        "short_term": {"trades": [], "total_return_pct": 0.0, "win_rate": 0.0, "trade_count": 0},
        "swing": {"trades": [], "total_return_pct": 0.0, "win_rate": 0.0, "trade_count": 0},
        "value": {"trades": [], "total_return_pct": 0.0, "win_rate": 0.0, "trade_count": 0},
        "dividend": {"trades": [], "total_return_pct": 0.0, "win_rate": 0.0, "trade_count": 0},
        "composite": {"trades": [], "total_return_pct": 0.0, "win_rate": 0.0, "trade_count": 0},
    })
    
    # 各風格歷史狀態（每個時間點的分數 + 訊號）
    signal_history: pd.DataFrame = field(default_factory=pd.DataFrame)


def run_backtest(
    df: pd.DataFrame,
    stock_id: str,
    start_date: str = None,
    end_date: str = None,
    freq: str = 'W',
    buy_threshold: int = 70,
    sell_threshold: int = 50,
) -> BacktestResult:
    """
    執行完整回測
    
    流程：
    1. 呼叫 get_historical_scores 取得歷史分數
    2. 五種策略各自解析買賣訊號
    3. 計算各策略績效
    
    Parameters:
        df: 母表 DataFrame
        stock_id: 股票代號
        start_date: 回測起始日
        end_date: 回測結束日
        freq: 頻率（D/W/M/Q）
        buy_threshold: 買入門檻分數（預設 70）
        sell_threshold: 賣出門檻分數（預設 50）
    
    Returns:
        BacktestResult: 完整回測結果
    """
    from core.scorer import get_historical_scores
    
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
        )
    
    # 確保 date 是 datetime
    hist_df = hist_df.copy()
    if not pd.api.types.is_datetime64_any_dtype(hist_df["date"]):
        hist_df["date"] = pd.to_datetime(hist_df["date"])
    hist_df = hist_df.sort_values("date").reset_index(drop=True)
    
    # 合併價格資料
    if "close" in df.columns and "date" in df.columns:
        price_df = df[["date", "close"]].copy()
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
    )
    
    # === 2. 五種策略各自解析買賣訊號 ===
    
    # 四種風格獨立策略
    for style in style_keys:
        score_col = style_scores[style]
        trades = _parse_trades(
            hist_df, score_col, style,
            buy_threshold, sell_threshold,
        )
        result.styles[style]["trades"] = trades
        result.styles[style]["trade_count"] = len(trades)
        result.styles[style]["total_return_pct"] = _calc_total_return(trades)
        result.styles[style]["win_rate"] = _calc_win_rate(trades)
    
    # 綜合策略：任一 ≥70 買入，≥2 種 <50 賣出
    composite_trades = _parse_composite_trades(
        hist_df, style_scores,
        buy_threshold, sell_threshold,
    )
    result.styles["composite"]["trades"] = composite_trades
    result.styles["composite"]["trade_count"] = len(composite_trades)
    result.styles["composite"]["total_return_pct"] = _calc_total_return(composite_trades)
    result.styles["composite"]["win_rate"] = _calc_win_rate(composite_trades)
    
    # === 3. 訊號歷史（給 CSV 輸出和圖表用） ===
    signal_records = []
    for i, row in hist_df.iterrows():
        record = {
            "date": row["date"],
            "price": row.get("close", np.nan),
        }
        for style in style_keys:
            score_col = style_scores[style]
            record[score_col] = row.get(score_col, np.nan)
            
            # 檢查該時間點是否剛好買入
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
                # 檢查是否持有中
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


def _parse_trades(
    hist_df: pd.DataFrame,
    score_col: str,
    style_name: str,
    buy_threshold: int = 70,
    sell_threshold: int = 50,
) -> List[TradeRecord]:
    """
    解析單一風格的買賣訊號
    
    買入：分數首次 ≥ buy_threshold
    賣出：分數跌破 sell_threshold
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
            # 尋找買入點
            if score >= buy_threshold:
                holding = True
                entry_price = row.get("close", np.nan)
                entry_date = row["date"]
        else:
            # 尋找賣出點
            if score < sell_threshold:
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
    
    # 若最後一筆仍在持有中
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
) -> List[TradeRecord]:
    """
    解析綜合策略的買賣訊號
    
    買入：任一風格分數 ≥ buy_threshold
    賣出：≥2 種風格分數 < sell_threshold
    成本：加權平均
    """
    trades = []
    holding = False
    total_shares = 0.0   # 虛擬股數（僅供加權平均成本計算）
    total_cost = 0.0      # 總成本（價格 × 股數）
    entry_date = None
    style_keys = list(style_scores.keys())
    
    for i, row in hist_df.iterrows():
        # 取得各風格分數
        scores = {}
        for style in style_keys:
            score = row.get(style_scores[style], 0)
            scores[style] = 0 if pd.isna(score) else score
        
        if not holding:
            # 綜合買入條件：任一風格 ≥ threshold
            if any(s >= buy_threshold for s in scores.values()):
                holding = True
                entry_price = row.get("close", np.nan)
                entry_date = row["date"]
                # 初始化加權平均
                total_shares = 1.0
                total_cost = entry_price * total_shares
        else:
            # 綜合賣出條件：≥2 種風格 < threshold
            sell_count = sum(1 for s in scores.values() if s < sell_threshold)
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
            else:
                # 檢查是否有加碼訊號（其他風格也觸發買入，視為加碼）
                # 任何風格仍 ≥ buy_threshold 就繼續持有
                pass
    
    # 最後若仍在持有
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


def _calc_total_return(trades: List[TradeRecord]) -> float:
    """計算總報酬率
    - 有已出清交易：取已出清交易平均報酬率
    - 只有持有中交易：取最後一筆持有中交易的未實現報酬率
    - 無交易：0%
    """
    closed = [t for t in trades if t.status == "已出清"]
    if closed:
        total = sum(t.return_pct for t in closed)
        avg = total / len(closed)
        return round(avg, 2)
    # 只有持有中交易：取最後一筆的未實現報酬
    holding = [t for t in trades if t.status == "持有中"]
    if holding:
        return round(holding[-1].return_pct, 2)
    return 0.0


def _calc_win_rate(trades: List[TradeRecord]) -> float:
    """計算勝率（已出清交易的獲利比例），無已出清交易時回傳 None"""
    closed = [t for t in trades if t.status == "已出清"]
    if not closed:
        return None
    wins = sum(1 for t in closed if t.return_pct > 0)
    return round(wins / len(closed) * 100, 1)


if __name__ == "__main__":
    print("backtest.py v1.0 - 回測分析模組完成")