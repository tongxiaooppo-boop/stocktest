"""
core/scorer.py
四種風格打分 — 五級評分制 + 回測功能
"""

import pandas as pd
import numpy as np
from stock.metrics import ols_slope, cagr, cv as compute_cv
from core.scoring_config import (
    SHORT_TERM_WEIGHTS, SHORT_TERM_THRESHOLDS,
    SHORT_TERM_BUY_WEIGHTS, SHORT_TERM_SELL_WEIGHTS,
    SWING_WEIGHTS, SWING_THRESHOLDS,
    SWING_BUY_WEIGHTS, SWING_SELL_WEIGHTS,
    VALUE_WEIGHTS, VALUE_THRESHOLDS,
    DIVIDEND_WEIGHTS, DIVIDEND_THRESHOLDS,
    DATA_QUALITY_MODIFIER,
    RISK_PENALTY, RISK_BONUS,
    REVENUE_MA_CROSS,
    OPERATING_MARGIN_QUALITY,
    INDUSTRY_DEBT_BIAS,
    FINANCE_SECTORS, FINANCE_STOCK_IDS,
    RSI_OVERHEAT_THRESHOLD, RSI_OVERHEAT_PENALTY,
)

def is_finance(row: dict) -> bool:
    """判斷 row 是否為金融業（依產業名或股票代碼）"""
    industry = row.get("Industry", None)
    if industry is None:
        industry = row.get("industry_category", None)
    if isinstance(industry, str) and industry in FINANCE_SECTORS:
        return True
    stock_id = row.get("stock_id", None)
    if stock_id is not None and not pd.isna(stock_id):
        if isinstance(stock_id, (int, float)):
            stock_id_str = str(int(float(stock_id)))
        else:
            stock_id_str = str(stock_id).strip()
        if stock_id_str in FINANCE_STOCK_IDS:
            return True
        if stock_id_str.startswith("28") and len(stock_id_str) == 4:
            return True
    return False


# ============================================================
# 通用輔助函式
# ============================================================

def five_level_score(value, thresholds, reverse=False):
    """
    五級評分通用函式（v2.0 平滑映射：100/85/70/50/0）
    
    Parameters:
        value: 實際數值
        thresholds: dict 包含 _excellent, _good, _normal, _weak, _poor 門檻
                     所有 key 皆為可選（若缺少則跳過該級別）
        reverse: True 表示數值越低越好（反向評分）
    
    Returns:
        int: 100, 85, 70, 50, 0
    """
    if pd.isna(value):
        return 0
    
    has_excellent = "_excellent" in thresholds
    has_good = "_good" in thresholds
    has_normal = "_normal" in thresholds
    has_weak = "_weak" in thresholds
    has_poor = "_poor" in thresholds
    
    if reverse:
        # 反向評分：數值越低越好
        # 注意：必須從最嚴格（_excellent）開始檢查，確保不會穿透
        if has_excellent and value <= thresholds["_excellent"]:
            return 100
        if has_good and value <= thresholds["_good"]:
            return 85
        if has_normal and value <= thresholds["_normal"]:
            return 70
        if has_weak and value <= thresholds["_weak"]:
            return 50
        if has_poor and value <= thresholds["_poor"]:
            return 0
        # 若數值大於所有已定義門檻（例如 pe_percentile=93.2 超過 weak=80），一律視為最差
        return 0
    else:
        # 正向評分：數值越高越好
        if has_excellent and value >= thresholds["_excellent"]:
            return 100
        elif has_good and value >= thresholds["_good"]:
            return 85
        elif has_normal and value >= thresholds["_normal"]:
            return 70
        elif has_weak and value >= thresholds["_weak"]:
            return 50
        elif has_poor and value >= thresholds["_poor"]:
            return 0
        else:
            return 0


def apply_weight(score, weight):
    """將分數乘以權重，回傳加權後的分數"""
    return score * weight


def get_data_quality_modifier(data_years):
    """根據資料年數取得調整係數"""
    if pd.isna(data_years):
        return 1.00
    data_years = int(data_years)
    if data_years >= DATA_QUALITY_MODIFIER["excellent"]["min_years"]:
        return DATA_QUALITY_MODIFIER["excellent"]["modifier"]
    elif data_years >= DATA_QUALITY_MODIFIER["good"]["min_years"]:
        return DATA_QUALITY_MODIFIER["good"]["modifier"]
    elif data_years >= DATA_QUALITY_MODIFIER["normal"]["min_years"]:
        return DATA_QUALITY_MODIFIER["normal"]["modifier"]
    else:
        return DATA_QUALITY_MODIFIER["poor"]["modifier"]


def apply_all_modifiers(base_score: int, row: dict, style: str,
                         dq_modifier: float = 1.0,
                         industry_bias_adjust: int = None) -> int:
    """
    v2.1 統一 Modifier 疊加邏輯。
    
    計算順序：
      最終分數 = (base_score × DQ_Modifier) - Risk_Penalty + Risk_Bonus
      若有 Industry_Debt_Bias，則在 Risk 之後再套用
    
    最後用 np.clip 確保 [0, 100]。
    """
    score = base_score
    
    # 1. Data Quality Modifier（乘）
    score = int(round(score * dq_modifier))
    
    # 2. Industry Debt Bias（若有，另乘）
    if industry_bias_adjust is not None:
        score = industry_bias_adjust
    
    # 3. Risk Modifier（僅含非 RSI 風險因子）
    _fin = is_finance(row)
    penalty = 0
    bonus = 0
    
    # Penalty
    debt = row.get("Debt_Ratio", None)
    if pd.notna(debt) and not _fin and debt > RISK_PENALTY["debt_too_high"]["threshold"]:
        penalty += RISK_PENALTY["debt_too_high"]["penalty"]
    ttm_eps = row.get("TTM_EPS", None)
    if pd.notna(ttm_eps) and ttm_eps < 0:
        penalty += RISK_PENALTY["eps_negative"]["penalty"]
    ttm_ocf = row.get("TTM_OCF", None)
    payout = row.get("Payout_Ratio", None)
    if not _fin and pd.notna(ttm_ocf) and pd.notna(payout) and ttm_ocf < 0 and payout > 100:
        penalty += RISK_PENALTY["payout_unsustainable"]["penalty"]
    
    # Bonus
    rsi = row.get("RSI_6", None)
    if pd.notna(rsi) and rsi < RISK_BONUS["rsi_oversold"]["threshold"]:
        bonus += RISK_BONUS["rsi_oversold"]["bonus"]
    if pd.notna(debt) and not _fin and debt < RISK_BONUS["low_debt"]["threshold"]:
        bonus += RISK_BONUS["low_debt"]["bonus"]
    
    score = score - abs(penalty) + bonus
    return int(np.clip(score, 0, 100))


# ============================================================
# 短線評分
# ============================================================

def score_trend_structure(row) -> dict:
    """趨勢結構評分（權重20%）"""
    t = SHORT_TERM_THRESHOLDS
    
    # 均線排列
    ma_alignment = row.get("MA_Alignment", 0)
    ma_score = five_level_score(ma_alignment, {
        "_excellent": t["ma_alignment_excellent"],
        "_good": t["ma_alignment_good"],
        "_normal": t["ma_alignment_normal"],
        "_weak": t["ma_alignment_weak"],
    })
    
    # 站上均線數量
    above_count = 0
    for ma in ["MA_5", "MA_10", "MA_20", "MA_60"]:
        close = row.get("close", 0)
        ma_val = row.get(ma, 0)
        if pd.notna(close) and pd.notna(ma_val) and close > ma_val:
            above_count += 1
    above_score = five_level_score(above_count, {
        "_excellent": t["above_ma_excellent"],
        "_good": t["above_ma_good"],
        "_normal": t["above_ma_normal"],
        "_weak": t["above_ma_weak"],
    })
    
    # 綜合評分（均線排列權重60%，站上均線權重40%）
    composite = ma_score * 0.6 + above_score * 0.4
    
    return {
        "score": int(round(composite)),
        "details": {
            "ma_alignment": int(ma_alignment) if pd.notna(ma_alignment) else 0,
            "ma_alignment_score": ma_score,
            "above_ma_count": above_count,
            "above_ma_score": above_score,
        }
    }


def score_momentum(row, rsi_limit: int = 88) -> dict:
    """
    動能強度評分（權重20%）
    
    Phase 2 重構：以 RSI(6) + 距離高點比例 Dist_High_5D 雙條件，
    套用新五級分 [100, 85, 70, 50, 0]。
    
    RSI 過熱門檻由 rsi_limit 動態控制（均線護航機制）：
    - MA_Alignment >= 3（完全多頭排列）：rsi_limit = 95
    - 否則：rsi_limit = 88
    
    100分: RSI(6) ∈ [65, 80] 且 距離高點 ≤ 1.5%
    85分:  RSI(6) ∈ [50, 65) 且 MACD柱 > 0
    70分:  RSI(6) ∈ [50, 80) (中性偏強)
    50分:  RSI(6) < 50 且 距離高點 > 5% (超賣)
    0分:   跌破前5日最低點 或 RSI ≥ rsi_limit (過熱)
    """
    rsi = row.get("RSI_6", None)
    close = row.get("close", None)
    high_5d = row.get("High_5D", None)
    low_5d = row.get("Low_5D", None)
    macd_hist = row.get("MACD_HIST", None)  # MACD 柱狀體
    
    # NaN 防禦
    if pd.isna(rsi) or pd.isna(close):
        return {
            "score": 0,
            "details": {"rsi": None, "note": "RSI 或 close 資料不足"}
        }
    
    # 距離高點比例 Dist_High_5D = (close - max(high[-5:])) / close
    dist_high = None
    if pd.notna(close) and abs(close) > 1e-10 and pd.notna(high_5d) and high_5d > 0:
        dist_high = (close - high_5d) / close * 100  # 百分比
    
    # 跌破前5日最低點
    break_low = pd.notna(low_5d) and close < low_5d
    
    # MACD 柱 > 0
    macd_positive = pd.notna(macd_hist) and macd_hist > 0
    
    # 核心評分
    if break_low or rsi >= rsi_limit:
        score = 0
    elif 65 <= rsi <= 80 and pd.notna(dist_high) and dist_high >= -1.5:
        score = 100
    elif 50 <= rsi < 65 and macd_positive:
        score = 85
    elif 50 <= rsi < 80:
        score = 70
    elif rsi < 50 and pd.notna(dist_high) and dist_high < -5:
        score = 50  # 超賣
    else:
        score = 50  # 偏弱但未破底
    
    return {
        "score": score,
        "details": {
            "rsi": round(rsi, 1),
            "dist_high_5d": round(dist_high, 2) if pd.notna(dist_high) else None,
            "break_low_5d": break_low,
            "macd_positive": macd_positive,
            "note": "Phase 2: RSI(6) + Dist_High_5D 雙條件評分"
        }
    }


