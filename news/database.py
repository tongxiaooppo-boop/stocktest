"""
news/database.py
SQLite 資料庫管理模組

核心資料表 news_sentiment:
  id                  INTEGER PRIMARY KEY AUTOINCREMENT
  stock_id            TEXT NOT NULL
  publish_time        TEXT NOT NULL
  title               TEXT NOT NULL
  source              TEXT NOT NULL
  link                TEXT NOT NULL UNIQUE
  sentiment_score     REAL
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from .config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """取得資料庫連線（每次呼叫確保資料表存在）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _init_table(conn)
    return conn


def _init_table(conn: sqlite3.Connection):
    """初始化 news_sentiment 資料表"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news_sentiment (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id            TEXT NOT NULL,
            publish_time        TEXT NOT NULL,
            title               TEXT NOT NULL,
            source              TEXT NOT NULL,
            link                TEXT NOT NULL UNIQUE,
            sentiment_score     REAL,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_stock_id ON news_sentiment(stock_id)
    """)
    conn.commit()


def save_news(news_list: List[Dict]) -> Tuple[int, int]:
    """
    將新聞列表存入資料庫，跳過已存在（link 重複）的新聞
    
    Args:
        news_list: 新聞列表，每筆須含 stock_id, publish_time, title, source, link, sentiment_score
    
    Returns:
        (inserted_count, total_count) 插入筆數 vs 總筆數
    """
    if not news_list:
        return (0, 0)
    
    conn = get_connection()
    inserted = 0
    for news in news_list:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO news_sentiment 
                (stock_id, publish_time, title, source, link, sentiment_score)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                news.get("stock_id", ""),
                news.get("publish_time", ""),
                news.get("title", ""),
                news.get("source", ""),
                news.get("link", ""),
                news.get("sentiment_score", 0.0),
            ))
            if conn.total_changes > 0:
                inserted += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return (inserted, len(news_list))


def get_historical_sentiment(stock_id: str, limit: int = 50) -> List[Dict]:
    """
    查詢個股歷史新聞與情緒分數
    
    Args:
        stock_id: 股票代號
        limit: 最多回傳筆數
    
    Returns:
        新聞列表（含 sentiment_score），依 publish_time DESC 排序
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT stock_id, publish_time, title, source, link, sentiment_score, created_at
        FROM news_sentiment
        WHERE stock_id = ?
        ORDER BY publish_time DESC
        LIMIT ?
    """, (stock_id, limit)).fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_aggregate_sentiment(stock_id: str) -> Optional[Dict]:
    """
    計算個股歷史新聞的綜合情緒統計
    
    Args:
        stock_id: 股票代號
    
    Returns:
        {
            "avg_score": float,       # 平均情緒分數
            "max_score": float,       # 最高分
            "min_score": float,       # 最低分
            "total_news": int,        # 新聞總數
            "positive_count": int,    # 偏多新聞數 (>0)
            "negative_count": int,    # 偏空新聞數 (<0)
            "neutral_count": int,     # 中性新聞數 (=0)
        }
        若無資料回傳 None
    """
    conn = get_connection()
    row = conn.execute("""
        SELECT 
            AVG(sentiment_score) as avg_score,
            MAX(sentiment_score) as max_score,
            MIN(sentiment_score) as min_score,
            COUNT(*) as total_news,
            SUM(CASE WHEN sentiment_score > 0 THEN 1 ELSE 0 END) as positive_count,
            SUM(CASE WHEN sentiment_score < 0 THEN 1 ELSE 0 END) as negative_count,
            SUM(CASE WHEN sentiment_score = 0 THEN 1 ELSE 0 END) as neutral_count
        FROM news_sentiment
        WHERE stock_id = ?
    """, (stock_id,)).fetchone()
    conn.close()
    
    if row and row["total_news"] > 0:
        return dict(row)
    return None


def delete_old_news(stock_id: str, keep_count: int = 200):
    """
    刪除該個股過舊的新聞，只保留最新的 keep_count 筆
    """
    conn = get_connection()
    conn.execute("""
        DELETE FROM news_sentiment
        WHERE id NOT IN (
            SELECT id FROM news_sentiment
            WHERE stock_id = ?
            ORDER BY publish_time DESC
            LIMIT ?
        ) AND stock_id = ?
    """, (stock_id, keep_count, stock_id))
    conn.commit()
    conn.close()


