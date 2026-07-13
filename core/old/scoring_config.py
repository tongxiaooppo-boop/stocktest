"""
core/scoring_config.py
評分權重與門檻設定檔 v4.1

v4.1 變更：
- 短線 MACD／突破前高／爆量評分門檻改讀 config（原寫死在程式碼）
- 波段 Revenue_Accelerating 門檻改為二元評分（原為次數門檻，與布林值不符）
- 定存長期成長子項 EPS CAGR 改用真實 EPS 年成長率（原用 TTM_EPS 絕對值冒充）

v4.2 新增（核心防禦運算重構）：
- 新增 1.5Y-CAGR 五級閾值
- 新增營收動能 3MA vs 6MA 長短線交叉設定
- 新增雙重質檢與去偏誤 Modifier 防線設定
"""

# ============================================================
# 通用五級評分門檻（每個子項共用）
# ============================================================
# 每個子項的 score_* 函式回傳 0-100 分
# 再由 apply_weight(score, weight) 轉換為加權分數

# ===== 短線評分權重（總和 100%） =====
SHORT_TERM_WEIGHTS = {
    "trend_structure": 0.20,   # 趨勢結構
    "momentum": 0.20,          # 動能強度
    "volume": 0.20,            # 成交量結構
    "institutional": 0.15,     # 法人籌碼
    "chip": 0.15,              # 籌碼健康
    "risk": 0.10,              # 波動風險
}

SHORT_TERM_THRESHOLDS = {
    # 趨勢結構
    "ma_alignment_excellent": 3,     # 3條均線多頭排列
    "ma_alignment_good": 2,
    "ma_alignment_normal": 1,
    "ma_alignment_weak": 0,
    "above_ma_excellent": 4,         # 站上4條均線
    "above_ma_good": 3,
    "above_ma_normal": 2,
    "above_ma_weak": 1,
    
    # 動能強度
    "rsi_oversold": 30,
    "rsi_mid": 50,
    "rsi_strong": 70,
    "rsi_overheat": 80,
    "macd_excellent": 1,
    "macd_good": 0,
    "macd_normal": -5,
    "macd_weak": -10,
    "break_high_excellent": 3,
    "break_high_good": 2,
    "break_high_normal": 1,
    
    # 成交量結構
    "volume_ratio_excellent": 2.0,
    "volume_ratio_good": 1.5,
    "volume_ratio_normal": 1.2,
    "volume_ratio_weak": 1.0,
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
    "inst_10d_excellent": 10000000,
    "inst_10d_good": 2000000,
    "inst_10d_normal": 0,
    "inst_10d_weak": -2000000,
    "foreign_excellent": 3000000,
    "foreign_good": 500000,
    "foreign_normal": 0,
    "foreign_weak": -500000,
    "trust_excellent": 1000000,
    "trust_good": 200000,
    "trust_normal": 0,
    "trust_weak": -200000,
    
    # 籌碼健康
    "margin_change_excellent": -5,
    "margin_change_good": 0,
    "margin_change_normal": 5,
    "margin_change_weak": 10,
    "short_change_excellent": 5,
    "short_change_good": 0,
    "short_change_normal": -5,
    "short_change_weak": -10,
    "sbl_excellent": -100000,
    "sbl_good": 0,
    "sbl_normal": 100000,
    "sbl_weak": 500000,
    
    # 波動風險（反向評分：越低越好）
    "rsi_overheat_penalty": 80,
    "bias_excellent": 0.03,
    "bias_good": 0.05,
    "bias_normal": 0.08,
    "bias_weak": 0.12,
    "bias_poor": 0.15,
    "atr_excellent": 0.02,
    "atr_good": 0.03,
    "atr_normal": 0.05,
    "atr_weak": 0.08,
}

# ===== 波段評分權重（總和 100%） =====
SWING_WEIGHTS = {
    "revenue_momentum": 0.25,    # 營收動能
    "mid_trend": 0.20,           # 中期趨勢
    "institutional_trend": 0.20, # 籌碼趨勢
    "earnings_growth": 0.15,     # 獲利成長
    "valuation": 0.10,           # 估值位置
    "catalyst": 0.10,            # 催化因子
}