def score_volume_structure(row) -> dict:
    """成交量結構評分（權重20%）"""
    t = SHORT_TERM_THRESHOLDS
    
    # Volume Ratio
    vol_ratio = row.get("Volume_Ratio", 0)
    vol_score = five_level_score(vol_ratio, {
        "_excellent": t["volume_ratio_excellent"],
        "_good": t["volume_ratio_good"],
        "_normal": t["volume_ratio_normal"],
        "_weak": t["volume_ratio_weak"],
    })
    
    # 5日均量趨勢
    volume = row.get("volume", 0)
    vol_ma5 = row.get("Vol_MA_5", 0)
    if pd.notna(volume) and pd.notna(vol_ma5) and vol_ma5 > 0:
        vol_trend_ratio = volume / vol_ma5
        surge_score = five_level_score(vol_trend_ratio, {
            "_excellent": t["volume_surge_excellent"],
            "_good": t["volume_surge_good"],
            "_normal": t["volume_surge_normal"],
            "_weak": t["volume_surge_weak"],
            "_poor": t["volume_surge_poor"],
        })
    else:
        surge_score = 0
    
    # 綜合評分（Volume Ratio 60%, 爆量 40%）
    composite = vol_score * 0.60 + surge_score * 0.40
    
    return {
        "score": int(round(composite)),
        "details": {
            "volume_ratio": round(vol_ratio, 2) if pd.notna(vol_ratio) else None,
            "volume_ratio_score": vol_score,
            "surge_score": surge_score,
        }
    }


def score_institutional(row) -> dict:
    """法人籌碼評分（權重15%）"""
    t = SHORT_TERM_THRESHOLDS
    
    # 5日法人
    inst_5d = row.get("Inst_5D_Net", 0)
    inst_5d_score = five_level_score(inst_5d, {
        "_excellent": t["inst_5d_excellent"],
        "_good": t["inst_5d_good"],
        "_normal": t["inst_5d_normal"],
        "_weak": t["inst_5d_weak"],
    })
    
    # 20日法人代理（因無 Inst_10D_Net，用 Inst_20D_Net + 專用門檻）
    # v2.1 校準：使用獨立的 inst_20d_surrogate_* 門檻，不與 10 日門檻共用
    inst_20d = row.get("Inst_20D_Net", 0)
    inst_20d_score = five_level_score(inst_20d, {
        "_excellent": t["inst_20d_surrogate_excellent"],
        "_good": t["inst_20d_surrogate_good"],
        "_normal": t["inst_20d_surrogate_normal"],
        "_weak": t["inst_20d_surrogate_weak"],
    })
    
    # 外資
    foreign_net = row.get("Foreign_Net", 0)
    foreign_score = five_level_score(foreign_net, {
        "_excellent": t["foreign_excellent"],
        "_good": t["foreign_good"],
        "_normal": t["foreign_normal"],
        "_weak": t["foreign_weak"],
    })
    
    # 投信
    trust_net = row.get("Trust_Net", 0)
    trust_score = five_level_score(trust_net, {
        "_excellent": t["trust_excellent"],
        "_good": t["trust_good"],
        "_normal": t["trust_normal"],
        "_weak": t["trust_weak"],
    })
    
    # 綜合評分（5日法人 35%, 20日代理 25%, 外資 25%, 投信 15%）
    composite = inst_5d_score * 0.35 + inst_20d_score * 0.25 + foreign_score * 0.25 + trust_score * 0.15
    
    return {
        "score": int(round(composite)),
        "details": {
            "inst_5d_net": int(inst_5d) if pd.notna(inst_5d) else 0,
            "inst_5d_score": inst_5d_score,
            "inst_20d_score": inst_20d_score,
            "inst_20d_is_proxy": True,  # 用 Inst_20D_Net 代理 Inst_10D_Net
            "foreign_score": foreign_score,
            "trust_score": trust_score,
        }
    }


def score_chip_health(row) -> dict:
    """籌碼健康評分（權重15%）"""
    t = SHORT_TERM_THRESHOLDS
    
    # 融資變化（反向評分：融資減少越好）
    margin_change = row.get("Margin_5D_Change", 0)
    margin_score = five_level_score(margin_change, {
        "_excellent": t["margin_change_excellent"],
        "_good": t["margin_change_good"],
        "_normal": t["margin_change_normal"],
        "_weak": t["margin_change_weak"],
    }, reverse=True)
    
    # 融券變化（正向評分：融券增加代表看空力道強）
    short_change = row.get("Short_5D_Change", 0)
    short_score = five_level_score(short_change, {
        "_excellent": t["short_change_excellent"],
        "_good": t["short_change_good"],
        "_normal": t["short_change_normal"],
        "_weak": t["short_change_weak"],
    })
    
    # 借券變化（反向評分：借券減少越好）
    sbl = row.get("SBL_5D_Change", 0)
    sbl_score = five_level_score(sbl, {
        "_excellent": t["sbl_excellent"],
        "_good": t["sbl_good"],
        "_normal": t["sbl_normal"],
        "_weak": t["sbl_weak"],
    }, reverse=True)
    
    # 綜合評分（融資 40%, 融券 30%, 借券 30%）
    composite = margin_score * 0.40 + short_score * 0.30 + sbl_score * 0.30
    
    return {
        "score": int(round(composite)),
        "details": {
            "margin_5d_change": int(margin_change) if pd.notna(margin_change) else 0,
            "margin_score": margin_score,
            "short_5d_change": int(short_change) if pd.notna(short_change) else 0,
            "short_score": short_score,
            "sbl_score": sbl_score,
        }
    }


def score_volatility_risk(row, rsi_limit: int = 88) -> dict:
    """
    波動風險評分（權重10%）— 反向評分：波動越低越好
    
    Phase 2 重構：使用 Bias_5D + RSI(6) 過熱判定，
    套用新五級分 [100, 85, 70, 50, 0]。
    
    RSI 過熱門檻由 rsi_limit 動態控制（均線護航機制）：
    - MA_Alignment >= 3（完全多頭排列）：rsi_limit = 95
    - 否則：rsi_limit = 88
    
    100分: Bias_5D ∈ [-2%, 2%] 且 RSI(6) ≤ 80 (低波動安全)
    85分:  Bias_5D ∈ [-5%, 5%]  (乖離適中)
    70分:  Bias_5D > 10%         (短線乖離過大)
    50分:  無過熱但乖離略大
    0分:   RSI(6) > rsi_limit    (觸發過熱扣分)
    """
    bias_5d = row.get("Bias_5D", None)  # 5日乖離率
    rsi = row.get("RSI_6", None)
    
    # NaN 防禦
    if pd.isna(bias_5d):
        bias_5d = row.get("MA60_Bias", None)  # fallback to MA60_Bias
    
    if pd.isna(rsi):
        return {
            "score": 0,
            "details": {"note": "RSI 資料不足"}
        }
    
    # 核心評分：Bias_5D + RSI 過熱
    bias_abs = abs(bias_5d) if pd.notna(bias_5d) else 999
    
    # RSI 過熱：直接 0 分（使用動態 rsi_limit）
    if rsi > rsi_limit:
        score = 0
    elif pd.notna(bias_5d) and bias_abs <= 0.02 and rsi <= 80:
        score = 100
    elif pd.notna(bias_5d) and bias_abs <= 0.05:
        score = 85
    elif pd.notna(bias_5d) and bias_abs > 0.10:
        score = 70  # 乖離過大風險
    elif rsi <= rsi_limit:
        score = 50  # 無過熱但乖離略大
    else:
        score = 50
    
    return {
        "score": score,
        "details": {
            "bias_5d": round(bias_5d, 4) if pd.notna(bias_5d) else None,
            "rsi": round(rsi, 1) if pd.notna(rsi) else None,
            "note": "Phase 2: Bias_5D + RSI(6) 過熱判定評分"
        }
    }


def score_short_term(row) -> dict:
    """
    計算短線總分與子項明細（雙軌制）
    
    買入權重：SHORT_TERM_BUY_WEIGHTS（動能/量能權重較高）
    賣出權重：SHORT_TERM_SELL_WEIGHTS（趨勢/風險權重較高）
    
    RSI 過熱門檻由均線護航機制動態控制：
    - MA_Alignment >= 3（完全多頭排列）：rsi_limit = 95
    - 否則：rsi_limit = 88
    """
    # A. 動態計算 RSI 過熱門檻
    ma_alignment = row.get("MA_Alignment", 0)
    rsi_limit = 95 if pd.notna(ma_alignment) and ma_alignment >= 3 else 88
    
    # B. 計算 6 個子項（傳入 rsi_limit）
    trend = score_trend_structure(row)
    momentum = score_momentum(row, rsi_limit)
    volume = score_volume_structure(row)
    inst = score_institutional(row)
    chip = score_chip_health(row)
    risk = score_volatility_risk(row, rsi_limit)
    
    sub_scores = {
        "trend_structure": trend["score"],
        "momentum": momentum["score"],
        "volume": volume["score"],
        "institutional": inst["score"],
        "chip": chip["score"],
        "risk": risk["score"],
    }
    
    # C. 雙軌加權計算
    buy_total = (
        sub_scores["trend_structure"] * SHORT_TERM_BUY_WEIGHTS["trend_structure"] +
        sub_scores["momentum"] * SHORT_TERM_BUY_WEIGHTS["momentum"] +
        sub_scores["volume"] * SHORT_TERM_BUY_WEIGHTS["volume"] +
        sub_scores["institutional"] * SHORT_TERM_BUY_WEIGHTS["institutional"] +
        sub_scores["chip"] * SHORT_TERM_BUY_WEIGHTS["chip"] +
        sub_scores["risk"] * SHORT_TERM_BUY_WEIGHTS["risk"]
    )
    sell_total = (
        sub_scores["trend_structure"] * SHORT_TERM_SELL_WEIGHTS["trend_structure"] +
        sub_scores["momentum"] * SHORT_TERM_SELL_WEIGHTS["momentum"] +
        sub_scores["volume"] * SHORT_TERM_SELL_WEIGHTS["volume"] +
        sub_scores["institutional"] * SHORT_TERM_SELL_WEIGHTS["institutional"] +
        sub_scores["chip"] * SHORT_TERM_SELL_WEIGHTS["chip"] +
        sub_scores["risk"] * SHORT_TERM_SELL_WEIGHTS["risk"]
    )
    
    return {
        "total_buy": int(round(buy_total)),
        "total_sell": int(round(sell_total)),
        "breakdown": sub_scores,
        "details": {
            "trend_structure": trend["details"],
            "momentum": momentum["details"],
            "volume": volume["details"],
            "institutional": inst["details"],
            "chip": chip["details"],
            "risk": risk["details"],
        }
    }


