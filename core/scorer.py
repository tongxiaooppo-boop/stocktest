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
    STYLE_PROFILES,
    INERTIA_THRESHOLDS,
    CHIP_CONCENTRATION_THRESHOLDS,
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
    """五級評分通用函式（v2.0 平滑映射：100/85/70/50/0）"""
    if pd.isna(value):
        return 0
    has_excellent = "_excellent" in thresholds
    has_good = "_good" in thresholds
    has_normal = "_normal" in thresholds
    has_weak = "_weak" in thresholds
    has_poor = "_poor" in thresholds
    if reverse:
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
        return 0
    else:
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
    """v2.1 統一 Modifier 疊加邏輯"""
    score = base_score
    score = int(round(score * dq_modifier))
    if industry_bias_adjust is not None:
        score = industry_bias_adjust
    _fin = is_finance(row)
    penalty = 0
    bonus = 0
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
    rsi = row.get("RSI_6", None)
    if pd.notna(rsi) and rsi < RISK_BONUS["rsi_oversold"]["threshold"]:
        bonus += RISK_BONUS["rsi_oversold"]["bonus"]
    if pd.notna(debt) and not _fin and debt < RISK_BONUS["low_debt"]["threshold"]:
        bonus += RISK_BONUS["low_debt"]["bonus"]
    score = score - abs(penalty) + bonus
    return int(np.clip(score, 0, 100))


# ============================================================
# 短線評分 (6 子項)
# ============================================================

def score_trend_structure(row) -> dict:
    """趨勢結構評分（權重20%）"""
    t = SHORT_TERM_THRESHOLDS
    ma_alignment = row.get("MA_Alignment", 0)
    ma_score = five_level_score(ma_alignment, {
        "_excellent": t["ma_alignment_excellent"],
        "_good": t["ma_alignment_good"],
        "_normal": t["ma_alignment_normal"],
        "_weak": t["ma_alignment_weak"],
    })
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
    """動能強度評分（權重20%）"""
    rsi = row.get("RSI_6", None)
    close = row.get("close", None)
    high_5d = row.get("High_5D", None)
    low_5d = row.get("Low_5D", None)
    macd_hist = row.get("MACD_HIST", None)
    if pd.isna(rsi) or pd.isna(close):
        return {"score": 0, "details": {"rsi": None, "note": "RSI 或 close 資料不足"}}
    dist_high = None
    if pd.notna(close) and abs(close) > 1e-10 and pd.notna(high_5d) and high_5d > 0:
        dist_high = (close - high_5d) / close * 100
    break_low = pd.notna(low_5d) and close < low_5d
    macd_positive = pd.notna(macd_hist) and macd_hist > 0
    if break_low or rsi >= rsi_limit:
        score = 0
    elif 65 <= rsi <= 80 and pd.notna(dist_high) and dist_high >= -1.5:
        score = 100
    elif 50 <= rsi < 65 and macd_positive:
        score = 85
    elif 50 <= rsi < 80:
        score = 70
    elif rsi < 50 and pd.notna(dist_high) and dist_high < -5:
        score = 50
    else:
        score = 50
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
    vol_ratio = row.get("Volume_Ratio", 0)
    vol_score = five_level_score(vol_ratio, {
        "_excellent": t["volume_ratio_excellent"],
        "_good": t["volume_ratio_good"],
        "_normal": t["volume_ratio_normal"],
        "_weak": t["volume_ratio_weak"],
    })
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
    inst_5d = row.get("Inst_5D_Net", 0)
    inst_5d_score = five_level_score(inst_5d, {
        "_excellent": t["inst_5d_excellent"],
        "_good": t["inst_5d_good"],
        "_normal": t["inst_5d_normal"],
        "_weak": t["inst_5d_weak"],
    })
    inst_20d = row.get("Inst_20D_Net", 0)
    inst_20d_score = five_level_score(inst_20d, {
        "_excellent": t["inst_20d_surrogate_excellent"],
        "_good": t["inst_20d_surrogate_good"],
        "_normal": t["inst_20d_surrogate_normal"],
        "_weak": t["inst_20d_surrogate_weak"],
    })
    foreign_net = row.get("Foreign_Net", 0)
    foreign_score = five_level_score(foreign_net, {
        "_excellent": t["foreign_excellent"],
        "_good": t["foreign_good"],
        "_normal": t["foreign_normal"],
        "_weak": t["foreign_weak"],
    })
    trust_net = row.get("Trust_Net", 0)
    trust_score = five_level_score(trust_net, {
        "_excellent": t["trust_excellent"],
        "_good": t["trust_good"],
        "_normal": t["trust_normal"],
        "_weak": t["trust_weak"],
    })
    composite = inst_5d_score * 0.35 + inst_20d_score * 0.25 + foreign_score * 0.25 + trust_score * 0.15
    return {
        "score": int(round(composite)),
        "details": {
            "inst_5d_net": int(inst_5d) if pd.notna(inst_5d) else 0,
            "inst_5d_score": inst_5d_score,
            "inst_20d_score": inst_20d_score,
            "inst_20d_is_proxy": True,
            "foreign_score": foreign_score,
            "trust_score": trust_score,
        }
    }


def score_chip_health(row) -> dict:
    """籌碼健康評分（權重15%）"""
    t = SHORT_TERM_THRESHOLDS
    margin_change = row.get("Margin_5D_Change", 0)
    margin_score = five_level_score(margin_change, {
        "_excellent": t["margin_change_excellent"],
        "_good": t["margin_change_good"],
        "_normal": t["margin_change_normal"],
        "_weak": t["margin_change_weak"],
    }, reverse=True)
    short_change = row.get("Short_5D_Change", 0)
    short_score = five_level_score(short_change, {
        "_excellent": t["short_change_excellent"],
        "_good": t["short_change_good"],
        "_normal": t["short_change_normal"],
        "_weak": t["short_change_weak"],
    })
    sbl = row.get("SBL_5D_Change", 0)
    sbl_score = five_level_score(sbl, {
        "_excellent": t["sbl_excellent"],
        "_good": t["sbl_good"],
        "_normal": t["sbl_normal"],
        "_weak": t["sbl_weak"],
    }, reverse=True)
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
    """波動風險評分（權重10%）— 反向評分"""
    bias_5d = row.get("Bias_5D", None)
    rsi = row.get("RSI_6", None)
    if pd.isna(bias_5d):
        bias_5d = row.get("MA60_Bias", None)
    if pd.isna(rsi):
        return {"score": 0, "details": {"note": "RSI 資料不足"}}
    bias_abs = abs(bias_5d) if pd.notna(bias_5d) else 999
    if rsi > rsi_limit:
        score = 0
    elif pd.notna(bias_5d) and bias_abs <= 0.02 and rsi <= 80:
        score = 100
    elif pd.notna(bias_5d) and bias_abs <= 0.05:
        score = 85
    elif pd.notna(bias_5d) and bias_abs > 0.10:
        score = 70
    elif rsi <= rsi_limit:
        score = 50
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
    """計算短線總分與子項明細（雙軌制）"""
    ma_alignment = row.get("MA_Alignment", 0)
    rsi_limit = 95 if pd.notna(ma_alignment) and ma_alignment >= 3 else 88
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
# v3.0 雙分析師短線子項（僅使用 FinMind 免費版可得資料）
# ============================================================

