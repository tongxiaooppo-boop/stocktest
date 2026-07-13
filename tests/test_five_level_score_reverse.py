"""
測試 five_level_score() 反向評分（reverse=True）的迴歸 bug 修正

驗證案例：
1. pe_percentile = 93.2（本益比貴到市場前 6.8%，估值極差）
   thresholds: excellent=20, good=40, normal=60, weak=80（無 poor）
   修正前回傳 30 分 ← 錯誤
   正確結果應為 0 分（沒有任何門檻能匹配，應視為最差）

2. debt_ratio = 99（負債比 99%，財務體質極差）
   thresholds: excellent=30, good=45, normal=60, weak=75（無 poor）
   修正前回傳 30 分 ← 錯誤
   正確結果應為 0 分
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.scorer import five_level_score


def test_reverse_pe_percentile_extreme():
    """pe_percentile=93.2 超過所有門檻，應回傳 0 分"""
    result = five_level_score(93.2, {
        "_excellent": 20,
        "_good": 40,
        "_normal": 60,
        "_weak": 80,
    }, reverse=True)
    assert result == 0, f"[FAIL] pe_percentile=93.2 should be 0, got {result}"
    print(f"[PASS] pe_percentile=93.2 -> {result}")


def test_reverse_debt_ratio_extreme():
    """debt_ratio=99 超過所有門檻，應回傳 0 分"""
    result = five_level_score(99, {
        "_excellent": 30,
        "_good": 45,
        "_normal": 60,
        "_weak": 75,
    }, reverse=True)
    assert result == 0, f"[FAIL] debt_ratio=99 should be 0, got {result}"
    print(f"[PASS] debt_ratio=99 -> {result}")


def test_reverse_normal_case():
    """正常情況：pe_percentile=15 應得 100 分（excellent）"""
    result = five_level_score(15, {
        "_excellent": 20,
        "_good": 40,
        "_normal": 60,
        "_weak": 80,
    }, reverse=True)
    assert result == 100, f"[FAIL] pe_percentile=15 should be 100, got {result}"
    print(f"[PASS] pe_percentile=15 -> {result}")


def test_reverse_with_poor():
    """有定義 _poor 的情況：debt_ratio=85 應得 0 分（poor）"""
    result = five_level_score(85, {
        "_excellent": 30,
        "_good": 45,
        "_normal": 60,
        "_weak": 75,
        "_poor": 90,
    }, reverse=True)
    assert result == 0, f"[FAIL] debt_ratio=85 should be 0 (poor), got {result}"
    print(f"[PASS] debt_ratio=85 (with poor threshold) -> {result}")


def test_reverse_weak_case():
    """pe_percentile=70 應得 30 分（weak）"""
    result = five_level_score(70, {
        "_excellent": 20,
        "_good": 40,
        "_normal": 60,
        "_weak": 80,
    }, reverse=True)
    assert result == 30, f"[FAIL] pe_percentile=70 should be 30, got {result}"
    print(f"[PASS] pe_percentile=70 -> {result}")


if __name__ == "__main__":
    print("=" * 60)
    print("測試 five_level_score() 反向評分修正")
    print("=" * 60)
    
    test_reverse_pe_percentile_extreme()
    test_reverse_debt_ratio_extreme()
    test_reverse_normal_case()
    test_reverse_with_poor()
    test_reverse_weak_case()
    
    print("=" * 60)
    print("[ALL PASS] All tests passed!")