# ============================================================
# 波段評分
# ============================================================

def score_revenue_momentum(row, cagr_1_5y=None) -> dict:
    """營收動能評分（權重25%）
    
    v4.2：加入 1.5Y-CAGR 作為評分基礎之一。
    若 cagr_1_5y 有值，則權重重新分配：
    YoY 35%, MoM 15%, 加速度 15%, 1.5Y-CAGR 35%
    """
    t = SWING_THRESHOLDS
    
    # Revenue YoY
    rev_yoy = row.get("Revenue_YoY", 0)
    yoy_score = five_level_score(rev_yoy, {
        "_excellent": t["rev_yoy_excellent"],
        "_good": t["rev_yoy_good"],
        "_normal": t["rev_yoy_normal"],
        "_weak": t["rev_yoy_weak"],
    })
    
    # Revenue MoM（簡化：用季增率代替）
    rev_mom = row.get("Revenue_MoM", 0)
    mom_score = five_level_score(rev_mom, {
        "_excellent": t["rev_mom_excellent"],
        "_good": t["rev_mom_good"],
        "_normal": t["rev_mom_normal"],
        "_weak": t["rev_mom_weak"],
    })
    
    # 營收加速度（Revenue_Accelerating 為布林值，採二元評分）
    rev_accel = row.get("Revenue_Accelerating", 0)
    if pd.notna(rev_accel):
        if isinstance(rev_accel, bool):
            rev_accel_val = 1 if rev_accel else 0
        else:
            rev_accel_val = 1 if rev_accel > 0 else 0
        accel_score = five_level_score(rev_accel_val, {
            "_excellent": t["rev_accel_true"],
        })
    else:
        accel_score = 0
    
    # 1.5Y-CAGR 評分（v4.2 新增）
    cagr_score = 70
    cagr_value = None
    if cagr_1_5y is not None and pd.notna(cagr_1_5y):
        cagr_score = five_level_score(cagr_1_5y, {
            "_excellent": t["cagr_1_5y_excellent"],
            "_good": t["cagr_1_5y_good"],
            "_normal": t["cagr_1_5y_normal"],
            "_weak": t["cagr_1_5y_weak"],
            "_poor": t["cagr_1_5y_poor"],
        })
        cagr_value = round(cagr_1_5y, 2)
    
    # v4.2 綜合評分：有 CAGR 時重新分配權重，無則沿用原始
    if cagr_value is not None:
        composite = yoy_score * 0.35 + mom_score * 0.15 + accel_score * 0.15 + cagr_score * 0.35
    else:
        composite = yoy_score * 0.50 + mom_score * 0.25 + accel_score * 0.25
    
    return {
        "score": int(round(composite)),
        "details": {
            "revenue_yoy": round(rev_yoy, 2) if pd.notna(rev_yoy) else None,
            "yoy_score": yoy_score,
            "mom_score": mom_score,
            "accel_score": accel_score,
            "cagr_1_5y": cagr_value,
            "cagr_score": cagr_score if cagr_value is not None else None,
        }
    }


def score_mid_trend(row) -> dict:
    """
    中期趨勢評分（權重20%）
    
    Phase 2 重構：使用 20MA 斜率 + 站上 MA60 判斷，
    套用新五級分 [100, 85, 70, 50, 0]。
    
    100分: MA20_Slope > 0 且 close > MA60 (中期多頭)
    85分:  MA20_Slope > 0 (20MA 向上)
    70分:  close > MA60 (股價在年線之上)
    50分:  close > MA20 (股價在月線之上)
    0分:   close ≤ MA20 (短期偏空)
    """
    close = row.get("close", None)
    ma20 = row.get("MA_20", None)
    ma60 = row.get("MA_60", None)
    ma20_slope = row.get("MA20_Slope", None)  # OLS 斜率，由 processor 計算
    
    # NaN 防禦
    if pd.isna(close):
        return {
            "score": 0,
            "details": {"note": "close 資料不足"}
        }
    
    # 核心評分：MA20 斜率 + 站上均線
    above_ma20 = pd.notna(ma20) and close > ma20
    above_ma60 = pd.notna(ma60) and close > ma60
    ma20_up = pd.notna(ma20_slope) and ma20_slope > 0
    
    if ma20_up and above_ma60:
        score = 100
    elif ma20_up:
        score = 85
    elif above_ma60:
        score = 70
    elif above_ma20:
        score = 50
    else:
        score = 0
    
    return {
        "score": score,
        "details": {
            "above_ma20": above_ma20,
            "above_ma60": above_ma60,
            "ma20_slope": round(ma20_slope, 6) if pd.notna(ma20_slope) else None,
            "note": "Phase 2: MA20_Slope + 站上均線評分"
        }
    }


def score_institutional_trend(row) -> dict:
    """
    籌碼趨勢評分（權重20%）
    
    Phase 2 重構：使用 ols_slope 計算 20 日法人買超斜率，
    套用新五級分 [100, 85, 70, 50, 0]。
    
    100分: Inst_Slope_20D ≥ 50000 (顯著正斜率)
    85分:  Inst_Slope_20D ≥ 0 (正斜率)
    70分:  Inst_20D_Net ≥ 0 (累計買超)
    50分:  Inst_20D_Net < 0 但 Inst_Slope_20D > -50000
    0分:   Inst_20D_Net < 0 且斜率明顯為負
    """
    # 嘗試取得 OLS 斜率（data processor 計算後寫入 row）
    inst_slope = row.get("Inst_Slope_20D", None)
    inst_20d = row.get("Inst_20D_Net", None)
    
    # NaN 防禦
    if pd.isna(inst_20d):
        return {
            "score": 0,
            "details": {"note": "Inst_20D_Net 資料不足"}
        }
    
    # 核心評分：OLS 斜率優先，其次為 20 日累計
    if pd.notna(inst_slope):
        if inst_slope >= 50000:
            score = 100
        elif inst_slope >= 0:
            score = 85
        elif inst_20d >= 0:
            score = 70
        elif inst_slope > -50000:
            score = 50
        else:
            score = 0
    else:
        # 無 OLS 斜率時，用 20 日累計法人買超替代
        if inst_20d >= 10000000:
            score = 100
        elif inst_20d >= 2000000:
            score = 85
        elif inst_20d >= 0:
            score = 70
        elif inst_20d >= -2000000:
            score = 50
        else:
            score = 0
    
    return {
        "score": score,
        "details": {
            "inst_slope_20d": round(inst_slope, 0) if pd.notna(inst_slope) else None,
            "inst_20d_net": int(inst_20d) if pd.notna(inst_20d) else 0,
            "note": "Phase 2: Inst_Slope_20D (OLS斜率) 優先評分"
        }
    }


def score_earnings_growth(row) -> dict:
    """獲利成長評分（權重15%）"""
    t = SWING_THRESHOLDS
    
    # TTM EPS
    ttm_eps = row.get("TTM_EPS", 0)
    ttm_eps_valid = row.get("TTM_EPS_Valid", True)
    if pd.notna(ttm_eps) and ttm_eps_valid:
        eps_score = five_level_score(ttm_eps, {
            "_excellent": t["ttm_eps_excellent"],
            "_good": t["ttm_eps_good"],
            "_normal": t["ttm_eps_normal"],
            "_weak": t["ttm_eps_weak"],
        })
    else:
        eps_score = 0
    
    # EPS YoY（真正的 EPS 年成長率，非營收 YoY 近似）
    eps_yoy = row.get("EPS_YoY", None)
    eps_yoy_reason = row.get("EPS_YoY_Reason", "")
    eps_yoy_available = pd.notna(eps_yoy) and eps_yoy_reason == ""
    
    if eps_yoy_available:
        eps_yoy_score = five_level_score(eps_yoy, {
            "_excellent": t["eps_yoy_excellent"],
            "_good": t["eps_yoy_good"],
            "_normal": t["eps_yoy_normal"],
            "_weak": t["eps_yoy_weak"],
        })
        eps_yoy_note = ""
    else:
        eps_yoy_score = 0
        if eps_yoy_reason == "denominator_invalid":
            eps_yoy_note = "去年同期EPS為負或零，無法計算成長率"
        elif eps_yoy_reason == "insufficient_history":
            eps_yoy_note = "資料不足（無去年同期EPS）"
        else:
            eps_yoy_note = "EPS成長率資料缺失"
    
    # 綜合評分（TTM EPS 60%, EPS YoY 40%）
    composite = eps_score * 0.60 + eps_yoy_score * 0.40
    
    return {
        "score": int(round(composite)),
        "details": {
            "ttm_eps": round(ttm_eps, 2) if pd.notna(ttm_eps) else None,
            "eps_score": eps_score,
            "eps_yoy": round(eps_yoy, 2) if eps_yoy_available else None,
            "eps_yoy_score": eps_yoy_score,
            "eps_yoy_available": eps_yoy_available,
            "eps_yoy_note": eps_yoy_note,
        }
    }


def score_valuation_position(row) -> dict:
    """估值位置評分（權重10%）— 反向評分：百分位越低越好"""
    t = SWING_THRESHOLDS
    
    # PE Percentile
    pe_pct = row.get("PE_Percentile", None)
    if pd.notna(pe_pct):
        pe_score = five_level_score(pe_pct, {
            "_excellent": t["pe_percentile_excellent"],
            "_good": t["pe_percentile_good"],
            "_normal": t["pe_percentile_normal"],
            "_weak": t["pe_percentile_weak"],
        }, reverse=True)
    else:
        pe_score = 70  # 無資料給中間分
    
    # PB Percentile
    pb_pct = row.get("PB_Percentile", None)
    if pd.notna(pb_pct):
        pb_score = five_level_score(pb_pct, {
            "_excellent": t["pb_percentile_excellent"],
            "_good": t["pb_percentile_good"],
            "_normal": t["pb_percentile_normal"],
            "_weak": t["pb_percentile_weak"],
        }, reverse=True)
    else:
        pb_score = 70
    
    # 綜合評分（PE 60%, PB 40%）
    composite = pe_score * 0.60 + pb_score * 0.40
    
    return {
        "score": int(round(composite)),
        "details": {
            "pe_percentile": round(pe_pct, 1) if pd.notna(pe_pct) else None,
            "pe_score": pe_score,
            "pb_percentile": round(pb_pct, 1) if pd.notna(pb_pct) else None,
            "pb_score": pb_score,
        }
    }


