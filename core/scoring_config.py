"""
core/scoring_config.py
評分權重與門檻設定檔 — 單一事實來源

v2.1 校準版變更：
1. 新增 inst_20d_surrogate_* 門檻（隔離的 20 日代理指標）
2. 所有 24 子項補齊 _poor 檔位
3. 常數搬移：FINANCE_SECTORS, FINANCE_STOCK_IDS, RSI_OVERHEAT_* 搬至此處
"""

# ============================================================
# 常數（單一事實來源，從 scorer.py 搬遷至此）
# ============================================================

# RSI 過熱設定
RSI_OVERHEAT_THRESHOLD = 88
RSI_OVERHEAT_PENALTY = -10

# 金融業排除清單
FINANCE_SECTORS = ['金融業']
FINANCE_STOCK_IDS = [
    '2881', '2882', '2883', '2884', '2885', '2886', '2887', '2888',
    '2889', '2890', '2891', '2892',
    '5801', '5802', '5815', '5820', '5836', '5840', '5854',
    '5863', '5871', '5876', '5880', '6005',
]


# ============================================================
# 通用五級評分門檻
# ============================================================
# 每個子項的 score_* 函式回傳 0-100 分
# 五級映射：100(excellent) / 85(good) / 70(normal) / 50(weak) / 0(poor)

# ===== 短線評分權重（總和 100%） =====
SHORT_TERM_WEIGHTS = {
    "trend_structure": 0.20,
    "momentum": 0.20,
    "volume": 0.20,
    "institutional": 0.15,
    "chip": 0.15,
    "risk": 0.10,
}

# 短線雙軌權重（總和皆為 1.0）
SHORT_TERM_BUY_WEIGHTS = {
    "trend_structure": 0.15,
    "momentum": 0.25,
    "volume": 0.25,
    "institutional": 0.15,
    "chip": 0.10,
    "risk": 0.10,
}
SHORT_TERM_SELL_WEIGHTS = {
    "trend_structure": 0.25,
    "momentum": 0.15,
    "volume": 0.10,
    "institutional": 0.05,
    "chip": 0.15,
    "risk": 0.30,
}

SHORT_TERM_THRESHOLDS = {
    # 趨勢結構
    "ma_alignment_excellent": 3,
    "ma_alignment_good": 2,
    "ma_alignment_normal": 1,
    "ma_alignment_weak": 0,
    "ma_alignment_poor": -1,
    "above_ma_excellent": 4,
    "above_ma_good": 3,
    "above_ma_normal": 2,
    "above_ma_weak": 1,
    "above_ma_poor": 0,

    # 成交量結構
    "volume_ratio_excellent": 2.0,
    "volume_ratio_good": 1.5,
    "volume_ratio_normal": 1.2,
    "volume_ratio_weak": 1.0,
    "volume_ratio_poor": 0.5,
    "volume_surge_excellent": 3.0,
    "volume_surge_good": 2.0,
    "volume_surge_normal": 1.5,
    "volume_surge_weak": 1.0,
    "volume_surge_poor": 0.5,

    # 法人籌碼
    "inst_5d_excellent": 5000000,
    "inst_5d_good": 1000000,
    "inst_5d_normal": 0,
    "inst_5d_weak": -1000000,
    "inst_5d_poor": -5000000,
    # 專用 20 日代理門檻（與 10 日門檻隔離）— 約放大 1.5~1.8 倍
    "inst_20d_surrogate_excellent": 15000000,
    "inst_20d_surrogate_good": 3500000,
    "inst_20d_surrogate_normal": 0,
    "inst_20d_surrogate_weak": -3500000,
    "inst_20d_surrogate_poor": -15000000,
    "foreign_excellent": 3000000,
    "foreign_good": 500000,
    "foreign_normal": 0,
    "foreign_weak": -500000,
    "foreign_poor": -3000000,
    "trust_excellent": 1000000,
    "trust_good": 200000,
    "trust_normal": 0,
    "trust_weak": -200000,
    "trust_poor": -1000000,

    # 籌碼健康
    "margin_change_excellent": -5,
    "margin_change_good": 0,
    "margin_change_normal": 5,
    "margin_change_weak": 10,
    "margin_change_poor": 20,
    "short_change_excellent": 5,
    "short_change_good": 0,
    "short_change_normal": -5,
    "short_change_weak": -10,
    "short_change_poor": -20,
    "sbl_excellent": -100000,
    "sbl_good": 0,
    "sbl_normal": 100000,
    "sbl_weak": 500000,
    "sbl_poor": 1000000,

    # 波動風險（反向評分：越低越好）
    "bias_excellent": 0.03,
    "bias_good": 0.05,
    "bias_normal": 0.08,
    "bias_weak": 0.12,
    "bias_poor": 0.20,
}

