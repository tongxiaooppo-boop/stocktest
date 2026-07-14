"""
news/fetcher.py
新聞抓取模組 — 同時從 Yahoo Finance RSS 與 Google News RSS 抓取指定個股新聞

抓取來源：
1. Yahoo Finance RSS（https://finance.yahoo.com/rss/headline）
2. Google News RSS（https://news.google.com/rss/search）

注意：鉅亨網 API (cnyes.com) 在部分環境 DNS 無法解析，因此改用 Yahoo Finance 作為第二來源。

輸出格式（統一）：
{
    "stock_id": "2330",
    "publish_time": "2024-01-15 10:30:00",
    "title": "台積電法說會...",
    "source": "Yahoo Finance",
    "link": "https://...",
    "sentiment_score": 0.0,   # 預設 0，由 analyzer 填入
}
"""

import time
import requests
import feedparser
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from .config import DEFAULT_LIMIT, GOOGLE_NEWS_RSS_URL, YAHOO_FINANCE_RSS_URL


def _stock_to_yahoo_symbol(stock_id: str) -> str:
    """
    將台股代號轉為 Yahoo Finance 專用代號
    
    上市股票（1、2、3、4、6 開頭）：suffix .TW
    上櫃股票（5、7、8 開頭 或 4碼但非上市）：suffix .TWO
    其他情況預設 .TW
    
    Args:
        stock_id: 台股代號（如 "2330"、"5483"）
    
    Returns:
        Yahoo Finance 格式（如 "2330.TW"、"5483.TWO"）
    """
    stock_id = stock_id.strip()
    if not stock_id.isdigit():
        return f"{stock_id}.TW"
    
    first_digit = stock_id[0]
    # 上市：1,2,3,4,6 開頭
    if first_digit in ('1', '2', '3', '4', '6'):
        return f"{stock_id}.TW"
    # 上櫃：5,7,8 開頭
    elif first_digit in ('5', '7', '8'):
        return f"{stock_id}.TWO"
    # 其他（0,9 等）預設上市
    return f"{stock_id}.TW"


def _search_yahoo_finance(stock_id: str, limit: int = 10) -> List[Dict]:
    """
    從 Yahoo Finance RSS 抓取指定個股新聞

    URL: https://finance.yahoo.com/rss/headline?s={symbol}

    Args:
        stock_id: 股票代號（如 2330）
        limit: 抓取篇數

    Returns:
        新聞列表（尚未填入 sentiment_score）
    """
    results = []
    try:
        # 自動判斷上市/上櫃，轉為 Yahoo Finance 格式
        yahoo_symbol = _stock_to_yahoo_symbol(stock_id)
        rss_url = f"{YAHOO_FINANCE_RSS_URL}?s={yahoo_symbol}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        feed = feedparser.parse(rss_url)
        entries = feed.entries[:limit]

        for entry in entries:
            title = (entry.get("title") or "").strip()
            link = entry.get("link", "")
            pub_time = entry.get("published", "") or entry.get("updated", "") or ""

            if not title:
                continue

            pub_time = _normalize_time(pub_time)

            results.append({
                "stock_id": stock_id,
                "publish_time": pub_time,
                "title": title,
                "source": "Yahoo Finance",
                "link": link,
                "sentiment_score": 0.0,  # placeholder
            })

    except Exception as e:
        print(f"[FETCH_ERROR] 抓取 Yahoo Finance 新聞時發生異常：{e}")

    return results


def _search_google_news(stock_id: str, limit: int = 10) -> List[Dict]:
    """
    從 Google News RSS 抓取新聞

    Args:
        stock_id: 股票代號

    Returns:
        新聞列表（尚未填入 sentiment_score）
    """
    results = []
    try:
        # 查詢關鍵字：台股 + 股票代號
        query = f"{stock_id} 台股 股票"
        rss_url = f"{GOOGLE_NEWS_RSS_URL}?q={requests.utils.quote(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"

        feed = feedparser.parse(rss_url)
        entries = feed.entries[:limit]

        stock_suffix = stock_id[-4:] if len(stock_id) >= 4 else stock_id

        for entry in entries:
            title = (entry.get("title") or "").strip()
            link = entry.get("link", "")
            pub_time = entry.get("published", "") or entry.get("updated", "") or ""

            # 過濾：標題必須包含股票代號或相關關鍵字
            if stock_suffix not in title and stock_id not in title:
                continue

            if not title:
                continue

            pub_time = _normalize_time(pub_time)

            results.append({
                "stock_id": stock_id,
                "publish_time": pub_time,
                "title": title,
                "source": "Google News",
                "link": link,
                "sentiment_score": 0.0,  # placeholder
            })
    except Exception as e:
        print(f"[FETCH_ERROR] 抓取 Google News 時發生異常：{e}")

    return results


def _normalize_time(time_str: str) -> str:
    """
    將各種時間格式標準化為 YYYY-MM-DD HH:MM:SS

    Supports:
        - ISO 8601: 2024-01-15T10:30:00Z
        - RSS: Mon, 15 Jan 2024 10:30:00 GMT
        - 簡潔: 2024-01-15 10:30:00
        - 日期 only: 2024-01-15
    """
    if not time_str or time_str == "None":
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 嘗試 ISO 8601
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        pass

    # 嘗試 RSS 格式
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(time_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass

    # 嘗試 YYYY-MM-DD
    match = re.match(r"(\d{4}-\d{2}-\d{2})", str(time_str))
    if match:
        return match.group(1) + " 00:00:00"

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _deduplicate(news_list: List[Dict]) -> List[Dict]:
    """
    去除重複新聞（基於 title 相似度比對）

    Args:
        news_list: 原始新聞列表

    Returns:
        去重後的新聞列表
    """
    seen_titles = set()
    unique = []
    for news in news_list:
        # 取標題前 20 個字作為唯一性判斷
        title_key = news["title"][:20].strip().lower()
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique.append(news)
    return unique


def fetch_news(stock_id: str, limit: int = None) -> List[Dict]:
    """
    主要公開函數：同時從 Yahoo Finance 與 Google News 抓取指定個股新聞，
    合併、去重後回傳

    Args:
        stock_id: 股票代號（如 "2330"）
        limit: 總共回傳篇數（預設使用 config.DEFAULT_LIMIT）

    Returns:
        統一格式的新聞列表（sentiment_score 預設為 0，
        需呼叫 analyzer.analyze() 填入）
    """
    if limit is None:
        limit = DEFAULT_LIMIT

    # 兩邊各抓多一些，去重後保留 limit 篇
    each_limit = max(limit * 2, 15)

    yahoo_news = _search_yahoo_finance(stock_id, limit=each_limit)
    google_news = _search_google_news(stock_id, limit=each_limit)

    print(f"[FETCH] Yahoo Finance {len(yahoo_news)} 篇 | Google News {len(google_news)} 篇 | 目標 {limit} 篇")

    # 合併 + 去重
    all_news = yahoo_news + google_news
    all_news = _deduplicate(all_news)

    # 依時間排序（最新的在前）
    all_news.sort(key=lambda x: x["publish_time"], reverse=True)

    return all_news[:limit]