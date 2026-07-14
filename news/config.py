"""
news/config.py
新聞模組設定檔
"""

import os

# 資料庫路徑（放在專案根目錄）
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "news_sentiment.db")

# 預設單次查詢抓取篇數
DEFAULT_LIMIT = 10

# Google News RSS 設定（中文財經新聞）
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"

# Yahoo Finance RSS 設定（英文財經新聞，作為第二來源）
YAHOO_FINANCE_RSS_URL = "https://finance.yahoo.com/rss/headline"