def score_catalyst(row) -> dict:
    """
    催化因子評分（權重10%）
    
    v2.1 校準：與 revenue_momentum 定量階梯評分區隔，
    改為「突破性事件」判定：
    - 若「最新單月營收創近 12 個月新高」→ 100 分
    - 若「最新月營收連續 3 個月 MoM 持續成長」→ 100 分
    - 其餘狀況 → 70 分（中性，不扣分）
    """
    revenue_momentum = row.get("Revenue_Momentum", None)
    rev_yoy = row.get("Revenue_YoY", None)
    
    # 檢查營收動能：Revenue_Momentum > 0 代表營收持續成長
    if pd.notna(revenue_momentum) and isinstance(revenue_momentum, (int, float)):
        if revenue_momentum >= 3:  # 連續 3 個月 MoM 成長
            score = 100
            note = "營收連續 3 個月 MoM 成長（突破性動能）"
        elif revenue_momentum >= 1:
            score = 100
            note = "營收持續加速成長（正面催化）"
        else:
            score = 70
            note = "無明顯突破性催化因子"
    elif pd.notna(rev_yoy) and rev_yoy > 30:
        score = 85
        note = "營收 YoY > 30%，強勁成長（正面催化）"
    else:
        score = 70
        note = "無明顯突破性催化因子"
    
    return {
        "score": score,
        "details": {
            "revenue_momentum": int(revenue_momentum) if pd.notna(revenue_momentum) else None,
            "catalyst_score": score,
            "note": note,
        }
    }


def score_swing(row, cagr_1_5y=None) -> dict:
    """計算波段總分與子項明細（雙軌制）
    
    v4.2：接收 cagr_1_5y 傳入 score_revenue_momentum
    買入權重：SWING_BUY_WEIGHTS（營收/籌碼/催化權重較高）
    賣出權重：SWING_SELL_WEIGHTS（趨勢/估值權重較高）
    """
    rev = score_revenue_momentum(row, cagr_1_5y)
    mid = score_mid_trend(row)
    inst = score_institutional_trend(row)
    earn = score_earnings_growth(row)
    val = score_valuation_position(row)
    cat = score_catalyst(row)
    
    sub_scores = {
        "revenue_momentum": rev["score"],
        "mid_trend": mid["score"],
        "institutional_trend": inst["score"],
        "earnings_growth": earn["score"],
        "valuation": val["score"],
        "catalyst": cat["score"],
    }
    
    # 雙軌加權計算
    buy_total = (
        sub_scores["revenue_momentum"] * SWING_BUY_WEIGHTS["revenue_momentum"] +
        sub_scores["mid_trend"] * SWING_BUY_WEIGHTS["mid_trend"] +
        sub_scores["institutional_trend"] * SWING_BUY_WEIGHTS["institutional_trend"] +
        sub_scores["earnings_growth"] * SWING_BUY_WEIGHTS["earnings_growth"] +
        sub_scores["valuation"] * SWING_BUY_WEIGHTS["valuation"] +
        sub_scores["catalyst"] * SWING_BUY_WEIGHTS["catalyst"]
    )
    sell_total = (
        sub_scores["revenue_momentum"] * SWING_SELL_WEIGHTS["revenue_momentum"] +
        sub_scores["mid_trend"] * SWING_SELL_WEIGHTS["mid_trend"] +
        sub_scores["institutional_trend"] * SWING_SELL_WEIGHTS["institutional_trend"] +
        sub_scores["earnings_growth"] * SWING_SELL_WEIGHTS["earnings_growth"] +
        sub_scores["valuation"] * SWING_SELL_WEIGHTS["valuation"] +
        sub_scores["catalyst"] * SWING_SELL_WEIGHTS["catalyst"]
    )
    
    return {
        "total_buy": int(round(buy_total)),
        "total_sell": int(round(sell_total)),
        "breakdown": sub_scores,
        "details": {
            "revenue_momentum": rev["details"],
            "mid_trend": mid["details"],
            "institutional_trend": inst["details"],
            "earnings_growth": earn["details"],
            "valuation": val["details"],
            "catalyst": cat["details"],
        }
    }


# ============================================================
# 價值評分
# ============================================================

def score_valuation_safety(row) -> dict:
    """
    估值安全評分（權重15%）
    
    Phase 2 重構：結合 PE_TTM 絕對值與 PB_Percentile (1200D)，
    套用新五級分 [100, 85, 70, 50, 0]。
    
    100分: PE_TTM ≤ 12 且 PB_Percentile ≤ 20%
    85分:  PE_TTM ∈ (12, 15] 且 PB_Percentile ≤ 40%
    70分:  PE_TTM ∈ (15, 20] 或 PB_Percentile ≤ 60%
    50分:  PE_TTM ∈ (20, 30] 且 PB_Percentile ≤ 80%
    0分:   PE_TTM > 30 或 PB_Percentile > 80%
    """
    pe_ttm = row.get("pe_ratio", None)  # 已由 TTM_EPS 覆蓋
    pb_pct = row.get("PB_Percentile", None)
    
    # 雙條件複合評分
    if pd.notna(pe_ttm) and pd.notna(pb_pct):
        if pe_ttm <= 12 and pb_pct <= 20:
            score = 100
        elif pe_ttm <= 15 and pb_pct <= 40:
            score = 85
        elif pe_ttm <= 20 or pb_pct <= 60:
            score = 70
        elif pe_ttm <= 30 and pb_pct <= 80:
            score = 50
        else:
            score = 0
    elif pd.notna(pe_ttm):
        # 僅有 PE 時
        if pe_ttm <= 12:
            score = 85
        elif pe_ttm <= 20:
            score = 70
        elif pe_ttm <= 30:
            score = 50
        else:
            score = 0
    elif pd.notna(pb_pct):
        # 僅有 PB 時
        if pb_pct <= 20:
            score = 85
        elif pb_pct <= 40:
            score = 70
        elif pb_pct <= 60:
            score = 50
        else:
            score = 0
    else:
        score = 70  # 無資料給中間分
    
    return {
        "score": score,
        "details": {
            "pe_ttm": round(pe_ttm, 2) if pd.notna(pe_ttm) else None,
            "pb_percentile": round(pb_pct, 1) if pd.notna(pb_pct) else None,
            "note": "Phase 2: PE_TTM 絕對值 + PB_Percentile 雙條件"
        }
    }


def score_profit_quality(row) -> dict:
    """
    獲利品質評分（權重20%）
    
    Phase 2 重構：以 ROE_TTM 為核心 + EPS 穩定度（使用 CV 概念），
    套用新五級分 [100, 85, 70, 50, 0]。
    
    100分: ROE_TTM ≥ 15% 且 Gross_Margin ≥ 50%
    85分:  ROE_TTM ≥ 10% 且 Gross_Margin ≥ 30%
    70分:  ROE_TTM ≥ 6%
    50分:  ROE_TTM ≥ 3%
    0分:   ROE_TTM < 3% 或資料不足
    """
    roe = row.get("ROE_TTM", None)
    gm = row.get("Gross_Margin", None)
    
    # NaN/0 防禦
    if pd.isna(roe):
        return {
            "score": 0,
            "details": {"roe": None, "note": "ROE_TTM 資料不足"}
        }
    
    # 核心評分：ROE_TTM + Gross_Margin 雙條件
    if roe >= 15 and pd.notna(gm) and gm >= 50:
        score = 100
    elif roe >= 10 and pd.notna(gm) and gm >= 30:
        score = 85
    elif roe >= 6:
        score = 70
    elif roe >= 3:
        score = 50
    else:
        score = 0
    
    return {
        "score": score,
        "details": {
            "roe": round(roe, 2),
            "gross_margin": round(gm, 2) if pd.notna(gm) else None,
            "note": "Phase 2: ROE_TTM + Gross_Margin 雙條件評分"
        }
    }


def score_growth_ability(row) -> dict:
    """成長能力評分（權重20%）"""
    t = VALUE_THRESHOLDS
    
    # TTM EPS
    ttm_eps = row.get("TTM_EPS", 0)
    ttm_eps_valid = row.get("TTM_EPS_Valid", True)
    if pd.notna(ttm_eps) and ttm_eps_valid:
        eps_score = five_level_score(ttm_eps, {
            "_excellent": t["ttm_eps_excellent"],
            "_good": t["ttm_eps_good"],
            "_normal": t["ttm_eps_normal"],
            "_weak": t["ttm_eps_weak"],
        })
    else:
        eps_score = 0
    
    # Revenue YoY
    rev_yoy = row.get("Revenue_YoY", 0)
    rev_score = five_level_score(rev_yoy, {
        "_excellent": t["rev_yoy_excellent"],
        "_good": t["rev_yoy_good"],
        "_normal": t["rev_yoy_normal"],
        "_weak": t["rev_yoy_weak"],
    })
    
    # 綜合評分（TTM EPS 60%, Revenue YoY 40%）
    composite = eps_score * 0.60 + rev_score * 0.40
    
    return {
        "score": int(round(composite)),
        "details": {
            "ttm_eps": round(ttm_eps, 2) if pd.notna(ttm_eps) else None,
            "eps_score": eps_score,
            "revenue_yoy": round(rev_yoy, 2) if pd.notna(rev_yoy) else None,
            "rev_score": rev_score,
        }
    }


def score_financial_safety_value(row) -> dict:
    """財務安全評分（權重15%）— 反向評分：負債比越低越好
    
    v5.1：金融業跳過負債比評分，改給基準滿分 100
    """
    # v5.1：金融業防錯
    if is_finance(row):
        return {
            "score": 100,
            "details": {
                "debt_ratio": row.get("Debt_Ratio", None),
                "debt_score": 100,
                "note": "金融業不適用負債比評分，給予基準滿分"
            }
        }
    
    t = VALUE_THRESHOLDS
    
    # 負債比（反向評分）
    debt = row.get("Debt_Ratio", 100)
    debt_score = five_level_score(debt, {
        "_excellent": t["debt_ratio_excellent"],
        "_good": t["debt_ratio_good"],
        "_normal": t["debt_ratio_normal"],
        "_weak": t["debt_ratio_weak"],
    }, reverse=True)
    
    # 流動比率
    current_ratio = row.get("Current_Ratio", 0)
    cr_score = five_level_score(current_ratio, {
        "_excellent": t["current_ratio_excellent"],
        "_good": t["current_ratio_good"],
        "_normal": t["current_ratio_normal"],
        "_weak": t["current_ratio_weak"],
    })
    
    # 綜合評分（負債比 60%, 流動比率 40%）
    composite = debt_score * 0.60 + cr_score * 0.40
    
    return {
        "score": int(round(composite)),
        "details": {
            "debt_ratio": round(debt, 2) if pd.notna(debt) else None,
            "debt_score": debt_score,
            "current_ratio": round(current_ratio, 2) if pd.notna(current_ratio) else None,
            "cr_score": cr_score,
        }
    }


