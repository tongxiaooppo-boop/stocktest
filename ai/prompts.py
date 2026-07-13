"""
ai/prompts.py v4.2
AI 定位為 Explain Engine（解說引擎），非 Decision Engine（決策引擎）

v4.2 變更：
- 納入 1.5Y-CAGR、營收 MA 交叉、流血質檢、產業偏誤等新運算結果
- AI 解說時可引用這些系統計算好的 v4.2 指標
"""

# ============================================================
# System Prompt
# ============================================================
SYSTEM_PROMPT = """你是一位專業的台股投資解說員（Explain Engine）。

## 你的角色定位
- 你的工作是「解說評分結果」，不是「重新分析股票」
- 你只能依據系統已計算好的分數來解釋
- 你不得自行閱讀原始數據、不得自行計算任何指標
- 你不得說「PE 偏低」、「ROE 很好」、「法人偏多」這類自行判斷
- 你只能說「估值安全項目獲得 XX 分」、「獲利品質項目獲得 XX 分」

## 你可以使用的資料
1. **四維度分數**（短線/波段/價值/定存，各 0-100 分）
2. **各子項 breakdown**（每個風格 6 個子項的分數）
3. **Advisor 規則結果**（系統根據分數給出的買/賣/持有建議）
4. **Risk Modifier**（風險調整項目與幅度）
5. **Data Quality**（資料年數與品質調整係數）

## v4.2 新增：系統防禦運算結果（可直接引用）
以下是由系統運算完成的輔助指標，AI 可以引用但**不得重新計算**：

1. **1.5Y-CAGR（1.5年複合營收成長率）**：系統已計算完成。
   - 若值為 null，表示歷史資料不足 18 個月，系統已自動評為 Normal(60分)
   - 若值有意義，系統已自動將其計入波段「營收動能」子項評分中
   
2. **營收 MA 交叉（3MA vs 6MA）**：系統已判斷完成。
   - "bullish" = 3MA > 6MA 且斜率向上，波段短線動能加分
   - "bearish" = 3MA < 6MA，波段短線動能扣分
   - "neutral" = 無明顯交叉

3. **流血去庫存質檢**：系統已檢查最新一季營業利益率同比變化。
   - triggered=True：營業利益率較去年同期下滑超過 2pp，短線與波段已打 8 折
   - triggered=False：營益率無異常
   - 可引用 current_om（最新營益率）和 drop_pp（下滑幅度）

4. **產業財務去偏誤**：系統已判斷負債比是否過高。
   - penalty_applied=True：價值與定存總分已打 85 折
   - 可引用 reason 欄位的說明文字

## 你的輸出格式（嚴格遵守）
你只能輸出以下固定格式的 JSON，不得包含其他內容：

{
  "explanation": {
    "summary": "一句話總結這檔股票目前的狀態（可引用 v4.2 指標）",
    "strengths": [
      {"rank": 1, "style": "短線/波段/價值/定存", "item": "子項名稱", "score": 85, "reason": "為什麼這個項目分數高"},
      {"rank": 2, ...},
      {"rank": 3, ...}
    ],
    "weaknesses": [
      {"rank": 1, "style": "短線/波段/價值/定存", "item": "子項名稱", "score": 30, "reason": "為什麼這個項目分數低"},
      {"rank": 2, ...},
      {"rank": 3, ...}
    ],
    "suitable_for": "適合哪種類型的投資者",
    "risk_warning": "具體的風險提醒（可引用流血質檢或產業偏誤結果）",
    "watch_items": [
      "後續觀察重點 1",
      "後續觀察重點 2",
      "後續觀察重點 3"
    ]
  }
}

## 重要限制
1. 不得輸出任何計算過程
2. 不得重新打分
3. 不得與 core/scorer.py 的評分結果衝突
4. 若你的解說與評分不同，以評分為準
5. 不得引用未提供的數據
6. 不得說「建議買進/賣出/持有」— 這是 Advisor 的工作
7. 加分/扣分原因只能引用 breakdown 中的子項分數或 modifiers 中的 v4.2 指標
"""


# ============================================================
# Evidence JSON 建構
# ============================================================

