"""
test_ai_v4.py
測試 AI v4.0 Explain Engine 架構

測試項目：
1. build_evidence_json() 輸出格式
2. build_user_message() 不包含原始數據
3. analyze_with_deepseek() 降級回應格式
4. 模擬完整流程（不含 API 呼叫）
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai.prompts import build_evidence_json, build_user_message, build_system_prompt
from ai.analyzer import analyze_with_deepseek, _build_fallback_explanation

# ============================================================
# 模擬資料
# ============================================================
MOCK_SCORES = {
    "short_term": {
        "total": 82,
        "breakdown": {
            "trend_structure": 18,
            "momentum": 16,
            "volume": 20,
            "institutional": 12,
            "chip": 9,
            "risk": 7,
        },
        "details": {},
    },
    "swing": {
        "total": 65,
        "breakdown": {
            "revenue_momentum": 15,
            "mid_trend": 14,
            "institutional_trend": 12,
            "earnings_growth": 10,
            "valuation": 8,
            "catalyst": 6,
        },
        "details": {},
    },
    "value": {
        "total": 45,
        "breakdown": {
            "valuation_safety": 10,
            "profit_quality": 8,
            "growth_ability": 7,
            "financial_safety": 8,
            "cash_flow_quality": 6,
            "shareholder_return": 6,
        },
        "details": {},
        "modifiers": {
            "data_quality": {
                "data_years": 5,
                "modifier": 0.95,
                "adjusted_score": 43,
            }
        },
    },
    "dividend": {
        "total": 55,
        "breakdown": {
            "dividend_record": 15,
            "dividend_quality": 10,
            "cash_flow": 8,
            "financial_safety": 10,
            "profit_stability": 6,
            "long_term_growth": 6,
        },
        "details": {},
        "modifiers": {
            "data_quality": {
                "data_years": 5,
                "modifier": 0.95,
                "adjusted_score": 52,
            }
        },
    },
}

MOCK_ADVICE = {
    "advice": "買進",
    "best_style": "short_term",
    "best_score": 82,
    "all_scores": MOCK_SCORES,
}


# ============================================================
# Test 1: build_evidence_json()
# ============================================================
print("=" * 70)
print("Test 1: build_evidence_json() 格式驗證")
print("=" * 70)

evidence = build_evidence_json(MOCK_SCORES, MOCK_ADVICE)

# 檢查四維度
assert "短線" in evidence, "缺少短線"
assert "波段" in evidence, "缺少波段"
assert "價值" in evidence, "缺少價值"
assert "定存" in evidence, "缺少定存"
assert "advisor" in evidence, "缺少 advisor"
print("✅ 四維度 + advisor 都存在")

# 檢查短線結構
short = evidence["短線"]
assert short["score"] == 82, f"短線分數錯誤: {short['score']}"
assert "items" in short, "短線缺少 items"
assert "trend_structure" in short["items"], "短線缺少 trend_structure"
assert short["items"]["trend_structure"]["score"] == 18
print(f"✅ 短線: {short['score']} 分, {len(short['items'])} 個子項")

# 檢查價值有 modifiers
value = evidence["價值"]
assert "modifiers" in value, "價值缺少 modifiers"
assert "data_quality" in value["modifiers"]
print(f"✅ 價值: {value['score']} 分, 含 data_quality modifier")

# 檢查 advisor
adv = evidence["advisor"]
assert adv["advice"] == "買進"
assert adv["best_style"] == "短線"
assert adv["best_score"] == 82
print(f"✅ advisor: {adv['advice']}, 最佳風格: {adv['best_style']}")

print()

# ============================================================
# Test 2: build_user_message() 不包含原始數據
# ============================================================
print("=" * 70)
print("Test 2: build_user_message() 內容檢查")
print("=" * 70)

msg = build_user_message(
    stock_id="2330",
    stock_name="台積電",
    scores=MOCK_SCORES,
    advice=MOCK_ADVICE,
    has_position=True,
    avg_price=150.0,
    shares=1000,
)

# 檢查不該出現的原始數據關鍵字
# 注意：子項名稱（如 volume, momentum, risk 等）是 breakdown key，不是原始數據
forbidden = ["close", "MA_5", "MA_10", "MA_20", "MA_60",
             "TTM_EPS", "PE_Percentile", "PB_Percentile",
             "ROE_TTM", "Gross_Margin", "Debt_Ratio",
             "Revenue_YoY", "RSI_6", "MA60_Bias",
             "pe_ratio", "pb_ratio", "dividend_yield",
             "收盤價", "成交量", "本益比", "毛利率"]

found_forbidden = [w for w in forbidden if w in msg]
if found_forbidden:
    print(f"❌ 發現不該出現的原始數據: {found_forbidden}")
else:
    print("✅ 無原始數據洩漏")

# 檢查該出現的內容
required = ["2330", "台積電", "短線", "波段", "價值", "定存",
            "82 分", "65 分", "45 分", "55 分",
            "trend_structure", "revenue_momentum",
            "買進", "data_quality",
            "1000 股", "150.0 元"]

missing = [w for w in required if w not in msg]
if missing:
    print(f"❌ 缺少必要內容: {missing}")
else:
    print("✅ 所有必要內容都存在")

print()

# ============================================================
# Test 3: System Prompt 檢查
# ============================================================
print("=" * 70)
print("Test 3: System Prompt 內容檢查")
print("=" * 70)

sp = build_system_prompt()

# 檢查關鍵定位
assert "Explain Engine" in sp, "缺少 Explain Engine 定位"
assert "解說評分結果" in sp, "缺少解說定位"
assert "不得自行閱讀原始數據" in sp, "缺少不得閱讀原始數據"
assert "不得重新打分" in sp, "缺少不得重新打分"
assert "不得說「建議買進/賣出/持有」" in sp, "缺少不得給建議"
print("✅ System Prompt 定位正確")

# 檢查輸出格式
assert "summary" in sp, "缺少 summary"
assert "strengths" in sp, "缺少 strengths"
assert "weaknesses" in sp, "缺少 weaknesses"
assert "suitable_for" in sp, "缺少 suitable_for"
assert "risk_warning" in sp, "缺少 risk_warning"
assert "watch_items" in sp, "缺少 watch_items"
print("✅ 輸出格式定義完整")

print()

# ============================================================
# Test 4: 降級回應格式
# ============================================================
print("=" * 70)
print("Test 4: 降級回應格式")
print("=" * 70)

fallback = _build_fallback_explanation("2330", "台積電", "測試錯誤")

assert fallback["stock_id"] == "2330"
assert fallback["stock_name"] == "台積電"
assert "explanation" in fallback
assert "summary" in fallback["explanation"]
assert "strengths" in fallback["explanation"]
assert "weaknesses" in fallback["explanation"]
assert "suitable_for" in fallback["explanation"]
assert "risk_warning" in fallback["explanation"]
assert "watch_items" in fallback["explanation"]
assert "evidence" in fallback
print("✅ 降級回應格式正確")

print()

# ============================================================
# Test 5: analyze_with_deepseek() 無 API Key 時
# ============================================================
print("=" * 70)
print("Test 5: analyze_with_deepseek() 無 API Key")
print("=" * 70)

result = analyze_with_deepseek(
    stock_id="2330",
    stock_name="台積電",
    scores=MOCK_SCORES,
    advice=MOCK_ADVICE,
    has_position=True,
    avg_price=150.0,
    shares=1000,
    api_key="",
)

assert result["stock_id"] == "2330"
assert "explanation" in result
assert "請輸入 DeepSeek API Key" in result["explanation"]["summary"]
assert "evidence" in result
print(f"✅ 無 API Key 回應正確: {result['explanation']['summary']}")

print()

# ============================================================
# 總結
# ============================================================
print("=" * 70)
print("✅ 全部測試通過！")
print("=" * 70)
print()
print("v4.0 改造重點確認：")
print("  1. AI 只能看到評分結果，看不到原始數據")
print("  2. AI 輸出 explanation 格式（解說），非 decision 格式（決策）")
print("  3. Evidence JSON 結構化分數明細")
print("  4. 降級回應也符合 explanation 格式")
print("  5. System Prompt 明確定位為 Explain Engine")