def score_cash_flow_quality(row) -> dict:
    """現金流品質評分（權重10%）
    
    v5.1：金融業跳過營業現金流評分，改給基準滿分 100
    """
    # v5.1：金融業防錯
    if is_finance(row):
        return {
            "score": 100,
            "details": {
                "note": "金融業不適用營業現金流評分，給予基準滿分"
            }
        }
    
    t = VALUE_THRESHOLDS
    
    # TTM FCF
    ttm_fcf = row.get("TTM_FCF", 0)
    fcf_score = five_level_score(ttm_fcf, {
        "_excellent": t["ttm_fcf_excellent"],
        "_good": t["ttm_fcf_good"],
        "_normal": t["ttm_fcf_normal"],
        "_weak": t["ttm_fcf_weak"],
    })
    
    # Operating CF
    ocf = row.get("TTM_OCF", 0)
    ocf_score = five_level_score(ocf, {
        "_excellent": t["ocf_excellent"],
        "_good": t["ocf_good"],
        "_normal": t["ocf_normal"],
        "_weak": t["ocf_weak"],
    })
    
    # 綜合評分（FCF 60%, OCF 40%）
    composite = fcf_score * 0.60 + ocf_score * 0.40
    
    return {
        "score": int(round(composite)),
        "details": {
            "ttm_fcf": round(ttm_fcf, 0) if pd.notna(ttm_fcf) else None,
            "fcf_score": fcf_score,
            "ocf_score": ocf_score,
        }
    }


def score_shareholder_return(row) -> dict:
    """股東報酬評分（權重10%）"""
    t = VALUE_THRESHOLDS
    
    # 殖利率
    div_yield = row.get("dividend_yield", 0)
    yield_score = five_level_score(div_yield, {
        "_excellent": t["div_yield_excellent"],
        "_good": t["div_yield_good"],
        "_normal": t["div_yield_normal"],
        "_weak": t["div_yield_weak"],
    })
    
    # 股利
    dividend = row.get("cash_dividend_total", 0)
    if pd.notna(dividend) and dividend > 0:
        div_score = 100
    elif pd.notna(dividend):
        div_score = 0
    else:
        div_score = 70  # 無資料給中間分
    
    # 綜合評分（殖利率 60%, 股利 40%）
    composite = yield_score * 0.60 + div_score * 0.40
    
    return {
        "score": int(round(composite)),
        "details": {
            "dividend_yield": round(div_yield, 2) if pd.notna(div_yield) else None,
            "yield_score": yield_score,
            "dividend": round(dividend, 2) if pd.notna(dividend) else None,
            "div_score": div_score,
        }
    }


def _redistribute_weights(skip_keys: list, original_weights: dict) -> dict:
    """
    金融股權重等比例再分配
    
    跳過特定子項後，將其權重等比例分配給其餘子項。
    
    Args:
        skip_keys: 要跳過的子項 key 列表
        original_weights: 原始權重 dict
    
    Returns:
        新的權重 dict（已排除跳過項目）
    """
    total_skip = sum(original_weights.get(k, 0) for k in skip_keys)
    if total_skip >= 1.0 or total_skip == 0:
        return {k: v for k, v in original_weights.items() if k not in skip_keys}
    
    ratio = 1.0 / (1.0 - total_skip)
    return {k: v * ratio for k, v in original_weights.items() if k not in skip_keys}


def score_value(row, data_years_available: int = 10) -> dict:
    """計算價值總分與子項明細
    
    v2.0：金融股跳過財務安全(15%) + 現金流品質(10%)，
    權重等比例再分配給其餘 4 子項。
    """
    is_fin = is_finance(row)
    weights = VALUE_WEIGHTS
    
    val_safety = score_valuation_safety(row)
    profit = score_profit_quality(row)
    growth = score_growth_ability(row)
    fin_safety = score_financial_safety_value(row)
    cf = score_cash_flow_quality(row)
    shareholder = score_shareholder_return(row)
    
    breakdown = {
        "valuation_safety": val_safety["score"],
        "profit_quality": profit["score"],
        "growth_ability": growth["score"],
        "financial_safety": fin_safety["score"],
        "cash_flow_quality": cf["score"],
        "shareholder_return": shareholder["score"],
    }
    
    # v2.0：金融股權重再分配
    if is_fin:
        skip_keys = ["financial_safety", "cash_flow_quality"]
        adj_weights = _redistribute_weights(skip_keys, weights)
        weighted_total = 0
        for k, w in adj_weights.items():
            weighted_total += breakdown.get(k, 0) * w
        finance_note = f"金融股跳過財務安全+現金流品質({sum(weights.get(k,0) for k in skip_keys)*100:.0f}%)，權重等比例再分配"
    else:
        weighted_total = (
            val_safety["score"] * weights["valuation_safety"] +
            profit["score"] * weights["profit_quality"] +
            growth["score"] * weights["growth_ability"] +
            fin_safety["score"] * weights["financial_safety"] +
            cf["score"] * weights["cash_flow_quality"] +
            shareholder["score"] * weights["shareholder_return"]
        )
        finance_note = None
    
    base_score = int(round(weighted_total))
    
    # 套用 Data Quality Modifier
    dq_modifier = get_data_quality_modifier(data_years_available)
    adjusted_score = int(round(base_score * dq_modifier))
    
    result = {
        "total": adjusted_score,
        "breakdown": breakdown,
        "details": {
            "valuation_safety": val_safety["details"],
            "profit_quality": profit["details"],
            "growth_ability": growth["details"],
            "financial_safety": fin_safety["details"],
            "cash_flow_quality": cf["details"],
            "shareholder_return": shareholder["details"],
        },
        "modifiers": {
            "data_quality": {
                "data_years": data_years_available,
                "modifier": dq_modifier,
                "adjusted_score": adjusted_score,
            }
        }
    }
    
    if finance_note:
        result["modifiers"]["finance_redistribution"] = finance_note
    
    return result


# ============================================================
# 定存評分
# ============================================================

def score_dividend_record(row) -> dict:
    """
    配息紀錄評分（權重25%）
    
    Phase 2 重構：連續配息年數 + 殖利率雙條件，
    套用新五級分 [100, 85, 70, 50, 0]。
    
    100分: 連續配息 ≥ 10 年 且 殖利率 ≥ 6.0%
    85分:  連續配息 ≥ 7 年  且 殖利率 ∈ [4.5%, 6.0%)
    70分:  連續配息 ≥ 5 年  且 殖利率 ∈ [3.0%, 4.5%)
    50分:  連續配息 < 3 年  或 殖利率 < 3.0%
    0分:   無配息或資料不足
    """
    div_years = row.get("Dividend_Continuity_Years", None)
    div_yield = row.get("dividend_yield", None)
    
    # NaN 防禦
    if pd.isna(div_years) or div_years == 0:
        return {
            "score": 0,
            "details": {
                "dividend_continuity_years": 0,
                "note": "無配息紀錄"
            }
        }
    
    div_years = int(div_years)
    
    # 雙條件評分：年數 + 殖利率
    if div_years >= 10 and pd.notna(div_yield) and div_yield >= 6.0:
        score = 100
    elif div_years >= 7 and pd.notna(div_yield) and div_yield >= 4.5:
        score = 85
    elif div_years >= 5 and pd.notna(div_yield) and div_yield >= 3.0:
        score = 70
    elif div_years >= 3:
        score = 50
    else:
        score = 0
    
    return {
        "score": score,
        "details": {
            "dividend_continuity_years": div_years,
            "dividend_yield": round(div_yield, 2) if pd.notna(div_yield) else None,
            "note": "Phase 2: 連續配息年數 + 殖利率雙條件評分"
        }
    }


def score_dividend_quality(row) -> dict:
    """
    配息品質評分（權重20%）
    
    Phase 2 重構：以配息率區間為核心 + EPS Cover Ratio，
    套用新五級分 [100, 85, 70, 50, 0]。
    
    100分: Payout_Ratio ∈ [60%, 80%] 且 EPS Cover ≥ 2.0
    85分:  Payout_Ratio ∈ [45%, 60%) 或 EPS Cover ≥ 1.5
    70分:  Payout_Ratio ∈ [30%, 45%) 或 Payout_Ratio ∈ (80%, 90%]
    50分:  Payout_Ratio < 30% 或 EPS Cover < 1.0
    0分:   Payout_Ratio > 90% 或資料不足
    """
    payout = row.get("Payout_Ratio", None)
    ttm_eps = row.get("TTM_EPS", None)
    cash_div = row.get("cash_dividend_total", None)
    
    # 計算 EPS Cover
    eps_cover = None
    if pd.notna(ttm_eps) and pd.notna(cash_div) and cash_div > 0 and ttm_eps > 0:
        eps_cover = ttm_eps / cash_div
    
    # NaN 防禦：無配息率時直接 0 分
    if pd.isna(payout):
        return {
            "score": 0,
            "details": {"payout_ratio": None, "note": "配息率資料不足"}
        }
    
    # Phase 2 階梯式評分：配息率區間 + EPS Cover
    if 60 <= payout <= 80 and pd.notna(eps_cover) and eps_cover >= 2.0:
        score = 100
    elif 45 <= payout < 60 or (pd.notna(eps_cover) and eps_cover >= 1.5):
        score = 85
    elif 30 <= payout < 45 or 80 < payout <= 90:
        score = 70
    elif payout < 30 or (pd.notna(eps_cover) and eps_cover < 1.0):
        score = 50
    else:
        score = 0
    
    return {
        "score": score,
        "details": {
            "payout_ratio": round(payout, 2),
            "eps_cover": round(eps_cover, 2) if pd.notna(eps_cover) else None,
            "note": "Phase 2: 配息率區間 + EPS Cover 雙條件評分"
        }
    }


