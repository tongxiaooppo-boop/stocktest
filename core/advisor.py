"""
core/advisor.py
基本建議規則（買/持有/賣）

讀取 scorer 分數（含 breakdown），輸出制式建議
純 Python，不依賴 AI，可解釋性高
"""

from core.scorer import get_style_label as _get_style_label


def get_advice(scores: dict) -> dict:
    """
    根據四種風格分數輸出基本建議
    
    Parameters:
        scores: scorer.get_all_scores() 的回傳值
                {"short_term": {"total": 78, "breakdown": {...}}, ...}
    
    Returns:
        dict: {
            "advice": "強烈買進/買進/持有/賣出/強烈賣出",
            "best_style": "short_term",
            "best_score": 78,
            "all_scores": {...},
        }
    """
    # 取出各風格總分
    style_totals = {}
    for style, data in scores.items():
        if isinstance(data, dict) and "total" in data:
            style_totals[style] = data["total"]
        elif isinstance(data, (int, float)):
            style_totals[style] = data
    
    if not style_totals:
        return {"advice": "持有", "best_style": None, "best_score": 0, "all_scores": scores}
    
    # 找出最高分風格
    best_style = max(style_totals, key=style_totals.get)
    best_score = style_totals[best_style]
    
    # 根據最高分決定建議
    if best_score >= 80:
        advice = "強烈買進"
    elif best_score >= 60:
        advice = "買進"
    elif best_score >= 40:
        advice = "持有"
    elif best_score >= 20:
        advice = "賣出"
    else:
        advice = "強烈賣出"
    
    return {
        "advice": advice,
        "best_style": best_style,
        "best_score": best_score,
        "all_scores": scores,
    }


def get_style_label(style: str) -> str:
    """取得風格中文名稱（委託 scorer 的 get_style_label）"""
    return _get_style_label(style)


if __name__ == "__main__":
    print("advisor.py - 斷點 8 實作完成")