# ============================================================
# 分析快取持久化（analysis_cache 資料表）
# F5 刷新後可從此表載入上次的分析結果，避免重新撈取所有 FinMind 資料
# ============================================================

import json
import pickle
from typing import Any

def _init_analysis_cache_table(conn: sqlite3.Connection):
    """初始化 analysis_cache 資料表"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_cache (
            stock_id            TEXT PRIMARY KEY,
            scores_json         TEXT,
            advice_json         TEXT,
            ai_result_json      TEXT,
            trade_advice_blob   BLOB,
            fetch_info_json     TEXT,
            stock_name          TEXT,
            cache_date          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def get_cache_conn() -> sqlite3.Connection:
    """取得可讀寫 analysis_cache 的連線"""
    conn = sqlite3.connect(DB_PATH)
    _init_analysis_cache_table(conn)
    return conn


def save_analysis_cache(
    stock_id: str,
    scores: dict,
    advice: dict,
    ai_result: dict = None,
    trade_advice: Any = None,
    fetch_info: dict = None,
    stock_name: str = "",
) -> None:
    """
    將分析結果（不含 DataFrame）存入 SQLite
    
    Args:
        scores: get_all_scores() 回傳的 dict
        advice: get_advice() 回傳的 dict
        ai_result: analyze_with_deepseek() 回傳的 dict（可為 None）
        trade_advice: generate_trade_advice() 回傳的物件（可為 None）
        fetch_info: 撈取資訊 dict（可為 None）
        stock_name: 股票名稱
    """
    trade_advice_blob = None
    if trade_advice is not None:
        try:
            trade_advice_blob = pickle.dumps(trade_advice)
        except Exception:
            trade_advice_blob = None  # 無法序列化則跳過
    
    conn = get_cache_conn()
    conn.execute("""
        INSERT OR REPLACE INTO analysis_cache
        (stock_id, scores_json, advice_json, ai_result_json, 
         trade_advice_blob, fetch_info_json, stock_name, cache_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        stock_id,
        json.dumps(scores, ensure_ascii=False, default=str),
        json.dumps(advice, ensure_ascii=False, default=str),
        json.dumps(ai_result, ensure_ascii=False, default=str) if ai_result else None,
        trade_advice_blob,
        json.dumps(fetch_info, ensure_ascii=False, default=str) if fetch_info else None,
        stock_name,
    ))
    conn.commit()
    conn.close()


def load_analysis_cache(stock_id: str) -> Optional[Dict]:
    """
    從 SQLite 載入該個股上一次的分析結果
    
    Args:
        stock_id: 股票代號
    
    Returns:
        dict 或 None:
        {
            "scores": dict,
            "advice": dict,
            "ai_result": dict or None,
            "trade_advice": object or None,
            "fetch_info": dict or None,
            "stock_name": str,
        }
    """
    conn = get_cache_conn()
    row = conn.execute("""
        SELECT scores_json, advice_json, ai_result_json, 
               trade_advice_blob, fetch_info_json, stock_name, cache_date
        FROM analysis_cache
        WHERE stock_id = ?
    """, (stock_id,)).fetchone()
    conn.close()
    
    if not row:
        return None
    
    result = {}
    
    # scores
    if row[0]:
        result["scores"] = json.loads(row[0])
    else:
        return None  # scores 是必須的，沒有就視為無效快取
    
    # advice
    if row[1]:
        result["advice"] = json.loads(row[1])
    else:
        return None
    
    # ai_result
    result["ai_result"] = json.loads(row[2]) if row[2] else None
    
    # trade_advice（pickle 反序列化）
    if row[3]:
        try:
            result["trade_advice"] = pickle.loads(row[3])
        except Exception:
            result["trade_advice"] = None
    else:
        result["trade_advice"] = None
    
    # fetch_info
    result["fetch_info"] = json.loads(row[4]) if row[4] else {}
    
    # stock_name
    result["stock_name"] = row[5] or stock_id
    
    # cache_date（用於判斷快取是否過期）
    result["cache_date"] = row[6] if len(row) > 6 else None
    
    return result


def delete_analysis_cache(stock_id: str) -> None:
    """刪除指定個股的分析快取"""
    conn = get_cache_conn()
    conn.execute("DELETE FROM analysis_cache WHERE stock_id = ?", (stock_id,))
    conn.commit()
    conn.close()