def score_inertia_break(row, high_n=10, low_n=10, consec_required=3) -> dict:
    """慣性突破/破壞評分（v3.0 新增）"""
    close = row.get("close", None)
    high_nd = row.get(f"High_{high_n}D", None)
    low_nd = row.get(f"Low_{low_n}D", None)
    consec_up = row.get("Consec_Up_Days", 0)
    consec_down = row.get("Consec_Down_Days", 0)
    ma5 = row.get("MA_5", None)
    if pd.isna(close):
        return {"score": 0, "details": {"note": "close 資料不足"}}
    break_high = pd.notna(high_nd) and close > high_nd
    break_low = pd.notna(low_nd) and close < low_nd
    strong_up = consec_up is not None and consec_up >= consec_required
    strong_down = consec_down is not None and consec_down >= consec_required
    above_ma5 = pd.notna(ma5) and close > ma5
    if break_low or strong_down:
        score = 0
    elif break_high and strong_up:
        score = 100
    elif break_high or strong_up:
        score = 85
    elif above_ma5:
        score = 70
    else:
        score = 50
    return {
        "score": score,
        "details": {
            "break_high": break_high,
            "break_low": break_low,
            "consec_up_days": consec_up,
            "consec_down_days": consec_down,
            "note": "v3.0: 日K近N日高低點 + 連續漲跌天數判斷",
        }
    }


def score_chip_concentration(row, price_history: pd.DataFrame = None) -> dict:
    """籌碼密集區評分（v3.0 新增，多日日K代理版 POC）"""
    t = CHIP_CONCENTRATION_THRESHOLDS
    close = row.get("close", None)
    if pd.isna(close) or price_history is None or len(price_history) < 10:
        return {"score": 50, "details": {"note": "資料不足，回傳中性分數"}}
    vol_col = "volume" if "volume" in price_history.columns else ("Trading_Volume" if "Trading_Volume" in price_history.columns else "volume")
    hist = price_history.tail(t["lookback_days"]).dropna(subset=["close", vol_col])
    if hist.empty:
        return {"score": 50, "details": {"note": "資料不足，回傳中性分數"}}
    price_min, price_max = hist["close"].min(), hist["close"].max()
    if price_max <= price_min:
        return {"score": 50, "details": {"note": "價格區間過窄，無法分箱"}}
    bins = np.linspace(price_min, price_max, t["num_bins"] + 1)
    hist = hist.copy()
    hist["_bin"] = pd.cut(hist["close"], bins=bins, include_lowest=True)
    vol_by_bin = hist.groupby("_bin", observed=True)[vol_col].sum()
    if vol_by_bin.empty:
        return {"score": 50, "details": {"note": "分箱後無資料"}}
    top_bin = vol_by_bin.idxmax()
    ccp = (top_bin.left + top_bin.right) / 2
    if ccp <= 0:
        return {"score": 50, "details": {"note": "密集區價位異常"}}
    distance = (close - ccp) / ccp * 100
    if distance >= t["dist_excellent"]:
        score = 100
    elif distance >= t["dist_good"]:
        score = 85
    elif distance >= t["dist_normal"]:
        score = 70
    elif distance >= t["dist_weak"]:
        score = 50
    else:
        score = 0
    return {
        "score": score,
        "details": {
            "chip_concentration_price": round(ccp, 2),
            "distance_pct": round(distance, 2),
            "lookback_days": t["lookback_days"],
            "note": "v3.0: 多日收盤價x成交量加權分布，取代單日盤中POC",
        }
    }


def score_short_term_by_profile(row, profile: str = "chaser", price_history: pd.DataFrame = None) -> dict:
    """依分析師人格計算短線總分（v3.0 新增）
    profile: "chaser"（追熱門股） 或 "stable"（穩重型）
    """
    if profile not in STYLE_PROFILES:
        raise ValueError(f"未知的分析師人格: {profile}")
    ma_alignment = row.get("MA_Alignment", 0)
    rsi_limit = 95 if pd.notna(ma_alignment) and ma_alignment >= 3 else 88
    trend = score_trend_structure(row)
    momentum = score_momentum(row, rsi_limit)
    volume = score_volume_structure(row)
    inst = score_institutional(row)
    chip = score_chip_health(row)
    risk = score_volatility_risk(row, rsi_limit)
    inertia = score_inertia_break(row)
    concentration = score_chip_concentration(row, price_history)
    sub_scores = {
        "trend_structure": trend["score"],
        "momentum": momentum["score"],
        "volume": volume["score"],
        "institutional": inst["score"],
        "chip": chip["score"],
        "risk": risk["score"],
        "inertia_break": inertia["score"],
        "chip_concentration": concentration["score"],
    }
    buy_w = STYLE_PROFILES[profile]["buy"]
    sell_w = STYLE_PROFILES[profile]["sell"]
    buy_total = sum(sub_scores[k] * buy_w[k] for k in sub_scores)
    sell_total = sum(sub_scores[k] * sell_w[k] for k in sub_scores)
    return {
        "profile": profile,
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
            "inertia_break": inertia["details"],
            "chip_concentration": concentration["details"],
        }
    }


# ============================================================
# 波段評分
# ============================================================