# ===== 波段評分權重（總和 100%） =====
SWING_WEIGHTS = {
    "revenue_momentum": 0.25,
    "mid_trend": 0.20,
    "institutional_trend": 0.20,
    "earnings_growth": 0.15,
    "valuation": 0.10,
    "catalyst": 0.10,
}

# 波段雙軌權重（總和皆為 1.0）
SWING_BUY_WEIGHTS = {
    "revenue_momentum": 0.25,
    "mid_trend": 0.20,
    "institutional_trend": 0.20,
    "earnings_growth": 0.15,
    "valuation": 0.05,
    "catalyst": 0.15,
}
SWING_SELL_WEIGHTS = {
    "revenue_momentum": 0.20,
    "mid_trend": 0.30,
    "institutional_trend": 0.10,
    "earnings_growth": 0.15,
    "valuation": 0.15,
    "catalyst": 0.10,
}

SWING_THRESHOLDS = {
    # 營收動能
    "rev_yoy_excellent": 30,
    "rev_yoy_good": 20,
    "rev_yoy_normal": 10,
    "rev_yoy_weak": 0,
    "rev_yoy_poor": -20,
    "rev_mom_excellent": 5,
    "rev_mom_good": 2,
    "rev_mom_normal": 0,
    "rev_mom_weak": -5,
    "rev_mom_poor": -10,
    "rev_accel_true": 1,

    # 1.5Y-CAGR
    "cagr_1_5y_excellent": 15,
    "cagr_1_5y_good": 8,
    "cagr_1_5y_normal": 0,
    "cagr_1_5y_weak": -8,
    "cagr_1_5y_poor": -50,

    # 籌碼趨勢
    "inst_trend_slope_excellent": 50000,
    "inst_trend_slope_good": 0,
    "inst_trend_slope_normal": -25000,
    "inst_trend_slope_weak": -50000,
    "inst_trend_slope_poor": -100000,
    # 20 日累計法人（常規值）
    "inst_20d_net_excellent": 10000000,
    "inst_20d_net_good": 2000000,
    "inst_20d_net_normal": 0,
    "inst_20d_net_weak": -2000000,
    "inst_20d_net_poor": -10000000,

    # 獲利成長
    "ttm_eps_excellent": 15,
    "ttm_eps_good": 8,
    "ttm_eps_normal": 3,
    "ttm_eps_weak": 0,
    "ttm_eps_poor": -5,
    "eps_yoy_excellent": 30,
    "eps_yoy_good": 15,
    "eps_yoy_normal": 5,
    "eps_yoy_weak": 0,
    "eps_yoy_poor": -20,

    # 估值位置（反向評分）
    "pe_percentile_excellent": 20,
    "pe_percentile_good": 40,
    "pe_percentile_normal": 60,
    "pe_percentile_weak": 80,
    "pe_percentile_poor": 95,
    "pb_percentile_excellent": 20,
    "pb_percentile_good": 40,
    "pb_percentile_normal": 60,
    "pb_percentile_weak": 80,
    "pb_percentile_poor": 95,
}

# ===== 價值評分權重（總和 100%） =====
VALUE_WEIGHTS = {
    "valuation_safety": 0.15,
    "profit_quality": 0.20,
    "growth_ability": 0.30,
    "financial_safety": 0.15,
    "cash_flow_quality": 0.10,
    "shareholder_return": 0.10,
}