def score_cash_flow_dividend(row) -> dict:
    """
    現金流評分（權重20%）
    
    Phase 2 重構：使用現金轉換率 Cash_Conv_Ratio = OCF / NI，
    套用新五級分 [100, 85, 70, 50, 0]。
    
    NI < 0 時直接給 0 分（虧損企業無現金流品質可言）。
    
    100分: Cash_Conv_Ratio ≥ 100% 且 FCF_TTM > 0
    85分:  Cash_Conv_Ratio ∈ [80%, 100%) 且 FCF_TTM > 0
    70分:  Cash_Conv_Ratio ∈ [50%, 80%)
    50分:  Cash_Conv_Ratio ∈ [0%, 50%)
    0分:   Cash_Conv_Ratio < 0% 或 NI < 0 或資料不足
    """
    ttm_ocf = row.get("TTM_OCF", None)
    ttm_ni = row.get("TTM_NetIncome", None)
    ttm_fcf = row.get("TTM_FCF", None)
    
    # NaN/0 防禦：NI < 0 → 0 分
    if pd.isna(ttm_ni) or ttm_ni <= 0:
        return {
            "score": 0,
            "details": {"note": "TTM_NetIncome <= 0，無法計算現金轉換率"}
        }
    
    # 計算現金轉換率 OCF / NI（NI > 0 已確保）
    cash_conv = None
    if pd.notna(ttm_ocf):
        cash_conv = ttm_ocf / ttm_ni  # 單位：比值
    
    # NaN/0 防禦
    if pd.isna(cash_conv):
        return {
            "score": 0,
            "details": {"note": "TTM_OCF 資料不足"}
        }
    
    # 核心評分：Cash_Conv_Ratio + FCF 正數條件
    fcf_positive = pd.notna(ttm_fcf) and ttm_fcf > 0
    
    if cash_conv >= 1.0 and fcf_positive:
        score = 100
    elif cash_conv >= 0.8 and fcf_positive:
        score = 85
    elif cash_conv >= 0.5:
        score = 70
    elif cash_conv >= 0:
        score = 50
    else:
        score = 0  # cash_conv < 0
    
    return {
        "score": score,
        "details": {
            "cash_conv_ratio": round(cash_conv, 2),
            "fcf_positive": fcf_positive,
            "note": "Phase 2: 現金轉換率 OCF/NI + FCF 正數條件評分"
        }
    }


def score_financial_safety_dividend(row) -> dict:
    """財務安全評分（權重15%）— 反向評分：負債比越低越好
    
    v5.1：金融業跳過負債比評分，改給基準滿分 100
    """
    # v5.1：金融業防錯
    if is_finance(row):
        return {
            "score": 100,
            "details": {
                "debt_ratio": row.get("Debt_Ratio", None),
                "debt_score": 100,
                "note": "金融業不適用負債比評分，給予基準滿分"
            }
        }
    
    t = DIVIDEND_THRESHOLDS
    
    # 負債比（反向評分）
    debt = row.get("Debt_Ratio", 100)
    debt_score = five_level_score(debt, {
        "_excellent": t["debt_ratio_excellent"],
        "_good": t["debt_ratio_good"],
        "_normal": t["debt_ratio_normal"],
        "_weak": t["debt_ratio_weak"],
    }, reverse=True)
    
    # 利息保障倍數
    interest_cover = row.get("Interest_Coverage", 0)
    ic_score = five_level_score(interest_cover, {
        "_excellent": t["interest_cover_excellent"],
        "_good": t["interest_cover_good"],
        "_normal": t["interest_cover_normal"],
        "_weak": t["interest_cover_weak"],
    })
    
    # 綜合評分（負債比 60%, 利息保障倍數 40%）
    composite = debt_score * 0.60 + ic_score * 0.40
    
    return {
        "score": int(round(composite)),
        "details": {
            "debt_ratio": round(debt, 2) if pd.notna(debt) else None,
            "debt_score": debt_score,
            "interest_coverage": round(interest_cover, 2) if pd.notna(interest_cover) else None,
            "ic_score": ic_score,
        }
    }


def score_profit_stability(row) -> dict:
    """獲利穩定評分（權重10%）— 反向評分：波動越低越好"""
    t = DIVIDEND_THRESHOLDS
    
    # ROE 波動（反向評分）
    roe_std = row.get("ROE_Stability", 999)
    roe_std_score = five_level_score(roe_std, {
        "_excellent": t["roe_std_excellent"],
        "_good": t["roe_std_good"],
        "_normal": t["roe_std_normal"],
        "_weak": t["roe_std_weak"],
    }, reverse=True)
    
    # EPS 波動（反向評分）
    eps_std = row.get("EPS_Stability", 999)
    eps_std_score = five_level_score(eps_std, {
        "_excellent": t["eps_std_excellent"],
        "_good": t["eps_std_good"],
        "_normal": t["eps_std_normal"],
        "_weak": t["eps_std_weak"],
    }, reverse=True)
    
    # 綜合評分（ROE 波動 50%, EPS 波動 50%）
    composite = roe_std_score * 0.50 + eps_std_score * 0.50
    
    return {
        "score": int(round(composite)),
        "details": {
            "roe_std": round(roe_std, 2) if pd.notna(roe_std) else None,
            "roe_std_score": roe_std_score,
            "eps_std_score": eps_std_score,
        }
    }


def score_long_term_growth(row) -> dict:
    """長期成長評分（權重10%）"""
    t = DIVIDEND_THRESHOLDS
    
    # Revenue CAGR（用營收 YoY 近似）
    rev_yoy = row.get("Revenue_YoY", 0)
    rev_cagr_score = five_level_score(rev_yoy, {
        "_excellent": t["rev_cagr_excellent"],
        "_good": t["rev_cagr_good"],
        "_normal": t["rev_cagr_normal"],
        "_weak": t["rev_cagr_weak"],
    })
    
    # EPS YoY（真正的 EPS 年成長率，非 TTM_EPS 絕對值）
    eps_yoy = row.get("EPS_YoY", None)
    eps_yoy_reason = row.get("EPS_YoY_Reason", "")
    eps_yoy_available = pd.notna(eps_yoy) and eps_yoy_reason == ""
    
    if eps_yoy_available:
        eps_yoy_score = five_level_score(eps_yoy, {
            "_excellent": t["eps_yoy_excellent"],
            "_good": t["eps_yoy_good"],
            "_normal": t["eps_yoy_normal"],
            "_weak": t["eps_yoy_weak"],
        })
        eps_note = ""
    else:
        eps_yoy_score = 0
        if eps_yoy_reason == "denominator_invalid":
            eps_note = "去年同期EPS為負或零，無法計算成長率"
        elif eps_yoy_reason == "insufficient_history":
            eps_note = "資料不足（無去年同期EPS）"
        else:
            eps_note = "EPS成長率資料缺失"
    
    # 綜合評分（Revenue CAGR 50%, EPS YoY 50%）
    composite = rev_cagr_score * 0.50 + eps_yoy_score * 0.50
    
    return {
        "score": int(round(composite)),
        "details": {
            "revenue_cagr_score": rev_cagr_score,
            "eps_yoy": round(eps_yoy, 2) if eps_yoy_available else None,
            "eps_yoy_score": eps_yoy_score,
            "eps_yoy_available": eps_yoy_available,
            "eps_yoy_note": eps_note,
        }
    }


def score_dividend(row, data_years_available: int = 10) -> dict:
    """計算定存總分與子項明細
    
    v2.0：金融股跳過現金流(20%) + 財務安全(15%)，
    權重等比例再分配給其餘 4 子項。
    """
    is_fin = is_finance(row)
    weights = DIVIDEND_WEIGHTS
    
    record = score_dividend_record(row)
    quality = score_dividend_quality(row)
    cf = score_cash_flow_dividend(row)
    fin_safety = score_financial_safety_dividend(row)
    stability = score_profit_stability(row)
    growth = score_long_term_growth(row)
    
    breakdown = {
        "dividend_record": record["score"],
        "dividend_quality": quality["score"],
        "cash_flow": cf["score"],
        "financial_safety": fin_safety["score"],
        "profit_stability": stability["score"],
        "long_term_growth": growth["score"],
    }
    
    # v2.0：金融股權重再分配
    if is_fin:
        skip_keys = ["cash_flow", "financial_safety"]
        adj_weights = _redistribute_weights(skip_keys, weights)
        weighted_total = 0
        for k, w in adj_weights.items():
            weighted_total += breakdown.get(k, 0) * w
        finance_note = f"金融股跳過現金流+財務安全({sum(weights.get(k,0) for k in skip_keys)*100:.0f}%)，權重等比例再分配"
    else:
        weighted_total = (
            record["score"] * weights["dividend_record"] +
            quality["score"] * weights["dividend_quality"] +
            cf["score"] * weights["cash_flow"] +
            fin_safety["score"] * weights["financial_safety"] +
            stability["score"] * weights["profit_stability"] +
            growth["score"] * weights["long_term_growth"]
        )
        finance_note = None
    
    base_score = int(round(weighted_total))
    
    # 套用 Data Quality Modifier
    dq_modifier = get_data_quality_modifier(data_years_available)
    adjusted_score = int(round(base_score * dq_modifier))
    
    result = {
        "total": adjusted_score,
        "breakdown": breakdown,
        "details": {
            "dividend_record": record["details"],
            "dividend_quality": quality["details"],
            "cash_flow": cf["details"],
            "financial_safety": fin_safety["details"],
            "profit_stability": stability["details"],
            "long_term_growth": growth["details"],
        },
        "modifiers": {
            "data_quality": {
                "data_years": data_years_available,
                "modifier": dq_modifier,
                "adjusted_score": adjusted_score,
            }
        }
    }
    
    if finance_note:
        result["modifiers"]["finance_redistribution"] = finance_note
    
    return result


# ============================================================
# v5.0 新增：滾動視窗輔助函式（避免 look-ahead bias）
# ============================================================

def _compute_percentile_in_window(df_window: pd.DataFrame, col: str, eps_col: str = None) -> float:
    """
    在滾動視窗 df_window 內重新計算該視窗最新一筆的百分位。
    
    這是避免 look-ahead bias 的關鍵：
    - 只使用截止到時間點 T 的資料來計算百分位
    - 而非使用整個母表的百分位
    
    Parameters:
        df_window: 截至時間點 T 的 DataFrame（含 T）
        col: 要計算百分位的欄位名稱（如 'pe_ratio'）
        eps_col: EPS 欄位名稱（若提供，僅在 EPS > 0 時才納入百分位計算）
    
    Returns:
        float: 最新一筆的百分位（0-100），若資料不足則回傳 NaN
    """
    if df_window.empty or col not in df_window.columns:
        return np.nan
    
    # 準備有效資料
    valid = df_window[col].copy()
    if eps_col and eps_col in df_window.columns:
        valid = valid.where(df_window[eps_col] > 0, np.nan)
    
    valid_series = valid.dropna()
    
    # 至少需要 120 筆資料才能計算百分位
    if len(valid_series) < 120:
        return np.nan
    
    # 計算百分位
    percentile = valid_series.rank(pct=True).iloc[-1] * 100
    return float(percentile)


# ============================================================
# v4.2 新增：核心防禦運算輔助函式（不修改原始評分邏輯）
# ============================================================