def score_revenue_momentum(row, cagr_1_5y=None) -> dict:
    """營收動能評分（權重25%）"""
    t = SWING_THRESHOLDS
    rev_yoy = row.get("Revenue_YoY", 0)
    yoy_score = five_level_score(rev_yoy, {
        "_excellent": t["rev_yoy_excellent"], "_good": t["rev_yoy_good"],
        "_normal": t["rev_yoy_normal"], "_weak": t["rev_yoy_weak"],
    })
    rev_mom = row.get("Revenue_MoM", 0)
    mom_score = five_level_score(rev_mom, {
        "_excellent": t["rev_mom_excellent"], "_good": t["rev_mom_good"],
        "_normal": t["rev_mom_normal"], "_weak": t["rev_mom_weak"],
    })
    rev_accel = row.get("Revenue_Accelerating", 0)
    if pd.notna(rev_accel):
        if isinstance(rev_accel, bool):
            rev_accel_val = 1 if rev_accel else 0
        else:
            rev_accel_val = 1 if rev_accel > 0 else 0
        accel_score = five_level_score(rev_accel_val, {"_excellent": t["rev_accel_true"]})
    else:
        accel_score = 0
    cagr_score = 70
    cagr_value = None
    if cagr_1_5y is not None and pd.notna(cagr_1_5y):
        cagr_score = five_level_score(cagr_1_5y, {
            "_excellent": t["cagr_1_5y_excellent"], "_good": t["cagr_1_5y_good"],
            "_normal": t["cagr_1_5y_normal"], "_weak": t["cagr_1_5y_weak"],
            "_poor": t["cagr_1_5y_poor"],
        })
        cagr_value = round(cagr_1_5y, 2)
    if cagr_value is not None:
        composite = yoy_score * 0.35 + mom_score * 0.15 + accel_score * 0.15 + cagr_score * 0.35
    else:
        composite = yoy_score * 0.50 + mom_score * 0.25 + accel_score * 0.25
    return {
        "score": int(round(composite)),
        "details": {
            "revenue_yoy": round(rev_yoy, 2) if pd.notna(rev_yoy) else None,
            "yoy_score": yoy_score, "mom_score": mom_score,
            "accel_score": accel_score,
            "cagr_1_5y": cagr_value,
            "cagr_score": cagr_score if cagr_value is not None else None,
        }
    }


def score_mid_trend(row) -> dict:
    """中期趨勢評分（權重20%）"""
    close = row.get("close", None)
    ma20 = row.get("MA_20", None)
    ma60 = row.get("MA_60", None)
    ma20_slope = row.get("MA20_Slope", None)
    if pd.isna(close):
        return {"score": 0, "details": {"note": "close 資料不足"}}
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
            "above_ma20": above_ma20, "above_ma60": above_ma60,
            "ma20_slope": round(ma20_slope, 6) if pd.notna(ma20_slope) else None,
            "note": "Phase 2: MA20_Slope + 站上均線評分"
        }
    }