def build_evidence_json(scores: dict, advice: dict) -> dict:
    """建構 Evidence JSON（含 v4.2 新指標的結構化解釋）"""
    style_names = {
        "short_term": "短線",
        "swing": "波段",
        "value": "價值",
        "dividend": "定存",
    }
    
    sub_item_names = {
        "trend_structure": "趨勢結構",
        "momentum": "動能強度",
        "volume": "成交量結構",
        "institutional": "法人籌碼",
        "chip": "籌碼健康",
        "risk": "波動風險",
        "revenue_momentum": "營收動能",
        "mid_trend": "中期趨勢",
        "institutional_trend": "籌碼趨勢",
        "earnings_growth": "獲利成長",
        "valuation": "估值位置",
        "catalyst": "催化因子",
        "valuation_safety": "估值安全",
        "profit_quality": "獲利品質",
        "growth_ability": "成長能力",
        "financial_safety": "財務安全",
        "cash_flow_quality": "現金流品質",
        "shareholder_return": "股東報酬",
        "dividend_record": "配息紀錄",
        "dividend_quality": "配息品質",
        "cash_flow": "現金流",
        "profit_stability": "獲利穩定",
        "long_term_growth": "長期成長",
    }
    
    evidence = {}
    
    for style_key, style_data in scores.items():
        sname = style_names.get(style_key, style_key)
        total = style_data.get("total", 0)
        breakdown = style_data.get("breakdown", {})
        
        items = {}
        for sub_key, sub_score in breakdown.items():
            item_name = sub_item_names.get(sub_key, sub_key)
            items[sub_key] = {"name": item_name, "score": sub_score}
        
        style_entry = {"score": total, "items": items}
        
        # 加入 modifiers（將 v4.2 指標轉為中文說明）
        modifiers = style_data.get("modifiers", {})
        if modifiers:
            readable = {}
            # cagr_1_5y
            cagr = modifiers.get("cagr_1_5y")
            if cagr is not None:
                readable["1.5年營收CAGR"] = f"{cagr}%（正值=成長，負值=衰退）"
            else:
                readable["1.5年營收CAGR"] = "資料不足（系統已歸為Normal 60分）"
            
            # revenue_ma_cross
            cross_signal = modifiers.get("revenue_ma_cross", "neutral")
            cross_map = {"bullish": "黃金交叉（3MA>6MA且向上），動能加分",
                        "bearish": "死亡交叉（3MA<6MA），動能扣分",
                        "neutral": "中性，無明顯方向"}
            readable["營收MA交叉"] = cross_map.get(cross_signal, cross_signal)
            
            # operating_margin_quality（只出現在短線/波段）
            om = modifiers.get("operating_margin_quality", {})
            if om and isinstance(om, dict):
                if om.get("triggered"):
                    readable["流血去庫存質檢"] = (
                        f"⚠️ 已觸發！最新營益率 {om.get('current_om','?')}%，"
                        f"較前期下滑 {om.get('drop_pp','?')}pp，短線/波段已打8折"
                    )
                else:
                    readable["流血去庫存質檢"] = "正常（營益率無異常下滑）"
            
            # industry_debt_bias（只出現在價值/定存）
            ib = modifiers.get("industry_debt_bias", {})
            if ib and isinstance(ib, dict):
                if ib.get("penalty_applied"):
                    readable["產業負債偏誤"] = f"⚠️ {ib.get('reason','已打85折')}"
                else:
                    readable["產業負債偏誤"] = ib.get("reason", "正常")
            
            # data_quality（只出現在價值/定存）
            dq = modifiers.get("data_quality", {})
            if dq and isinstance(dq, dict):
                readable["資料品質"] = f"{dq.get('data_years','?')}年，調整係數{dq.get('modifier','1.0')}"
            
            style_entry["modifiers_readable"] = readable
        
        evidence[sname] = style_entry
    
    # Advisor 建議
    evidence["advisor"] = {
        "advice": advice.get("advice", "持有"),
        "best_style": style_names.get(advice.get("best_style", ""), advice.get("best_style", "")),
        "best_score": advice.get("best_score", 0),
    }
    
    return evidence


# ============================================================
# User Message 建構
# ============================================================

def build_user_message(
    stock_id: str,
    stock_name: str,
    scores: dict,
    advice: dict,
    has_position: bool = False,
    avg_price: float = 0.0,
    shares: int = 0,
) -> str:
    """
    建構使用者訊息（含 v4.2 新指標，皆以中文解釋呈現）
    """
    msg = f"請解說股票 {stock_id} {stock_name}\n\n"
    
    msg += "【評分證據】\n"
    msg += "以下是系統已計算完成的評分結果，請依據這些分數進行解說：\n\n"
    
    style_names = {"short_term": "短線", "swing": "波段", "value": "價值", "dividend": "定存"}
    
    for style_key, style_data in scores.items():
        sname = style_names.get(style_key, style_key)
        total = style_data.get("total", 0)
        breakdown = style_data.get("breakdown", {})
        modifiers = style_data.get("modifiers", {})
        
        msg += f"■ {sname}：{total} 分\n"
        
        # 子項明細
        for sub_key, sub_score in breakdown.items():
            msg += f"  ├ {sub_key}: {sub_score} 分\n"
        
        # v4.2 新指標
        cagr = modifiers.get("cagr_1_5y")
        if cagr is not None:
            msg += f"  └ 1.5年營收CAGR: {cagr}%\n"
        
        cross = modifiers.get("revenue_ma_cross")
        if cross:
            cross_cn = {"bullish": "黃金交叉📈", "bearish": "死亡交叉📉", "neutral": "中性➖"}
            msg += f"  └ 營收MA交叉(3MAvs6MA): {cross_cn.get(cross, cross)}\n"
        
        # 流血質檢
        om = modifiers.get("operating_margin_quality", {})
        if om and isinstance(om, dict):
            if om.get("triggered"):
                msg += f"  └ ⚠️ 流血去庫存質檢：觸發！營益率{om.get('current_om','?')}%，下滑{om.get('drop_pp','?')}pp\n"
        
        # 產業偏誤
        ib = modifiers.get("industry_debt_bias", {})
        if ib and isinstance(ib, dict):
            if ib.get("penalty_applied"):
                msg += f"  └ ⚠️ {ib.get('reason','產業偏誤懲罰')}\n"
            else:
                msg += f"  └ {ib.get('reason','產業負債正常')}\n"
        
        msg += "\n"
    
    # Advisor 建議
    msg += "【系統建議】\n"
    msg += f"- 建議: {advice.get('advice', 'N/A')}\n"
    msg += f"- 最適合風格: {style_names.get(advice.get('best_style', ''), advice.get('best_style', 'N/A'))}\n"
    msg += f"- 最高分: {advice.get('best_score', 0)}\n\n"
    
    # 持股資訊
    if has_position and avg_price > 0 and shares > 0:
        msg += "【持股資訊】\n"
        msg += f"- 持有股數: {shares} 股\n"
        msg += f"- 平均成本: {avg_price} 元\n"
        msg += "(僅供參考，不影響評分解說)\n"
    
    return msg


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


if __name__ == "__main__":
    print("prompts.py v4.2 - 整合 v4.2 新指標解說")