def compute_cagr_1_5y(df: pd.DataFrame) -> float:
    """
    計算 1.5 年複合營收成長率（1.5Y-CAGR）
    
    利用 month_revenue、revenue_year、revenue_month。
    最新一筆營收為 R_now，往回搜尋 18 個月前的營收 R_past。
    公式：1.5Y_CAGR = (R_now / R_past)^(1 / 1.5) - 1
    
    防禦機制：找不到 18 月前資料回傳 NaN，由呼叫端處理為 Normal(60分)。
    """
    if df.empty:
        return np.nan
    latest = df.iloc[-1]
    r_now = latest.get("month_revenue", np.nan)
    rev_year = latest.get("revenue_year", np.nan)
    rev_month = latest.get("revenue_month", np.nan)
    if pd.isna(r_now) or pd.isna(rev_year) or pd.isna(rev_month) or r_now <= 0:
        return np.nan
    rev_year = int(rev_year)
    rev_month = int(rev_month)
    target_total = rev_year * 12 + rev_month - 18
    target_year = target_total // 12
    target_month = target_total % 12
    if target_month == 0:
        target_month = 12
        target_year -= 1
    mask = (
        (df["revenue_year"].astype(float).fillna(0).astype(int) == target_year) &
        (df["revenue_month"].astype(float).fillna(0).astype(int) == target_month)
    )
    idx = df.index[mask].tolist()
    if not idx:
        return np.nan
    if idx[-1] > df.index[-1]:
        return np.nan
    r_past = df.loc[idx[-1], "month_revenue"]
    if pd.isna(r_past) or r_past <= 0:
        return np.nan
    ratio = r_now / r_past
    if ratio <= 0:
        return np.nan
    return (ratio ** (1.0 / 1.5) - 1) * 100


def compute_revenue_ma_cross(df: pd.DataFrame) -> dict:
    """
    計算營收動能長短線交叉（3MA vs 6MA）
    
    提取不重複月份營收序列，計算 3MA 與 6MA。
    3MA > 6MA 且斜率向上 → bullish，對應子項 100 分
    3MA < 6MA → bearish，對應子項 0 分
    其他 → neutral，不影響
    """
    result = {"signal": "neutral", "ma3": None, "ma6": None, "ma3_slope_up": False}
    if df.empty or "month_revenue" not in df.columns:
        return result
    if "revenue_year" in df.columns:
        key = df["revenue_year"].astype(str) + "_" + df["revenue_month"].astype(str).str.zfill(2)
        monthly = df.dropna(subset=["month_revenue"]).copy()
        monthly["_key"] = key
        monthly = monthly.groupby("_key").last().reset_index().sort_values("_key")
        s = monthly["month_revenue"].values
    else:
        s = df["month_revenue"].dropna().values
    if len(s) < 6:
        return result
    s = s.astype(float)
    ma3 = float(np.mean(s[-3:]))
    ma6 = float(np.mean(s[-6:]))
    slope = ma3 > float(np.mean(s[-4:-1])) if len(s) >= 4 else False
    signal = "neutral"
    if ma3 > ma6 and slope:
        signal = "bullish"
    elif ma3 < ma6:
        signal = "bearish"
    return {"signal": signal, "ma3": round(ma3, 2), "ma6": round(ma6, 2), "ma3_slope_up": slope}


def check_operating_margin_from_df(df: pd.DataFrame) -> dict:
    """
    使用 DataFrame 歷史資料檢查 Operating_Margin 同比下滑。
    取最新一季與約 4 季前的 OM 比較，下滑 > 2pp 則觸發質檢。
    """
    if df.empty or "Operating_Margin" not in df.columns:
        return {"triggered": False, "current_om": None, "prev_om": None, "drop_pp": None}
    s = df["Operating_Margin"]
    is_new = pd.Series(False, index=df.index) | (s.diff().abs() > 1e-8)
    if pd.notna(s.iloc[0]):
        is_new.iloc[0] = True
    q = df.loc[is_new, ["Operating_Margin"]].dropna()
    if len(q) < 2:
        return {"triggered": False, "current_om": None, "prev_om": None, "drop_pp": None}
    cur = q["Operating_Margin"].iloc[-1]
    prev = q["Operating_Margin"].iloc[-(1 + min(4, len(q) - 1))]
    drop = prev - cur
    triggered = drop > OPERATING_MARGIN_QUALITY["drop_threshold_pp"]
    return {"triggered": triggered, "current_om": round(cur, 2), "prev_om": round(prev, 2), "drop_pp": round(drop, 2)}


def apply_industry_debt_bias(row: dict, base_score: int, style: str,
                              industry_median_debt: float = None) -> dict:
    """
    產業財務去偏誤。不屬排除清單且負債比 > 同業中位數×1.2 則打 85 折。
    """
    if style not in ("value", "dividend"):
        return {"adjusted_score": base_score, "penalty_applied": False, "reason": f"不支援風格：{style}"}
    industry = row.get("Industry", None)
    if industry is None or (isinstance(industry, str) and industry in INDUSTRY_DEBT_BIAS["exclude_sectors"]):
        return {"adjusted_score": base_score, "penalty_applied": False, "reason": "無產業或屬排除產業"}
    debt = row.get("Debt_Ratio", np.nan)
    if pd.isna(debt):
        return {"adjusted_score": base_score, "penalty_applied": False, "reason": "無負債比"}
    if industry_median_debt is None or pd.isna(industry_median_debt):
        return {"adjusted_score": base_score, "penalty_applied": False, "reason": "無同業中位數"}
    threshold = industry_median_debt * INDUSTRY_DEBT_BIAS["debt_ratio_multiplier"]
    if debt > threshold:
        p = INDUSTRY_DEBT_BIAS["value_penalty"] if style == "value" else INDUSTRY_DEBT_BIAS["dividend_penalty"]
        return {"adjusted_score": int(round(base_score * p)), "penalty_applied": True,
                "reason": f"負債比({debt:.1f}%) > 同業中位數({industry_median_debt:.1f}%)×1.2={threshold:.1f}%，打{p}折"}
    return {"adjusted_score": base_score, "penalty_applied": False, "reason": "負債比在安全範圍內"}


# ============================================================
# 主函式
# ============================================================

def get_all_scores(df: pd.DataFrame, start_date: str = None, end_date: str = None) -> dict:
    """對 DataFrame 中最新一筆資料計算四種風格分數
    
    v5.0：加入 start_date / end_date 參數，篩選資料範圍後再評分
    
    Parameters:
        df: 母表 DataFrame（需含 date 欄位）
        start_date: 起始日期（'YYYY-MM-DD'），若指定則篩選 >= 該日期
        end_date: 結束日期（'YYYY-MM-DD'），若指定則篩選 <= 該日期
    
    Returns:
        dict: 四種風格分數結果
    """
    if df.empty:
        return {
            "short_term": {"total": 0, "breakdown": {}, "details": {}},
            "swing": {"total": 0, "breakdown": {}, "details": {}},
            "value": {"total": 0, "breakdown": {}, "details": {}, "modifiers": {}},
            "dividend": {"total": 0, "breakdown": {}, "details": {}, "modifiers": {}},
        }
    
    # === v5.0：時間跨度篩選 ===
    filtered_df = _filter_by_date(df, start_date, end_date)
    if filtered_df.empty:
        return {
            "short_term": {"total": 0, "breakdown": {}, "details": {}},
            "swing": {"total": 0, "breakdown": {}, "details": {}},
            "value": {"total": 0, "breakdown": {}, "details": {}, "modifiers": {}},
            "dividend": {"total": 0, "breakdown": {}, "details": {}, "modifiers": {}},
        }
    
    latest = filtered_df.iloc[-1]
    data_years = latest.get("Data_Years_Available", 10)
    if pd.isna(data_years):
        data_years = 10
    
    # === v4.2 前置計算 ===
    cagr_1_5y = compute_cagr_1_5y(filtered_df)
    revenue_cross = compute_revenue_ma_cross(filtered_df)
    om_quality = check_operating_margin_from_df(filtered_df)
    
    # 產業中位數負債比（用於去偏誤）
    industry_median_debt = None
    if "Industry" in filtered_df.columns and "Debt_Ratio" in filtered_df.columns:
        industry = latest.get("Industry", None)
        if pd.notna(industry) and isinstance(industry, str):
            idata = filtered_df[filtered_df["Industry"] == industry]["Debt_Ratio"].dropna()
            if len(idata) > 0:
                industry_median_debt = idata.median()
    
    # === 計算各風格分數（傳入 v4.2 參數） ===
    short_result = score_short_term(latest)
    swing_result = score_swing(latest, cagr_1_5y)
    value_result = score_value(latest, data_years)
    dividend_result = score_dividend(latest, data_years)
    
    # 套用 Unified Modifier（v2.1：含 DQ + Risk，不含 RSI 重複扣分）
    dq_mod = get_data_quality_modifier(data_years)
    # 短線/波段為雙軌制，買賣各自套用 Modifier
    short_total_buy = apply_all_modifiers(short_result["total_buy"], latest, "short_term", dq_mod)
    short_total_sell = apply_all_modifiers(short_result["total_sell"], latest, "short_term", dq_mod)
    swing_total_buy = apply_all_modifiers(swing_result["total_buy"], latest, "swing", dq_mod)
    swing_total_sell = apply_all_modifiers(swing_result["total_sell"], latest, "swing", dq_mod)
    value_total = apply_all_modifiers(value_result["total"], latest, "value", dq_mod)
    dividend_total = apply_all_modifiers(dividend_result["total"], latest, "dividend", dq_mod)
    
    # === v4.2 流血去庫存質檢（短線/波段打8折，買賣各自打） ===
    if om_quality["triggered"]:
        short_total_buy = int(round(short_total_buy * OPERATING_MARGIN_QUALITY["short_term_penalty"]))
        short_total_sell = int(round(short_total_sell * OPERATING_MARGIN_QUALITY["short_term_penalty"]))
        swing_total_buy = int(round(swing_total_buy * OPERATING_MARGIN_QUALITY["swing_penalty"]))
        swing_total_sell = int(round(swing_total_sell * OPERATING_MARGIN_QUALITY["swing_penalty"]))

    # === v4.2 產業財務去偏誤（價值/定存打85折） ===
    value_bias = apply_industry_debt_bias(latest, value_total, "value", industry_median_debt)
    if value_bias["penalty_applied"]:
        value_total = value_bias["adjusted_score"]
    dividend_bias = apply_industry_debt_bias(latest, dividend_total, "dividend", industry_median_debt)
    if dividend_bias["penalty_applied"]:
        dividend_total = dividend_bias["adjusted_score"]
    
    # 構建結果（短線/波段為雙軌制，買/賣分數各自獨立）
    result = {
        "short_term": {
            "total": short_total_buy,
            "total_buy": short_total_buy,
            "total_sell": short_total_sell,
            "breakdown": short_result["breakdown"],
            "details": short_result["details"],
            "modifiers": {},
        },
        "swing": {
            "total": swing_total_buy,
            "total_buy": swing_total_buy,
            "total_sell": swing_total_sell,
            "breakdown": swing_result["breakdown"],
            "details": swing_result["details"],
            "modifiers": {},
        },
        "value": {
            "total": value_total,
            "breakdown": value_result["breakdown"],
            "details": value_result["details"],
            "modifiers": value_result.get("modifiers", {}),
        },
        "dividend": {
            "total": dividend_total,
            "breakdown": dividend_result["breakdown"],
            "details": dividend_result["details"],
            "modifiers": dividend_result.get("modifiers", {}),
        },
    }
    
    # v4.2 modifiers 共用資訊
    cagr_val = round(cagr_1_5y, 2) if pd.notna(cagr_1_5y) else None
    for k in ["short_term", "swing", "value", "dividend"]:
        result[k]["modifiers"]["cagr_1_5y"] = cagr_val
        result[k]["modifiers"]["revenue_ma_cross"] = revenue_cross["signal"]
    
    # 流血去庫存質檢資訊
    for k in ["short_term", "swing"]:
        result[k]["modifiers"]["operating_margin_quality"] = {
            "triggered": om_quality["triggered"],
            "current_om": om_quality["current_om"],
            "prev_om": om_quality["prev_om"],
            "drop_pp": om_quality["drop_pp"],
        }
    
    # 產業去偏誤資訊
    result["value"]["modifiers"]["industry_debt_bias"] = {
        "penalty_applied": value_bias["penalty_applied"],
        "reason": value_bias["reason"],
    }
    result["dividend"]["modifiers"]["industry_debt_bias"] = {
        "penalty_applied": dividend_bias["penalty_applied"],
        "reason": dividend_bias["reason"],
    }
    
    return result


