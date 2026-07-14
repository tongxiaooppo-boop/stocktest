"""
ai/analyzer.py
DeepSeek API 呼叫 — Explain Engine 版本

v4.0 重大改版：
1. 不再傳入原始數據（df_summary），AI 只能看到評分結果
2. AI 輸出改為 explanation 格式（解說），非 decision 格式（決策）
3. 新增 build_evidence_json() 供前端直接使用
4. 降級回應改為回傳 explanation 格式
"""

import json
import re
from openai import OpenAI
from ai.prompts import build_system_prompt, build_user_message, build_evidence_json


def analyze_with_deepseek(
    stock_id: str,
    stock_name: str,
    scores: dict,
    advice: dict,
    has_position: bool = False,
    avg_price: float = 0.0,
    shares: int = 0,
    api_key: str = "",
    trade_advice: object = None,
    sentiment_data: dict = None,
) -> dict:
    """
    呼叫 DeepSeek API 進行 AI 解說分析
    
    Parameters:
        stock_id: 股票代號
        stock_name: 股票名稱
        scores: 四種風格分數（含 breakdown）
        advice: 基本建議（advisor.get_advice() 回傳值）
        has_position: 是否持有
        avg_price: 持股均價
        shares: 股數
        api_key: DeepSeek API Key（由前端傳入）
        trade_advice: 持倉判斷物件（可選）
        sentiment_data: 新聞輿情統計 dict（可選，有資料才傳）
    
    Returns:
        dict: {
            "explanation": {
                "summary": "...",
                "strengths": [...],
                "weaknesses": [...],
                "suitable_for": "...",
                "risk_warning": "...",
                "watch_items": [...]
            },
            "evidence": {...}  # Evidence JSON
        }
    """
    if not api_key:
        return _build_fallback_explanation(
            stock_id, stock_name,
            "請輸入 DeepSeek API Key"
        )
    
    try:
        # 建構 Prompt（只含評分結果，不含原始數據）
        system_prompt = build_system_prompt()
        user_message = build_user_message(
            stock_id, stock_name, scores, advice,
            has_position, avg_price, shares,
            trade_advice=trade_advice,
            sentiment_data=sentiment_data,
        )
        
        # 呼叫 DeepSeek API
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        
        # 解析回傳
        content = response.choices[0].message.content.strip()
        
        # 嘗試從回傳中提取 JSON
        result = _extract_json(content)
        
        if result is None:
            return _build_fallback_explanation(
                stock_id, stock_name,
                "AI 回傳格式異常，無法解析"
            )
        
        # 確保 explanation 格式
        if "explanation" not in result:
            # 嘗試將結果包裝成 explanation
            result = {"explanation": result}
        
        # 加入 Evidence JSON
        evidence = build_evidence_json(scores, advice)
        result["evidence"] = evidence
        result["stock_id"] = stock_id
        result["stock_name"] = stock_name
        
        return result
        
    except Exception as e:
        return _build_fallback_explanation(
            stock_id, stock_name,
            f"AI 分析異常: {str(e)}"
        )


def _extract_json(text: str) -> dict:
    """從文字中提取 JSON 物件"""
    # 嘗試直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 嘗試用正則表達式提取 JSON 區塊
    json_pattern = r'```(?:json)?\s*([\s\S]*?)```'
    matches = re.findall(json_pattern, text)
    
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue
    
    # 嘗試找第一個 { 到最後一個 }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass
    
    return None


def _build_fallback_explanation(
    stock_id: str,
    stock_name: str,
    error_msg: str,
) -> dict:
    """建構降級回應（API 失敗時使用）"""
    return {
        "stock_id": stock_id,
        "stock_name": stock_name,
        "explanation": {
            "summary": f"AI 解說暫時不可用：{error_msg}",
            "strengths": [],
            "weaknesses": [],
            "suitable_for": "無法判斷",
            "risk_warning": error_msg,
            "watch_items": ["請稍後再試"],
        },
        "evidence": {},
    }


if __name__ == "__main__":
    print("analyzer.py — Explain Engine 版本完成")
    print("支援 DeepSeek API 呼叫，輸出 explanation 格式")