VALUE_THRESHOLDS = {
    # 估值安全（反向評分）
    "pe_percentile_excellent": 20,
    "pe_percentile_good": 40,
    "pe_percentile_normal": 60,
    "pe_percentile_weak": 80,
    "pe_percentile_poor": 95,
    "pb_percentile_excellent": 20,
    "pb_percentile_good": 40,
    "pb_percentile_normal": 60,
    "pb_percentile_weak": 80,
    "pb_percentile_poor": 95,

    # 獲利品質
    "roe_excellent": 20,
    "roe_good": 15,
    "roe_normal": 8,
    "roe_weak": 3,
    "roe_poor": 0,
    "roa_excellent": 10,
    "roa_good": 5,
    "roa_normal": 2,
    "roa_weak": 0,
    "roa_poor": -2,
    "gm_excellent": 50,
    "gm_good": 30,
    "gm_normal": 15,
    "gm_weak": 5,
    "gm_poor": 0,

    # 成長能力
    "ttm_eps_excellent": 15,
    "ttm_eps_good": 8,
    "ttm_eps_normal": 3,
    "ttm_eps_weak": 0,
    "ttm_eps_poor": -5,
    "rev_yoy_excellent": 20,
    "rev_yoy_good": 10,
    "rev_yoy_normal": 5,
    "rev_yoy_weak": 0,
    "rev_yoy_poor": -20,

    # 1.5Y-CAGR
    "cagr_1_5y_excellent": 15,
    "cagr_1_5y_good": 8,
    "cagr_1_5y_normal": 0,
    "cagr_1_5y_weak": -8,
    "cagr_1_5y_poor": -50,

    # 財務安全（反向評分）
    "debt_ratio_excellent": 30,
    "debt_ratio_good": 45,
    "debt_ratio_normal": 60,
    "debt_ratio_weak": 75,
    "debt_ratio_poor": 90,
    "current_ratio_excellent": 2.5,
    "current_ratio_good": 2.0,
    "current_ratio_normal": 1.5,
    "current_ratio_weak": 1.0,
    "current_ratio_poor": 0.5,

    # 現金流品質
    "ttm_fcf_excellent": 10000000000,
    "ttm_fcf_good": 1000000000,
    "ttm_fcf_normal": 0,
    "ttm_fcf_weak": -1000000000,
    "ttm_fcf_poor": -5000000000,
    "ocf_excellent": 20000000000,
    "ocf_good": 5000000000,
    "ocf_normal": 0,
    "ocf_weak": -5000000000,
    "ocf_poor": -20000000000,

    # 股東報酬
    "div_yield_excellent": 5,
    "div_yield_good": 3,
    "div_yield_normal": 1.5,
    "div_yield_weak": 0.5,
    "div_yield_poor": 0,
}

# ===== 定存評分權重（總和 100%） =====
DIVIDEND_WEIGHTS = {
    "dividend_record": 0.25,
    "dividend_quality": 0.20,
    "cash_flow": 0.20,
    "financial_safety": 0.15,
    "profit_stability": 0.10,
    "long_term_growth": 0.10,
}

DIVIDEND_THRESHOLDS = {
    # 配息紀錄
    "div_continuity_excellent": 10,
    "div_continuity_good": 7,
    "div_continuity_normal": 5,
    "div_continuity_weak": 3,
    "div_continuity_poor": 1,

    # 配息品質
    "payout_ratio_excellent": 60,
    "payout_ratio_good_low": 40,
    "payout_ratio_good_high": 70,
    "payout_ratio_normal_low": 30,
    "payout_ratio_normal_high": 80,
    "payout_ratio_weak_low": 20,
    "payout_ratio_weak_high": 90,
    "eps_cover_excellent": 2.0,
    "eps_cover_good": 1.5,
    "eps_cover_normal": 1.0,
    "eps_cover_weak": 0.5,
    "eps_cover_poor": 0,

    # 現金流（反向評分時直接使用，不另加 _poor）
    "fcf_cover_excellent": 2.0,
    "fcf_cover_good": 1.5,
    "fcf_cover_normal": 1.0,
    "fcf_cover_weak": 0.5,
    "fcf_cover_poor": 0,

    # 財務安全（反向評分）
    "debt_ratio_excellent": 30,
    "debt_ratio_good": 45,
    "debt_ratio_normal": 60,
    "debt_ratio_weak": 75,
    "debt_ratio_poor": 90,
    "interest_cover_excellent": 10,
    "interest_cover_good": 5,
    "interest_cover_normal": 3,
    "interest_cover_weak": 1,
    "interest_cover_poor": 0,

    # 獲利穩定（反向評分）
    "roe_std_excellent": 3,
    "roe_std_good": 5,
    "roe_std_normal": 8,
    "roe_std_weak": 12,
    "roe_std_poor": 20,
    "eps_std_excellent": 2,
    "eps_std_good": 4,
    "eps_std_normal": 6,
    "eps_std_weak": 10,
    "eps_std_poor": 20,

    # 長期成長
    "rev_cagr_excellent": 15,
    "rev_cagr_good": 10,
    "rev_cagr_normal": 5,
    "rev_cagr_weak": 0,
    "rev_cagr_poor": -20,
    "eps_yoy_excellent": 30,
    "eps_yoy_good": 15,
    "eps_yoy_normal": 5,
    "eps_yoy_weak": 0,
    "eps_yoy_poor": -20,
}