def get_style_label(style: str) -> str:
    """取得風格中文名稱"""
    labels = {
        "short_term": "短線",
        "swing": "波段",
        "value": "價值",
        "dividend": "定存",
    }
    return labels.get(style, style)


# ============================================================
# v5.0 新增：歷史區間回測評分
# ============================================================

def _filter_by_date(df: pd.DataFrame, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    根據 start_date / end_date 篩選 DataFrame（依 date 欄位）
    
    Parameters:
        df: 輸入 DataFrame（需含 date 欄位）
        start_date: 起始日期 'YYYY-MM-DD'，None 表不限制
        end_date: 結束日期 'YYYY-MM-DD'，None 表不限制
    
    Returns:
        篩選後的 DataFrame
    """
    if df.empty:
        return df
    
    result = df.copy()
    
    # 確保 date 是 datetime
    if not pd.api.types.is_datetime64_any_dtype(result["date"]):
        result["date"] = pd.to_datetime(result["date"])
    
    if start_date is not None:
        start = pd.to_datetime(start_date)
        result = result[result["date"] >= start]
    
    if end_date is not None:
        end = pd.to_datetime(end_date)
        result = result[result["date"] <= end]
    
    return result


def get_historical_scores(
    df: pd.DataFrame,
    start_date: str = None,
    end_date: str = None,
    freq: str = 'W',
) -> pd.DataFrame:
    """
    計算歷史區間內每一個時間點的四種風格分數（walk-forward scoring）
    確保每個時間點只使用截至該點的歷史資料，避免 look-ahead bias。
    
    核心邏輯：
    1. 按日期排序後逐行遍歷
    2. 對每個時間點 T，用 df.iloc[:i+1]（截至 T 的資料）計算分數
    3. 百分位指標在每個視窗內重新計算，確保前瞻無偏
    4. 依 freq 參數控制輸出密度
    
    Parameters:
        df: 母表 DataFrame（需含 date 欄位及所有評分所需的指標欄位）
        start_date: 起始日期 'YYYY-MM-DD'，僅輸出 >= 該日期的分數
                    若未指定，預設為當年年初（2026-01-01）
        end_date: 結束日期 'YYYY-MM-DD'，僅輸出 <= 該日期的分數
                  若未指定，預設為今天
        freq: 輸出頻率，'D'=每日, 'W'=每週（預設）, 'M'=每月, 'Q'=每季
              內部計算仍為每日，僅輸出時做降採樣
    
    Returns:
        pd.DataFrame: 包含 'date' 及各風格分數欄位的歷史分數表
                      欄位：date, short_term_score, swing_score, value_score, dividend_score
    """
    from datetime import datetime, date
    
    if df.empty:
        return pd.DataFrame(columns=[
            "date", "short_term_score", "swing_score",
            "value_score", "dividend_score"
        ])
    
    # === 時間範圍設定 ===
    result_df = df.copy()
    
    # 確保 date 是 datetime 且排序
    if not pd.api.types.is_datetime64_any_dtype(result_df["date"]):
        result_df["date"] = pd.to_datetime(result_df["date"])
    result_df = result_df.sort_values("date").reset_index(drop=True)
    
    # 預設 start_date / end_date
    today = date.today()
    if end_date is None:
        end_date = today.strftime("%Y-%m-%d")
    if start_date is None:
        start_date = f"{today.year}-01-01"
    
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    # === Data_Years_Available（保持固定，從整個資料期間計算） ===
    data_years = df.get("Data_Years_Available", pd.Series(10)).iloc[0]
    if pd.isna(data_years):
        data_years = 10
    
    # === EPS 欄位名稱偵測 ===
    eps_col = None
    for col in df.columns:
        if col == "EPS":
            eps_col = col
            break
    
    # === walk-forward 逐筆評分 ===
    records = []
    n = len(result_df)
    
    # 為了效率，限制最小起點（至少要有足夠的暖機資料）
    # 短線需要至少 60 筆（MA60），加上財務指標需要更久
    # 從第 max(5, n//20) 筆開始，確保至少有 n//20 筆後才產出分數
    # 降低 min_window 讓回測在資料不長時仍有早期分數可用
    min_window = max(5, min(n // 5, 60))  # 至少 5 筆，最多 60 筆（約 3 個月）
    
    for i in range(min_window - 1, n):
        # 取出截至 i 的歷史視窗
        window = result_df.iloc[:i + 1].copy()
        current_row = window.iloc[-1]
        current_date = current_row["date"]
        
        # 若該日期不在輸出範圍內，跳過
        if current_date < start_dt or current_date > end_dt:
            continue
        
        # === 在 walk-forward 視窗內重新計算百分位（避免 look-ahead bias） ===
        pe_pct = _compute_percentile_in_window(window, "pe_ratio", eps_col)
        pb_pct = _compute_percentile_in_window(window, "pb_ratio")
        
        # 建立該時間點的 row dict（覆蓋百分位）
        row_dict = current_row.to_dict()
        if pd.notna(pe_pct):
            row_dict["PE_Percentile"] = pe_pct
        if pd.notna(pb_pct):
            row_dict["PB_Percentile"] = pb_pct
        
        # 將 window 傳入需要歷史資料計算的輔助函式
        cagr_1_5y = compute_cagr_1_5y(window)
        om_quality = check_operating_margin_from_df(window)
        
        # 產業中位數負債比
        industry_median_debt = None
        if "Industry" in window.columns and "Debt_Ratio" in window.columns:
            industry = row_dict.get("Industry", None)
            if pd.notna(industry) and isinstance(industry, str):
                idata = window[window["Industry"] == industry]["Debt_Ratio"].dropna()
                if len(idata) > 0:
                    industry_median_debt = idata.median()
        
        # === 計算四種風格分數 ===
        short_result = score_short_term(row_dict)
        swing_result = score_swing(row_dict, cagr_1_5y)
        value_result = score_value(row_dict, data_years)
        dividend_result = score_dividend(row_dict, data_years)
        
        # Unified Modifier（v2.1：含 DQ + Risk，不含 RSI 重複扣分）
        dq_mod = get_data_quality_modifier(data_years)
        # 短線/波段為雙軌制，歷史回測使用買入分數
        short_total_buy = apply_all_modifiers(short_result["total_buy"], row_dict, "short_term", dq_mod)
        short_total_sell = apply_all_modifiers(short_result["total_sell"], row_dict, "short_term", dq_mod)
        swing_total_buy = apply_all_modifiers(swing_result["total_buy"], row_dict, "swing", dq_mod)
        swing_total_sell = apply_all_modifiers(swing_result["total_sell"], row_dict, "swing", dq_mod)
        value_total = apply_all_modifiers(value_result["total"], row_dict, "value", dq_mod)
        dividend_total = apply_all_modifiers(dividend_result["total"], row_dict, "dividend", dq_mod)
        
        # 流血去庫存（買賣各自打）
        if om_quality["triggered"]:
            short_total_buy = int(round(short_total_buy * OPERATING_MARGIN_QUALITY["short_term_penalty"]))
            short_total_sell = int(round(short_total_sell * OPERATING_MARGIN_QUALITY["short_term_penalty"]))
            swing_total_buy = int(round(swing_total_buy * OPERATING_MARGIN_QUALITY["swing_penalty"]))
            swing_total_sell = int(round(swing_total_sell * OPERATING_MARGIN_QUALITY["swing_penalty"]))
        
        # 產業去偏誤
        value_bias = apply_industry_debt_bias(row_dict, value_total, "value", industry_median_debt)
        if value_bias["penalty_applied"]:
            value_total = value_bias["adjusted_score"]
        dividend_bias = apply_industry_debt_bias(row_dict, dividend_total, "dividend", industry_median_debt)
        if dividend_bias["penalty_applied"]:
            dividend_total = dividend_bias["adjusted_score"]
        
        records.append({
            "date": current_date,
            "short_term_score": short_total_buy,
            "short_term_score_buy": short_total_buy,
            "short_term_score_sell": short_total_sell,
            "swing_score": swing_total_buy,
            "swing_score_buy": swing_total_buy,
            "swing_score_sell": swing_total_sell,
            "value_score": value_total,
            "dividend_score": dividend_total,
        })
    
    if not records:
        return pd.DataFrame(columns=[
            "date", "short_term_score", "swing_score",
            "value_score", "dividend_score"
        ])
    
    # === 轉為 DataFrame 並依 freq 降採樣 ===
    scores_df = pd.DataFrame(records)
    scores_df = scores_df.sort_values("date").reset_index(drop=True)
    
    if freq != 'D':
        # 依頻率降採樣：對每個頻率區間取最後一筆
        scores_df["_freq_key"] = scores_df["date"].dt.to_period(freq)
        scores_df = scores_df.groupby("_freq_key").last().reset_index(drop=True)
        scores_df = scores_df.drop(columns=["_freq_key"], errors="ignore")
    
    return scores_df


if __name__ == "__main__":
    print("scorer.py — 五級評分制 + 回測功能")