SWING_THRESHOLDS = {
    # 營收動能
    "rev_yoy_excellent": 30,
    "rev_yoy_good": 20,
    "rev_yoy_normal": 10,
    "rev_yoy_weak": 0,
    "rev_mom_excellent": 5,
    "rev_mom_good": 2,
    "rev_mom_normal": 0,
    "rev_mom_weak": -5,
    "rev_accel_true": 1,
    
    # v4.2 新增：1.5Y-CAGR 閾值
    "cagr_1_5y_excellent": 15,
    "cagr_1_5y_good": 8,
    "cagr_1_5y_normal": 0,
    "cagr_1_5y_weak": -8,
    "cagr_1_5y_poor": -50,
    
    # 中期趨勢
    "above_ma20_excellent": 1,
    "above_ma60_excellent": 1,
    "ma20_bias_excellent": 0.03,
    "ma20_bias_good": 0.05,
    "ma20_bias_normal": 0.08,
    "ma20_bias_weak": 0.12,
    "ma60_bias_excellent": 0.03,
    "ma60_bias_good": 0.08,
    "ma60_bias_normal": 0.15,
    "ma60_bias_weak": 0.20,
    
    # 籌碼趨勢
    "inst_20d_excellent": 10000000,
    "inst_20d_good": 2000000,
    "inst_20d_normal": 0,
    "inst_20d_weak": -2000000,
    "inst_20d_poor": -10000000,
    "sbl_trend_excellent": -500000,
    "sbl_trend_good": 0,
    "sbl_trend_normal": 500000,
    "sbl_trend_weak": 1000000,
    "inst_trend_excellent": 3,
    "inst_trend_good": 2,
    "inst_trend_normal": 1,
    
    # 獲利成長
    "ttm_eps_excellent": 15,
    "ttm_eps_good": 8,
    "ttm_eps_normal": 3,
    "ttm_eps_weak": 0,
    "eps_yoy_excellent": 30,
    "eps_yoy_good": 15,
    "eps_yoy_normal": 5,
    "eps_yoy_weak": 0,
    
    # 估值位置（反向評分：百分位越低越好）
    "pe_percentile_excellent": 20,
    "pe_percentile_good": 40,
    "pe_percentile_normal": 60,
    "pe_percentile_weak": 80,
    "pb_percentile_excellent": 20,
    "pb_percentile_good": 40,
    "pb_percentile_normal": 60,
    "pb_percentile_weak": 80,
    
    # 催化因子
    "catalyst_positive": 1,
}

# ===== 價值評分權重（總和 100%） =====
# v5.1：valuation_safety 過高導致強勢股被低估，調降權重改配給 growth_ability
VALUE_WEIGHTS = {
    "valuation_safety": 0.15,    # 估值安全（原 0.25，調降避免強勢股被低估）
    "profit_quality": 0.20,      # 獲利品質
    "growth_ability": 0.30,      # 成長能力（原 0.20，吸收 valuation_safety 釋出的權重）
    "financial_safety": 0.15,    # 財務安全
    "cash_flow_quality": 0.10,   # 現金流品質
    "shareholder_return": 0.10,  # 股東報酬
}

VALUE_THRESHOLDS = {
    # 估值安全（反向評分：百分位越低越好）
    "pe_percentile_excellent": 20,
    "pe_percentile_good": 40,
    "pe_percentile_normal": 60,
    "pe_percentile_weak": 80,
    "pb_percentile_excellent": 20,
    "pb_percentile_good": 40,
    "pb_percentile_normal": 60,
    "pb_percentile_weak": 80,
    
    # 獲利品質
    "roe_excellent": 20,
    "roe_good": 15,
    "roe_normal": 8,
    "roe_weak": 3,
    "roa_excellent": 10,
    "roa_good": 5,
    "roa_normal": 2,
    "roa_weak": 0,
    "gm_excellent": 50,
    "gm_good": 30,
    "gm_normal": 15,
    "gm_weak": 5,
    
    # 成長能力
    "ttm_eps_excellent": 15,
    "ttm_eps_good": 8,
    "ttm_eps_normal": 3,
    "ttm_eps_weak": 0,
    "rev_yoy_excellent": 20,
    "rev_yoy_good": 10,
    "rev_yoy_normal": 5,
    "rev_yoy_weak": 0,
    
    # v4.2 新增：1.5Y-CAGR 閾值（價值風格共用）
    "cagr_1_5y_excellent": 15,
    "cagr_1_5y_good": 8,
    "cagr_1_5y_normal": 0,
    "cagr_1_5y_weak": -8,
    "cagr_1_5y_poor": -50,
    
    # 財務安全（反向評分：負債比越低越好）
    "debt_ratio_excellent": 30,
    "debt_ratio_good": 45,
    "debt_ratio_normal": 60,
    "debt_ratio_weak": 75,
    "current_ratio_excellent": 2.5,
    "current_ratio_good": 2.0,
    "current_ratio_normal": 1.5,
    "current_ratio_weak": 1.0,
    
    # 現金流品質
    "ttm_fcf_excellent": 10000000000,
    "ttm_fcf_good": 1000000000,
    "ttm_fcf_normal": 0,
    "ttm_fcf_weak": -1000000000,
    "ocf_excellent": 20000000000,
    "ocf_good": 5000000000,
    "ocf_normal": 0,
    "ocf_weak": -5000000000,
    
    # 股東報酬
    "div_yield_excellent": 5,
    "div_yield_good": 3,
    "div_yield_normal": 1.5,
    "div_yield_weak": 0.5,
    "dividend_excellent": 1,
}