def score_institutional_trend(row) -> dict:
    """籌碼趨勢評分（權重20%）"""
    inst_slope = row.get("Inst_Slope_20D", None)
    inst_20d = row.get("Inst_20D_Net", None)
    if pd.isna(inst_20d):
        return {"score": 0, "details": {"note": "Inst_20D_Net 資料不足"}}
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
    ttm_eps = row.get("TTM_EPS", 0)
    ttm_eps_valid = row.get("TTM_EPS_Valid", True)
    if pd.notna(ttm_eps) and ttm_eps_valid:
        eps_score = five_level_score(ttm_eps, {
            "_excellent": t["ttm_eps_excellent"], "_good": t["ttm_eps_good"],
            "_normal": t["ttm_eps_normal"], "_weak": t["ttm_eps_weak"],
        })
    else:
        eps_score = 0
    eps_yoy = row.get("EPS_YoY", None)
    eps_yoy_reason = row.get("EPS_YoY_Reason", "")
    eps_yoy_available = pd.notna(eps_yoy) and eps_yoy_reason == ""
    if eps_yoy_available:
        eps_yoy_score = five_level_score(eps_yoy, {
            "_excellent": t["eps_yoy_excellent"], "_good": t["eps_yoy_good"],
            "_normal": t["eps_yoy_normal"], "_weak": t["eps_yoy_weak"],
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
    """估值位置評分（權重10%）— 反向評分"""
    t = SWING_THRESHOLDS
    pe_pct = row.get("PE_Percentile", None)
    if pd.notna(pe_pct):
        pe_score = five_level_score(pe_pct, {
            "_excellent": t["pe_percentile_excellent"], "_good": t["pe_percentile_good"],
            "_normal": t["pe_percentile_normal"], "_weak": t["pe_percentile_weak"],
        }, reverse=True)
    else:
        pe_score = 70
    pb_pct = row.get("PB_Percentile", None)
    if pd.notna(pb_pct):
        pb_score = five_level_score(pb_pct, {
            "_excellent": t["pb_percentile_excellent"], "_good": t["pb_percentile_good"],
            "_normal": t["pb_percentile_normal"], "_weak": t["pb_percentile_weak"],
        }, reverse=True)
    else:
        pb_score = 70
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
    """催化因子評分"""
    revenue_12m_high = row.get("Revenue_12M_High", None)
    revenue_6m_high = row.get("Revenue_6M_High", None)
    rev_yoy = row.get("Revenue_YoY", None)
    if revenue_12m_high is True:
        score = 100
        note = "最新單月營收創近12個月新高（突破性催化）"
    elif revenue_6m_high is True:
        score = 85
        note = "最新單月營收創近6個月新高"
    elif pd.notna(rev_yoy) and rev_yoy > 30:
        score = 75
        note = "營收YoY > 30%，強勁成長，但非創高突破"
    else:
        score = 70
        note = "無明顯突破性催化因子"
    return {
        "score": score,
        "details": {
            "revenue_12m_high": revenue_12m_high,
            "revenue_6m_high": revenue_6m_high,
            "rev_yoy": round(rev_yoy, 2) if pd.notna(rev_yoy) else None,
            "note": note,
        }
    }


def score_swing(row, cagr_1_5y=None) -> dict:
    """計算波段總分與子項明細（雙軌制）"""
    rev = score_revenue_momentum(row, cagr_1_5y)
    mid = score_mid_trend(row)
    inst = score_institutional_trend(row)
    earn = score_earnings_growth(row)
    val = score_valuation_position(row)
    cat = score_catalyst(row)
    sub_scores = {
        "revenue_momentum": rev["score"], "mid_trend": mid["score"],
        "institutional_trend": inst["score"], "earnings_growth": earn["score"],
        "valuation": val["score"], "catalyst": cat["score"],
    }
    buy_total = sum(sub_scores[k] * SWING_BUY_WEIGHTS[k] for k in sub_scores)
    sell_total = sum(sub_scores[k] * SWING_SELL_WEIGHTS[k] for k in sub_scores)
    return {
        "total_buy": int(round(buy_total)), "total_sell": int(round(sell_total)),
        "breakdown": sub_scores,
        "details": {
            "revenue_momentum": rev["details"], "mid_trend": mid["details"],
            "institutional_trend": inst["details"], "earnings_growth": earn["details"],
            "valuation": val["details"], "catalyst": cat["details"],
        }
    }


# ============================================================
# 價值評分
# ============================================================

def score_valuation_safety(row) -> dict:
    """估值安全評分（權重15%）"""
    pe_ttm = row.get("pe_ratio", None)
    pb_pct = row.get("PB_Percentile", None)
    if pd.notna(pe_ttm) and pd.notna(pb_pct):
        if pe_ttm <= 12 and pb_pct <= 20: score = 100
        elif pe_ttm <= 15 and pb_pct <= 40: score = 85
        elif pe_ttm <= 20 or pb_pct <= 60: score = 70
        elif pe_ttm <= 30 and pb_pct <= 80: score = 50
        else: score = 0
    elif pd.notna(pe_ttm):
        if pe_ttm <= 12: score = 85
        elif pe_ttm <= 20: score = 70
        elif pe_ttm <= 30: score = 50
        else: score = 0
    elif pd.notna(pb_pct):
        if pb_pct <= 20: score = 85
        elif pb_pct <= 40: score = 70
        elif pb_pct <= 60: score = 50
        else: score = 0
    else:
        score = 70
    return {
        "score": score,
        "details": {
            "pe_ttm": round(pe_ttm, 2) if pd.notna(pe_ttm) else None,
            "pb_percentile": round(pb_pct, 1) if pd.notna(pb_pct) else None,
            "note": "Phase 2: PE_TTM 絕對值 + PB_Percentile 雙條件"
        }
    }


def score_profit_quality(row) -> dict:
    """獲利品質評分（權重20%）"""
    roe = row.get("ROE_TTM", None)
    gm = row.get("Gross_Margin", None)
    if pd.isna(roe): return {"score": 0, "details": {"roe": None, "note": "ROE_TTM 資料不足"}}
    if roe >= 15 and pd.notna(gm) and gm >= 50: score = 100
    elif roe >= 10 and pd.notna(gm) and gm >= 30: score = 85
    elif roe >= 6: score = 70
    elif roe >= 3: score = 50
    else: score = 0
    return {
        "score": score,
        "details": {"roe": round(roe, 2), "gross_margin": round(gm, 2) if pd.notna(gm) else None,
                    "note": "Phase 2: ROE_TTM + Gross_Margin 雙條件評分"}
    }


def score_growth_ability(row) -> dict:
    """成長能力評分（權重20%）"""
    t = VALUE_THRESHOLDS
    ttm_eps = row.get("TTM_EPS", 0)
    ttm_eps_valid = row.get("TTM_EPS_Valid", True)
    if pd.notna(ttm_eps) and ttm_eps_valid:
        eps_score = five_level_score(ttm_eps, {
            "_excellent": t["ttm_eps_excellent"], "_good": t["ttm_eps_good"],
            "_normal": t["ttm_eps_normal"], "_weak": t["ttm_eps_weak"],
        })
    else:
        eps_score = 0
    rev_yoy = row.get("Revenue_YoY", 0)
    rev_score = five_level_score(rev_yoy, {
        "_excellent": t["rev_yoy_excellent"], "_good": t["rev_yoy_good"],
        "_normal": t["rev_yoy_normal"], "_weak": t["rev_yoy_weak"],
    })
    composite = eps_score * 0.60 + rev_score * 0.40
    return {
        "score": int(round(composite)),
        "details": {"ttm_eps": round(ttm_eps, 2) if pd.notna(ttm_eps) else None,
                    "eps_score": eps_score,
                    "revenue_yoy": round(rev_yoy, 2) if pd.notna(rev_yoy) else None,
                    "rev_score": rev_score}
    }


def score_financial_safety_value(row) -> dict:
    """財務安全評分（權重15%）"""
    if is_finance(row):
        return {"score": 100, "details": {"debt_ratio": row.get("Debt_Ratio", None),
                "debt_score": 100, "note": "金融業不適用負債比評分，給予基準滿分"}}
    t = VALUE_THRESHOLDS
    debt = row.get("Debt_Ratio", 100)
    debt_score = five_level_score(debt, {
        "_excellent": t["debt_ratio_excellent"], "_good": t["debt_ratio_good"],
        "_normal": t["debt_ratio_normal"], "_weak": t["debt_ratio_weak"],
    }, reverse=True)
    current_ratio = row.get("Current_Ratio", 0)
    cr_score = five_level_score(current_ratio, {
        "_excellent": t["current_ratio_excellent"], "_good": t["current_ratio_good"],
        "_normal": t["current_ratio_normal"], "_weak": t["current_ratio_weak"],
    })
    composite = debt_score * 0.60 + cr_score * 0.40
    return {"score": int(round(composite)),
            "details": {"debt_ratio": round(debt, 2) if pd.notna(debt) else None,
                        "debt_score": debt_score,
                        "current_ratio": round(current_ratio, 2) if pd.notna(current_ratio) else None,
                        "cr_score": cr_score}}


def score_cash_flow_quality(row) -> dict:
    """現金流品質評分（權重10%）"""
    if is_finance(row):
        return {"score": 100, "details": {"note": "金融業不適用營業現金流評分，給予基準滿分"}}
    t = VALUE_THRESHOLDS
    ttm_fcf = row.get("TTM_FCF", 0)
    fcf_score = five_level_score(ttm_fcf, {
        "_excellent": t["ttm_fcf_excellent"], "_good": t["ttm_fcf_good"],
        "_normal": t["ttm_fcf_normal"], "_weak": t["ttm_fcf_weak"],
    })
    ocf = row.get("TTM_OCF", 0)
    ocf_score = five_level_score(ocf, {
        "_excellent": t["ocf_excellent"], "_good": t["ocf_good"],
        "_normal": t["ocf_normal"], "_weak": t["ocf_weak"],
    })
    composite = fcf_score * 0.60 + ocf_score * 0.40
    return {"score": int(round(composite)),
            "details": {"ttm_fcf": round(ttm_fcf, 0) if pd.notna(ttm_fcf) else None,
                        "fcf_score": fcf_score, "ocf_score": ocf_score}}


def score_shareholder_return(row) -> dict:
    """股東報酬評分（權重10%）"""
    t = VALUE_THRESHOLDS
    div_yield = row.get("dividend_yield", 0)
    yield_score = five_level_score(div_yield, {
        "_excellent": t["div_yield_excellent"], "_good": t["div_yield_good"],
        "_normal": t["div_yield_normal"], "_weak": t["div_yield_weak"],
    })
    dividend = row.get("cash_dividend_total", 0)
    if pd.notna(dividend) and dividend > 0: div_score = 100
    elif pd.notna(dividend): div_score = 0
    else: div_score = 70
    composite = yield_score * 0.60 + div_score * 0.40
    return {"score": int(round(composite)),
            "details": {"dividend_yield": round(div_yield, 2) if pd.notna(div_yield) else None,
                        "yield_score": yield_score,
                        "dividend": round(dividend, 2) if pd.notna(dividend) else None,
                        "div_score": div_score}}


def _redistribute_weights(skip_keys: list, original_weights: dict) -> dict:
    """金融股權重等比例再分配"""
    total_skip = sum(original_weights.get(k, 0) for k in skip_keys)
    if total_skip >= 1.0 or total_skip == 0:
        return {k: v for k, v in original_weights.items() if k not in skip_keys}
    ratio = 1.0 / (1.0 - total_skip)
    return {k: v * ratio for k, v in original_weights.items() if k not in skip_keys}


def score_value(row, data_years_available: int = 10) -> dict:
    """計算價值總分與子項明細"""
    is_fin = is_finance(row)
    weights = VALUE_WEIGHTS
    val_safety = score_valuation_safety(row)
    profit = score_profit_quality(row)
    growth = score_growth_ability(row)
    fin_safety = score_financial_safety_value(row)
    cf = score_cash_flow_quality(row)
    shareholder = score_shareholder_return(row)
    breakdown = {
        "valuation_safety": val_safety["score"], "profit_quality": profit["score"],
        "growth_ability": growth["score"], "financial_safety": fin_safety["score"],
        "cash_flow_quality": cf["score"], "shareholder_return": shareholder["score"],
    }
    if is_fin:
        skip_keys = ["financial_safety", "cash_flow_quality"]
        adj_weights = _redistribute_weights(skip_keys, weights)
        weighted_total = sum(breakdown.get(k, 0) * w for k, w in adj_weights.items())
        finance_note = f"金融股跳過財務安全+現金流品質({sum(weights.get(k,0) for k in skip_keys)*100:.0f}%)，權重等比例再分配"
    else:
        weighted_total = (val_safety["score"] * weights["valuation_safety"] + profit["score"] * weights["profit_quality"] +
                         growth["score"] * weights["growth_ability"] + fin_safety["score"] * weights["financial_safety"] +
                         cf["score"] * weights["cash_flow_quality"] + shareholder["score"] * weights["shareholder_return"])
        finance_note = None
    base_score = int(round(weighted_total))
    dq_modifier = get_data_quality_modifier(data_years_available)
    adjusted_score = int(round(base_score * dq_modifier))
    result = {
        "total": adjusted_score, "breakdown": breakdown,
        "details": {"valuation_safety": val_safety["details"], "profit_quality": profit["details"],
                    "growth_ability": growth["details"], "financial_safety": fin_safety["details"],
                    "cash_flow_quality": cf["details"], "shareholder_return": shareholder["details"]},
        "modifiers": {"data_quality": {"data_years": data_years_available, "modifier": dq_modifier, "adjusted_score": adjusted_score}}
    }
    if finance_note: result["modifiers"]["finance_redistribution"] = finance_note
    return result


# ============================================================
# 定存評分
# ============================================================

def score_dividend_record(row) -> dict:
    """配息紀錄評分（權重25%）"""
    div_years = row.get("Dividend_Continuity_Years", None)
    div_yield = row.get("dividend_yield", None)
    if pd.isna(div_years) or div_years == 0:
        return {"score": 0, "details": {"dividend_continuity_years": 0, "note": "無配息紀錄"}}
    div_years = int(div_years)
    if div_years >= 10 and pd.notna(div_yield) and div_yield >= 6.0: score = 100
    elif div_years >= 7 and pd.notna(div_yield) and div_yield >= 4.5: score = 85
    elif div_years >= 5 and pd.notna(div_yield) and div_yield >= 3.0: score = 70
    elif div_years >= 3: score = 50
    else: score = 0
    return {"score": score, "details": {"dividend_continuity_years": div_years,
            "dividend_yield": round(div_yield, 2) if pd.notna(div_yield) else None,
            "note": "Phase 2: 連續配息年數 + 殖利率雙條件評分"}}


def score_dividend_quality(row) -> dict:
    """配息品質評分（權重20%）"""
    payout = row.get("Payout_Ratio", None)
    ttm_eps = row.get("TTM_EPS", None)
    cash_div = row.get("cash_dividend_total", None)
    eps_cover = None
    if pd.notna(ttm_eps) and pd.notna(cash_div) and cash_div > 0 and ttm_eps > 0:
        eps_cover = ttm_eps / cash_div
    if pd.isna(payout): return {"score": 0, "details": {"payout_ratio": None, "note": "配息率資料不足"}}
    if 60 <= payout <= 80 and pd.notna(eps_cover) and eps_cover >= 2.0: score = 100
    elif 45 <= payout < 60 or (pd.notna(eps_cover) and eps_cover >= 1.5): score = 85
    elif 30 <= payout < 45 or 80 < payout <= 90: score = 70
    elif payout < 30 or (pd.notna(eps_cover) and eps_cover < 1.0): score = 50
    else: score = 0
    return {"score": score, "details": {"payout_ratio": round(payout, 2),
            "eps_cover": round(eps_cover, 2) if pd.notna(eps_cover) else None,
            "note": "Phase 2: 配息率區間 + EPS Cover 雙條件評分"}}


def score_cash_flow_dividend(row) -> dict:
    """現金流評分（權重20%）"""
    ttm_ocf = row.get("TTM_OCF", None)
    ttm_ni = row.get("TTM_NetIncome", None)
    ttm_fcf = row.get("TTM_FCF", None)
    if pd.isna(ttm_ni) or ttm_ni <= 0:
        return {"score": 0, "details": {"note": "TTM_NetIncome <= 0，無法計算現金轉換率"}}
    cash_conv = None
    if pd.notna(ttm_ocf): cash_conv = ttm_ocf / ttm_ni
    if pd.isna(cash_conv): return {"score": 0, "details": {"note": "TTM_OCF 資料不足"}}
    fcf_positive = pd.notna(ttm_fcf) and ttm_fcf > 0
    if cash_conv >= 1.0 and fcf_positive: score = 100
    elif cash_conv >= 0.8 and fcf_positive: score = 85
    elif cash_conv >= 0.5: score = 70
    elif cash_conv >= 0: score = 50
    else: score = 0
    return {"score": score, "details": {"cash_conv_ratio": round(cash_conv, 2),
            "fcf_positive": fcf_positive, "note": "Phase 2: 現金轉換率 OCF/NI + FCF 正數條件評分"}}


def score_financial_safety_dividend(row) -> dict:
    """財務安全評分（權重15%）"""
    if is_finance(row):
        return {"score": 100, "details": {"debt_ratio": row.get("Debt_Ratio", None),
                "debt_score": 100, "note": "金融業不適用負債比評分，給予基準滿分"}}
    t = DIVIDEND_THRESHOLDS
    debt = row.get("Debt_Ratio", 100)
    debt_score = five_level_score(debt, {
        "_excellent": t["debt_ratio_excellent"], "_good": t["debt_ratio_good"],
        "_normal": t["debt_ratio_normal"], "_weak": t["debt_ratio_weak"],
    }, reverse=True)
    interest_cover = row.get("Interest_Coverage", 0)
    ic_score = five_level_score(interest_cover, {
        "_excellent": t["interest_cover_excellent"], "_good": t["interest_cover_good"],
        "_normal": t["interest_cover_normal"], "_weak": t["interest_cover_weak"],
    })
    composite = debt_score * 0.60 + ic_score * 0.40
    return {"score": int(round(composite)),
            "details": {"debt_ratio": round(debt, 2) if pd.notna(debt) else None,
                        "debt_score": debt_score,
                        "interest_coverage": round(interest_cover, 2) if pd.notna(interest_cover) else None,
                        "ic_score": ic_score}}


def score_profit_stability(row) -> dict:
    """獲利穩定評分（權重10%）"""
    t = DIVIDEND_THRESHOLDS
    roe_std = row.get("ROE_Stability", 999)
    roe_std_score = five_level_score(roe_std, {
        "_excellent": t["roe_std_excellent"], "_good": t["roe_std_good"],
        "_normal": t["roe_std_normal"], "_weak": t["roe_std_weak"],
    }, reverse=True)
    eps_std = row.get("EPS_Stability", 999)
    eps_std_score = five_level_score(eps_std, {
        "_excellent": t["eps_std_excellent"], "_good": t["eps_std_good"],
        "_normal": t["eps_std_normal"], "_weak": t["eps_std_weak"],
    }, reverse=True)
    composite = roe_std_score * 0.50 + eps_std_score * 0.50
    return {"score": int(round(composite)),
            "details": {"roe_std": round(roe_std, 2) if pd.notna(roe_std) else None,
                        "roe_std_score": roe_std_score, "eps_std_score": eps_std_score}}


def score_long_term_growth(row) -> dict:
    """長期成長評分（權重10%）"""
    t = DIVIDEND_THRESHOLDS
    rev_yoy = row.get("Revenue_YoY", 0)
    rev_cagr_score = five_level_score(rev_yoy, {
        "_excellent": t["rev_cagr_excellent"], "_good": t["rev_cagr_good"],
        "_normal": t["rev_cagr_normal"], "_weak": t["rev_cagr_weak"],
    })
    eps_yoy = row.get("EPS_YoY", None)
    eps_yoy_reason = row.get("EPS_YoY_Reason", "")
    eps_yoy_available = pd.notna(eps_yoy) and eps_yoy_reason == ""
    if eps_yoy_available:
        eps_yoy_score = five_level_score(eps_yoy, {
            "_excellent": t["eps_yoy_excellent"], "_good": t["eps_yoy_good"],
            "_normal": t["eps_yoy_normal"], "_weak": t["eps_yoy_weak"],
        })
        eps_note = ""
    else:
        eps_yoy_score = 0
        if eps_yoy_reason == "denominator_invalid": eps_note = "去年同期EPS為負或零，無法計算成長率"
        elif eps_yoy_reason == "insufficient_history": eps_note = "資料不足（無去年同期EPS）"
        else: eps_note = "EPS成長率資料缺失"
    composite = rev_cagr_score * 0.50 + eps_yoy_score * 0.50
    return {"score": int(round(composite)),
            "details": {"revenue_cagr_score": rev_cagr_score,
                        "eps_yoy": round(eps_yoy, 2) if eps_yoy_available else None,
                        "eps_yoy_score": eps_yoy_score, "eps_yoy_available": eps_yoy_available,
                        "eps_yoy_note": eps_note}}


def score_dividend(row, data_years_available: int = 10) -> dict:
    """計算定存總分與子項明細"""
    is_fin = is_finance(row)
    weights = DIVIDEND_WEIGHTS
    record = score_dividend_record(row)
    quality = score_dividend_quality(row)
    cf = score_cash_flow_dividend(row)
    fin_safety = score_financial_safety_dividend(row)
    stability = score_profit_stability(row)
    growth = score_long_term_growth(row)
    breakdown = {
        "dividend_record": record["score"], "dividend_quality": quality["score"],
        "cash_flow": cf["score"], "financial_safety": fin_safety["score"],
        "profit_stability": stability["score"], "long_term_growth": growth["score"],
    }
    if is_fin:
        skip_keys = ["cash_flow", "financial_safety"]
        adj_weights = _redistribute_weights(skip_keys, weights)
        weighted_total = sum(breakdown.get(k, 0) * w for k, w in adj_weights.items())
        finance_note = f"金融股跳過現金流+財務安全({sum(weights.get(k,0) for k in skip_keys)*100:.0f}%)，權重等比例再分配"
    else:
        weighted_total = (record["score"] * weights["dividend_record"] + quality["score"] * weights["dividend_quality"] +
                         cf["score"] * weights["cash_flow"] + fin_safety["score"] * weights["financial_safety"] +
                         stability["score"] * weights["profit_stability"] + growth["score"] * weights["long_term_growth"])
        finance_note = None
    base_score = int(round(weighted_total))
    dq_modifier = get_data_quality_modifier(data_years_available)
    adjusted_score = int(round(base_score * dq_modifier))
    result = {
        "total": adjusted_score, "breakdown": breakdown,
        "details": {"dividend_record": record["details"], "dividend_quality": quality["details"],
                    "cash_flow": cf["details"], "financial_safety": fin_safety["details"],
                    "profit_stability": stability["details"], "long_term_growth": growth["details"]},
        "modifiers": {"data_quality": {"data_years": data_years_available, "modifier": dq_modifier, "adjusted_score": adjusted_score}}
    }
    if finance_note: result["modifiers"]["finance_redistribution"] = finance_note
    return result


# ============================================================
# v5.0 / v4.2 輔助函式
# ============================================================

def _compute_percentile_in_window(df_window: pd.DataFrame, col: str, eps_col: str = None) -> float:
    """在滾動視窗 df_window 內重新計算該視窗最新一筆的百分位"""
    if df_window.empty or col not in df_window.columns: return np.nan
    valid = df_window[col].copy()
    if eps_col and eps_col in df_window.columns: valid = valid.where(df_window[eps_col] > 0, np.nan)
    valid_series = valid.dropna()
    if len(valid_series) < 120: return np.nan
    percentile = valid_series.rank(pct=True).iloc[-1] * 100
    return float(percentile)


def compute_cagr_1_5y(df: pd.DataFrame) -> float:
    """計算 1.5 年複合營收成長率"""
    if df.empty: return np.nan
    latest = df.iloc[-1]
    r_now = latest.get("month_revenue", np.nan)
    rev_year = latest.get("revenue_year", np.nan)
    rev_month = latest.get("revenue_month", np.nan)
    if pd.isna(r_now) or pd.isna(rev_year) or pd.isna(rev_month) or r_now <= 0: return np.nan
    rev_year = int(rev_year); rev_month = int(rev_month)
    target_total = rev_year * 12 + rev_month - 18
    target_year = target_total // 12; target_month = target_total % 12
    if target_month == 0: target_month = 12; target_year -= 1
    mask = ((df["revenue_year"].astype(float).fillna(0).astype(int) == target_year) &
            (df["revenue_month"].astype(float).fillna(0).astype(int) == target_month))
    idx = df.index[mask].tolist()
    if not idx: return np.nan
    if idx[-1] > df.index[-1]: return np.nan
    r_past = df.loc[idx[-1], "month_revenue"]
    if pd.isna(r_past) or r_past <= 0: return np.nan
    ratio = r_now / r_past
    if ratio <= 0: return np.nan
    return (ratio ** (1.0 / 1.5) - 1) * 100


def compute_revenue_ma_cross(df: pd.DataFrame) -> dict:
    """計算營收動能長短線交叉"""
    result = {"signal": "neutral", "ma3": None, "ma6": None, "ma3_slope_up": False}
    if df.empty or "month_revenue" not in df.columns: return result
    if "revenue_year" in df.columns:
        key = df["revenue_year"].astype(str) + "_" + df["revenue_month"].astype(str).str.zfill(2)
        monthly = df.dropna(subset=["month_revenue"]).copy()
        monthly["_key"] = key
        monthly = monthly.groupby("_key").last().reset_index().sort_values("_key")
        s = monthly["month_revenue"].values
    else:
        s = df["month_revenue"].dropna().values
    if len(s) < 6: return result
    s = s.astype(float)
    ma3 = float(np.mean(s[-3:])); ma6 = float(np.mean(s[-6:]))
    slope = ma3 > float(np.mean(s[-4:-1])) if len(s) >= 4 else False
    signal = "neutral"
    if ma3 > ma6 and slope: signal = "bullish"
    elif ma3 < ma6: signal = "bearish"
    return {"signal": signal, "ma3": round(ma3, 2), "ma6": round(ma6, 2), "ma3_slope_up": slope}


def check_operating_margin_from_df(df: pd.DataFrame) -> dict:
    """檢查 Operating_Margin 同比下滑"""
    if df.empty or "Operating_Margin" not in df.columns:
        return {"triggered": False, "current_om": None, "prev_om": None, "drop_pp": None}
    s = df["Operating_Margin"]
    is_new = pd.Series(False, index=df.index) | (s.diff().abs() > 1e-8)
    if pd.notna(s.iloc[0]): is_new.iloc[0] = True
    q = df.loc[is_new, ["Operating_Margin"]].dropna()
    if len(q) < 2: return {"triggered": False, "current_om": None, "prev_om": None, "drop_pp": None}
    cur = q["Operating_Margin"].iloc[-1]
    prev = q["Operating_Margin"].iloc[-(1 + min(4, len(q) - 1))]
    drop = prev - cur
    triggered = drop > OPERATING_MARGIN_QUALITY["drop_threshold_pp"]
    return {"triggered": triggered, "current_om": round(cur, 2), "prev_om": round(prev, 2), "drop_pp": round(drop, 2)}


def apply_industry_debt_bias(row: dict, base_score: int, style: str, industry_median_debt: float = None) -> dict:
    """產業財務去偏誤"""
    if style not in ("value", "dividend"):
        return {"adjusted_score": base_score, "penalty_applied": False, "reason": f"不支援風格：{style}"}
    industry = row.get("Industry", None)
    if industry is None or (isinstance(industry, str) and industry in INDUSTRY_DEBT_BIAS["exclude_sectors"]):
        return {"adjusted_score": base_score, "penalty_applied": False, "reason": "無產業或屬排除產業"}
    debt = row.get("Debt_Ratio", np.nan)
    if pd.isna(debt): return {"adjusted_score": base_score, "penalty_applied": False, "reason": "無負債比"}
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

def get_all_scores(df: pd.DataFrame, start_date: str = None, end_date: str = None, profile: str = None) -> dict:
    """對 DataFrame 中最新一筆資料計算四種風格分數"""
    if df.empty:
        return {
            "short_term": {"total": 0, "breakdown": {}, "details": {}},
            "swing": {"total": 0, "breakdown": {}, "details": {}},
            "value": {"total": 0, "breakdown": {}, "details": {}, "modifiers": {}},
            "dividend": {"total": 0, "breakdown": {}, "details": {}, "modifiers": {}},
        }
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
    if pd.isna(data_years): data_years = 10
    cagr_1_5y = compute_cagr_1_5y(filtered_df)
    revenue_cross = compute_revenue_ma_cross(filtered_df)
    om_quality = check_operating_margin_from_df(filtered_df)
    industry_median_debt = None
    if "Industry" in filtered_df.columns and "Debt_Ratio" in filtered_df.columns:
        industry = latest.get("Industry", None)
        if pd.notna(industry) and isinstance(industry, str):
            idata = filtered_df[filtered_df["Industry"] == industry]["Debt_Ratio"].dropna()
            if len(idata) > 0: industry_median_debt = idata.median()
    if profile in ("chaser", "stable"):
        short_result = score_short_term_by_profile(latest, profile=profile, price_history=filtered_df)
    else:
        short_result = score_short_term(latest)
    swing_result = score_swing(latest, cagr_1_5y)
    value_result = score_value(latest, data_years)
    dividend_result = score_dividend(latest, data_years)
    dq_mod = get_data_quality_modifier(data_years)
    short_total_buy = apply_all_modifiers(short_result["total_buy"], latest, "short_term", dq_mod)
    short_total_sell = apply_all_modifiers(short_result["total_sell"], latest, "short_term", dq_mod)
    swing_total_buy = apply_all_modifiers(swing_result["total_buy"], latest, "swing", dq_mod)
    swing_total_sell = apply_all_modifiers(swing_result["total_sell"], latest, "swing", dq_mod)
    value_total = apply_all_modifiers(value_result["total"], latest, "value", dq_mod)
    dividend_total = apply_all_modifiers(dividend_result["total"], latest, "dividend", dq_mod)
    if om_quality["triggered"]:
        short_total_buy = int(round(short_total_buy * OPERATING_MARGIN_QUALITY["short_term_penalty"]))
        short_total_sell = int(round(short_total_sell * OPERATING_MARGIN_QUALITY["short_term_penalty"]))
        swing_total_buy = int(round(swing_total_buy * OPERATING_MARGIN_QUALITY["swing_penalty"]))
        swing_total_sell = int(round(swing_total_sell * OPERATING_MARGIN_QUALITY["swing_penalty"]))
    value_bias = apply_industry_debt_bias(latest, value_total, "value", industry_median_debt)
    if value_bias["penalty_applied"]: value_total = value_bias["adjusted_score"]
    dividend_bias = apply_industry_debt_bias(latest, dividend_total, "dividend", industry_median_debt)
    if dividend_bias["penalty_applied"]: dividend_total = dividend_bias["adjusted_score"]
    result = {
        "short_term": {"profile": profile, "total": short_total_buy, "total_buy": short_total_buy,
                       "total_sell": short_total_sell, "breakdown": short_result["breakdown"],
                       "details": short_result["details"], "modifiers": {}},
        "swing": {"total": swing_total_buy, "total_buy": swing_total_buy, "total_sell": swing_total_sell,
                  "breakdown": swing_result["breakdown"], "details": swing_result["details"], "modifiers": {}},
        "value": {"total": value_total, "breakdown": value_result["breakdown"],
                  "details": value_result["details"], "modifiers": value_result.get("modifiers", {})},
        "dividend": {"total": dividend_total, "breakdown": dividend_result["breakdown"],
                     "details": dividend_result["details"], "modifiers": dividend_result.get("modifiers", {})},
    }
    cagr_val = round(cagr_1_5y, 2) if pd.notna(cagr_1_5y) else None
    for k in ["short_term", "swing", "value", "dividend"]:
        result[k]["modifiers"]["cagr_1_5y"] = cagr_val
        result[k]["modifiers"]["revenue_ma_cross"] = revenue_cross["signal"]
    for k in ["short_term", "swing"]:
        result[k]["modifiers"]["operating_margin_quality"] = {
            "triggered": om_quality["triggered"], "current_om": om_quality["current_om"],
            "prev_om": om_quality["prev_om"], "drop_pp": om_quality["drop_pp"]}
    result["value"]["modifiers"]["industry_debt_bias"] = {"penalty_applied": value_bias["penalty_applied"], "reason": value_bias["reason"]}
    result["dividend"]["modifiers"]["industry_debt_bias"] = {"penalty_applied": dividend_bias["penalty_applied"], "reason": dividend_bias["reason"]}
    return result


def get_style_label(style: str) -> str:
    labels = {"short_term": "短線", "swing": "波段", "value": "價值", "dividend": "定存"}
    return labels.get(style, style)


def _filter_by_date(df: pd.DataFrame, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    if df.empty: return df
    result = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(result["date"]): result["date"] = pd.to_datetime(result["date"])
    if start_date is not None:
        start = pd.to_datetime(start_date); result = result[result["date"] >= start]
    if end_date is not None:
        end = pd.to_datetime(end_date); result = result[result["date"] <= end]
    return result


def get_historical_scores(df: pd.DataFrame, start_date: str = None, end_date: str = None, freq: str = 'W', profile: str = "stable") -> pd.DataFrame:
    """計算歷史區間內每一個時間點的四種風格分數（walk-forward scoring）。profile: chaser/stable"""
    from datetime import date
    if df.empty: return pd.DataFrame(columns=["date", "short_term_score", "swing_score", "value_score", "dividend_score"])
    result_df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(result_df["date"]): result_df["date"] = pd.to_datetime(result_df["date"])
    result_df = result_df.sort_values("date").reset_index(drop=True)
    today = date.today()
    if end_date is None: end_date = today.strftime("%Y-%m-%d")
    if start_date is None: start_date = f"{today.year}-01-01"
    start_dt = pd.to_datetime(start_date); end_dt = pd.to_datetime(end_date)
    data_years = df.get("Data_Years_Available", pd.Series(10)).iloc[0]
    if pd.isna(data_years): data_years = 10
    eps_col = None
    for col in df.columns:
        if col == "EPS": eps_col = col; break
    records = []
    n = len(result_df)
    min_window = max(5, min(n // 5, 60))
    for i in range(min_window - 1, n):
        window = result_df.iloc[:i + 1].copy()
        current_row = window.iloc[-1]
        current_date = current_row["date"]
        if current_date < start_dt or current_date > end_dt: continue
        pe_pct = _compute_percentile_in_window(window, "pe_ratio", eps_col)
        pb_pct = _compute_percentile_in_window(window, "pb_ratio")
        row_dict = current_row.to_dict()
        if pd.notna(pe_pct): row_dict["PE_Percentile"] = pe_pct
        if pd.notna(pb_pct): row_dict["PB_Percentile"] = pb_pct
        cagr_1_5y = compute_cagr_1_5y(window)
        om_quality = check_operating_margin_from_df(window)
        industry_median_debt = None
        if "Industry" in window.columns and "Debt_Ratio" in window.columns:
            industry = row_dict.get("Industry", None)
            if pd.notna(industry) and isinstance(industry, str):
                idata = window[window["Industry"] == industry]["Debt_Ratio"].dropna()
                if len(idata) > 0: industry_median_debt = idata.median()
        short_result = score_short_term_by_profile(row_dict, profile=profile, price_history=window)
        swing_result = score_swing(row_dict, cagr_1_5y)
        value_result = score_value(row_dict, data_years)
        dividend_result = score_dividend(row_dict, data_years)
        dq_mod = get_data_quality_modifier(data_years)
        short_total_buy = apply_all_modifiers(short_result["total_buy"], row_dict, "short_term", dq_mod)
        short_total_sell = apply_all_modifiers(short_result["total_sell"], row_dict, "short_term", dq_mod)
        swing_total_buy = apply_all_modifiers(swing_result["total_buy"], row_dict, "swing", dq_mod)
        swing_total_sell = apply_all_modifiers(swing_result["total_sell"], row_dict, "swing", dq_mod)
        value_total = apply_all_modifiers(value_result["total"], row_dict, "value", dq_mod)
        dividend_total = apply_all_modifiers(dividend_result["total"], row_dict, "dividend", dq_mod)
        if om_quality["triggered"]:
            short_total_buy = int(round(short_total_buy * OPERATING_MARGIN_QUALITY["short_term_penalty"]))
            short_total_sell = int(round(short_total_sell * OPERATING_MARGIN_QUALITY["short_term_penalty"]))
            swing_total_buy = int(round(swing_total_buy * OPERATING_MARGIN_QUALITY["swing_penalty"]))
            swing_total_sell = int(round(swing_total_sell * OPERATING_MARGIN_QUALITY["swing_penalty"]))
        value_bias = apply_industry_debt_bias(row_dict, value_total, "value", industry_median_debt)
        if value_bias["penalty_applied"]: value_total = value_bias["adjusted_score"]
        dividend_bias = apply_industry_debt_bias(row_dict, dividend_total, "dividend", industry_median_debt)
        if dividend_bias["penalty_applied"]: dividend_total = dividend_bias["adjusted_score"]
        records.append({"date": current_date, "short_term_score": short_total_buy,
                        "short_term_score_buy": short_total_buy, "short_term_score_sell": short_total_sell,
                        "swing_score": swing_total_buy, "swing_score_buy": swing_total_buy,
                        "swing_score_sell": swing_total_sell, "value_score": value_total,
                        "dividend_score": dividend_total})
    if not records: return pd.DataFrame(columns=["date", "short_term_score", "swing_score", "value_score", "dividend_score"])
    scores_df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    if freq != 'D':
        scores_df["_freq_key"] = scores_df["date"].dt.to_period(freq)
        scores_df = scores_df.groupby("_freq_key").last().reset_index(drop=True)
        scores_df = scores_df.drop(columns=["_freq_key"], errors="ignore")
    return scores_df


if __name__ == "__main__":
    print("scorer.py — 五級評分制 + 回測功能")