# ============================================================
# Data Quality Modifier
# ============================================================
DATA_QUALITY_MODIFIER = {
    "excellent": {"min_years": 8, "modifier": 1.00},
    "good": {"min_years": 5, "modifier": 0.95},
    "normal": {"min_years": 3, "modifier": 0.85},
    "poor": {"min_years": 0, "modifier": 0.70},
}


# ============================================================
# Risk Modifier
# ============================================================
# v2.1 校準版：僅包含非 RSI 的風險因子（RSI 已移至 score_volatility_risk）
RISK_PENALTY = {
    "debt_too_high": {"threshold": 70, "penalty": -10},
    "eps_negative": {"penalty": -15},
    "payout_unsustainable": {"penalty": -15},
    "major_negative": {"penalty": -20},
}

RISK_BONUS = {
    "rsi_oversold": {"threshold": 30, "bonus": 5},
    "low_debt": {"threshold": 20, "bonus": 5},
    "strong_momentum": {"threshold": 1, "bonus": 5},
}


# ============================================================
# 營收動能長短線交叉
# ============================================================
REVENUE_MA_CROSS = {
    "ma3_window": 3,
    "ma6_window": 6,
}


# ============================================================
# 雙重質檢與去偏誤 Modifier 防線
# ============================================================

OPERATING_MARGIN_QUALITY = {
    "drop_threshold_pp": 2.0,
    "swing_penalty": 0.8,
    "short_term_penalty": 0.8,
}

INDUSTRY_DEBT_BIAS = {
    "exclude_sectors": ["金融業", "營建業"],
    "debt_ratio_multiplier": 1.2,
    "value_penalty": 0.85,
    "dividend_penalty": 0.85,
}


# ============================================================
# 雙分析師短線權重（v3.0 新增，僅使用 FinMind 免費版可得資料）
# ============================================================

# 激進型分析師
CHASER_BUY_WEIGHTS = {
    "momentum": 0.30,
    "inertia_break": 0.25,
    "volume": 0.20,
    "trend_structure": 0.10,
    "risk": 0.05,
    "chip_concentration": 0.05,
    "institutional": 0.05,
    "chip": 0.00,
}
CHASER_SELL_WEIGHTS = {
    "momentum": 0.25,
    "inertia_break": 0.35,
    "volume": 0.15,
    "trend_structure": 0.10,
    "risk": 0.10,
    "chip_concentration": 0.00,
    "institutional": 0.05,
    "chip": 0.00,
}

# 穩重型分析師
STABLE_BUY_WEIGHTS = {
    "trend_structure": 0.35,
    "institutional": 0.20,
    "chip_concentration": 0.20,
    "volume": 0.10,
    "inertia_break": 0.05,
    "momentum": 0.05,
    "chip": 0.05,
    "risk": 0.00,
}
STABLE_SELL_WEIGHTS = {
    "trend_structure": 0.35,
    "institutional": 0.15,
    "chip_concentration": 0.25,
    "volume": 0.10,
    "inertia_break": 0.10,
    "momentum": 0.05,
    "chip": 0.00,
    "risk": 0.00,
}

STYLE_PROFILES = {
    "chaser": {"buy": CHASER_BUY_WEIGHTS, "sell": CHASER_SELL_WEIGHTS},
    "stable": {"buy": STABLE_BUY_WEIGHTS, "sell": STABLE_SELL_WEIGHTS},
}

# 慣性突破/破壞門檻
INERTIA_THRESHOLDS = {
    "high_n_days": 10,
    "low_n_days": 10,
    "consec_days_required": 3,
}

# 籌碼密集區（多日 POC 代理）參數
CHIP_CONCENTRATION_THRESHOLDS = {
    "lookback_days": 60,
    "num_bins": 30,
    "dist_excellent": 5.0,
    "dist_good": 1.0,
    "dist_normal": -2.0,
    "dist_weak": -5.0,
}