# ===== 定存評分權重（總和 100%） =====
DIVIDEND_WEIGHTS = {
    "dividend_record": 0.25,     # 配息紀錄
    "dividend_quality": 0.20,    # 配息品質
    "cash_flow": 0.20,           # 現金流
    "financial_safety": 0.15,   # 財務安全
    "profit_stability": 0.10,   # 獲利穩定
    "long_term_growth": 0.10,   # 長期成長
}

DIVIDEND_THRESHOLDS = {
    # 配息紀錄
    "div_continuity_excellent": 10,
    "div_continuity_good": 7,
    "div_continuity_normal": 5,
    "div_continuity_weak": 3,
    
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
    
    # 現金流
    "fcf_cover_excellent": 2.0,
    "fcf_cover_good": 1.5,
    "fcf_cover_normal": 1.0,
    "fcf_cover_weak": 0.5,
    
    # 財務安全（反向評分：負債比越低越好）
    "debt_ratio_excellent": 30,
    "debt_ratio_good": 45,
    "debt_ratio_normal": 60,
    "debt_ratio_weak": 75,
    "interest_cover_excellent": 10,
    "interest_cover_good": 5,
    "interest_cover_normal": 3,
    "interest_cover_weak": 1,
    
    # 獲利穩定（反向評分：波動越低越好）
    "roe_std_excellent": 3,
    "roe_std_good": 5,
    "roe_std_normal": 8,
    "roe_std_weak": 12,
    "eps_std_excellent": 2,
    "eps_std_good": 4,
    "eps_std_normal": 6,
    "eps_std_weak": 10,
    
    # 長期成長
    "rev_cagr_excellent": 15,
    "rev_cagr_good": 10,
    "rev_cagr_normal": 5,
    "rev_cagr_weak": 0,
    "eps_yoy_excellent": 30,
    "eps_yoy_good": 15,
    "eps_yoy_normal": 5,
    "eps_yoy_weak": 0,
}

# ===== Data Quality Modifier =====
DATA_QUALITY_MODIFIER = {
    "excellent": {"min_years": 8, "modifier": 1.00},
    "good": {"min_years": 5, "modifier": 0.95},
    "normal": {"min_years": 3, "modifier": 0.85},
    "poor": {"min_years": 0, "modifier": 0.70},
}

# ===== Risk Modifier Penalty =====
RISK_PENALTY = {
    "rsi_overheat": {"threshold": 80, "penalty": -10},
    "debt_too_high": {"threshold": 70, "penalty": -10},
    "eps_negative": {"penalty": -15},
    "payout_unsustainable": {"penalty": -15},
    "major_negative": {"penalty": -20},
}

# ===== Risk Modifier Bonus =====
RISK_BONUS = {
    "rsi_oversold": {"threshold": 30, "bonus": 5},
    "low_debt": {"threshold": 20, "bonus": 5},
    "strong_momentum": {"threshold": 1, "bonus": 5},
}


# ============================================================
# v4.2 新增：營收動能長短線交叉（3MA vs 6MA）
# ============================================================
REVENUE_MA_CROSS = {
    "ma3_window": 3,    # 3個月移動平均
    "ma6_window": 6,    # 6個月移動平均
}


# ============================================================
# v4.2 新增：雙重質檢與去偏誤 Modifier 防線
# ============================================================

# 【波段/短線：流血去庫存質檢】
# 檢查最新一季 Operating_Margin 較去年同期下滑 > 2pp
OPERATING_MARGIN_QUALITY = {
    "drop_threshold_pp": 2.0,
    "swing_penalty": 0.8,
    "short_term_penalty": 0.8,
}

# 【價值/定存：產業財務去偏誤】
# 排除清單：金融業、營建業
EXCLUDE_SECTORS = ['金融業', '營建業']

INDUSTRY_DEBT_BIAS = {
    "exclude_sectors": ["金融業", "營建業"],
    "debt_ratio_multiplier": 1.2,
    "value_penalty": 0.85,
    "dividend_penalty": 0.85,
}