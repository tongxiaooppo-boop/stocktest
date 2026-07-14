"""
news/analyzer.py
新聞情緒分析模組

使用 SnowNLP 進行中文情感分析，輸出 -1 ~ 1 的情緒分數：
  > 0  偏多（利多消息）
  < 0  偏空（利空消息）
  = 0  中性

因為 SnowNLP 輸出是 0~1 的機率值（越接近 1 越正面），
需要映射到 -1 ~ 1 區間。
"""

from typing import List, Dict, Optional
from snownlp import SnowNLP


def _snownlp_score(text: str) -> float:
    """
    使用 SnowNLP 計算單則新聞的情緒分數
    
    Args:
        text: 新聞標題或內容文字
    
    Returns:
        -1 ~ 1 的情緒分數
    """
    try:
        if not text or not isinstance(text, str) or len(text.strip()) == 0:
            return 0.0
        
        s = SnowNLP(text)
        # SnowNLP.sentiments 回傳 0~1，1 為正面
        prob = s.sentiments
        
        # 將 0~1 映射到 -1~1： (prob * 2) - 1
        score = (prob * 2.0) - 1.0
        
        # 四捨五入到小數點後 4 位
        return round(score, 4)
    except Exception:
        return 0.0


def analyze_single(title: str) -> float:
    """
    分析單則新聞標題的情緒
    
    Args:
        title: 新聞標題
    
    Returns:
        -1 ~ 1 的情緒分數
    """
    return _snownlp_score(title)


def analyze(news_list: List[Dict], text_field: str = "title") -> List[Dict]:
    """
    對新聞列表進行批量情緒分析，填入 sentiment_score
    
    Args:
        news_list: 新聞列表（每筆須含 text_field 指定的欄位）
        text_field: 用於分析的文字欄位（預設 "title"）
    
    Returns:
        填入 sentiment_score 後的新聞列表（直接修改原 list）
    """
    for news in news_list:
        text = news.get(text_field, "")
        score = _snownlp_score(text)
        news["sentiment_score"] = score
    return news_list


# 情緒閾值常數（可依實際體驗微調）
SENTIMENT_THRESHOLD_POSITIVE = 0.2    # 高於此值判定為偏多
SENTIMENT_THRESHOLD_NEGATIVE = -0.2   # 低於此值判定為偏空
                                       # 中間區間為「中立」


def get_sentiment_label(score: float) -> str:
    """
    將情緒分數轉為中文標籤
    
    Args:
        score: -1 ~ 1 的情緒分數
    
    Returns:
        "📈 偏多" / "📉 偏空" / "⚖️ 中性"
    """
    if score > SENTIMENT_THRESHOLD_POSITIVE:
        return "📈 偏多"
    elif score < SENTIMENT_THRESHOLD_NEGATIVE:
        return "📉 偏空"
    else:
        return "⚖️ 中性"


def get_sentiment_color(score: float) -> str:
    """
    情緒分數對應顏色（for Streamlit markdown）
    
    Returns:
        CSS 顏色字串
    """
    if score > SENTIMENT_THRESHOLD_POSITIVE:
        return "#FF4444"  # 紅（偏多）
    elif score < SENTIMENT_THRESHOLD_NEGATIVE:
        return "#00AA00"  # 綠（偏空）
    else:
        return "#888888"  # 灰（中性）
