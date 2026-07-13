"""
core/scorer.py v5.2
四種風格打分 — 五級評分制 + 回測功能

四維評分權重總覽（請以 scoring_config.py 為準）

一、短線風格 (short_term) —— 權重合計 100%
  trend_structure (趨勢結構)  20%  ← 均線排列(60%) + 站上均線數(40%)
  momentum        (動能強度)  20%  ← RSI(40%) + MACD(35%) + 突破前高(25%)
  volume          (成交量結構) 20%  ← Volume Ratio(60%) + 爆量幅度(40%)
  institutional   (法人籌碼)  15%  ← 5日法人(35%) + 10日法人(25%) + 外資(25%) + 投信(15%)
  chip            (籌碼健康)  15%  ← 融資(40%) + 融券(30%) + 借券(30%) [反向]
  risk            (波動風險)  10%  ← 乖離率(40%) + ATR(30%) + RSI過熱(30%) [反向]
  ★ 額外調整：Risk Modifier (RSI過熱扣分門檻88、負債過高扣分)
  ★ v5.1：RSI過熱門檻放寬 80→88
  ★ v5.2：Parabolic 模式豁免 RSI/乖離率扣分 + 5MA 移動止損保底 50

二、波段風格 (swing) —— 權重合計 100%
  revenue_momentum    (營收動能)  25%
  mid_trend           (中期趨勢)  20%
  institutional_trend (籌碼趨勢)  20%
  earnings_growth     (獲利成長)  15%
  valuation           (估值位置)  10%  ← PE_Percentile(60%) + PB_Percentile(40%) [反向]
  catalyst            (催化因子)  10%
  ★ 額外調整：Risk Modifier + 流血去庫存質檢(打8折) + CAGR子權重調整
  ★ v5.2：Parabolic 模式豁免 RSI/乖離率扣分 + 5MA 移動止損保底 50

三、價值風格 (value) —— 權重合計 100%
  valuation_safety    (估值安全)  15%  ← PE_Percentile(60%) + PB_Percentile(40%) [反向]
  profit_quality      (獲利品質)  20%  ← ROE(45%) + ROA(25%) + 毛利率(30%)
  growth_ability      (成長能力)  30%  ← v5.1:原20%,吸收估值釋出權重
  financial_safety    (財務安全)  15%  ← 負債比(60%) + 流動比率(40%) [反向]
  cash_flow_quality   (現金流品質) 10%
  shareholder_return  (股東報酬)  10%
  ★ v5.1：valuation_safety 25%→15%, growth_ability 20%→30%
  ★ 額外調整：Data Quality Modifier + Risk Modifier + 產業去偏誤(打85折)
  ★ 金融業防錯：負債比/現金流直接給滿分

四、定存風格 (dividend) —— 權重合計 100%
  dividend_record     (配息紀錄)  25%  ← 連續配息年數
  dividend_quality    (配息品質)  20%  ← 配息率(60%) + EPS Cover(40%)
  cash_flow           (現金流)   20%  ← FCF覆蓋率
  financial_safety    (財務安全)  15%  ← 負債比(60%) + 利息保障倍數(40%) [反向]
  profit_stability    (獲利穩定)  10%  ← ROE波動(50%) + EPS波動(50%) [反向]
  long_term_growth    (長期成長)  10%  ← Revenue CAGR(50%) + EPS YoY(50%)
  ★ 額外調整：Data Quality Modifier + Risk Modifier + 產業去偏誤(打85折)
  ★ 金融業防錯：負債比直接給滿分

通用規則
- 五級評分：Excellent=100, Good=80, Normal=60, Weak=30, Poor=0
- 反向評分：數值越低越好（用於負債比、波動、百分位）
- Risk Modifier：計算子項加權後，額外加減分（±10~15分）
- Data Quality Modifier：依資料年數打0.70~1.00折
- 流血去庫存質檢：營益率年減>2pp時，短線/波段打8折
- 產業去偏誤：負債比>同業中位數×1.2時，價值/定存打85折
- v5.1 金融業防錯：金融股跳過負債比/營業現金流評分，直接給基準滿分

v5.0 新增：
- get_all_scores() 加入 start_date / end_date 參數
- 新增 get_historical_scores()：walk-forward 歷史回測評分，避免 look-ahead bias
- 新增 _compute_percentile_in_window()：在滾動視窗內重新計算百分位，保證前瞻無偏

v5.2 新增：
- 極端動能保護機制（Parabolic Mode）
- is_parabolic() 偵測函式（close>5MA×1.06 或 乖離率>15%）
- score_volatility_risk()：Parabolic 模式直接豁免乖離率/波動扣分
- apply_risk_modifier()：Parabolic 豁免 RSI 過熱扣分
- 5MA 移動止損安全鎖：短線/波段站上5MA強制保底50分
- ★ 短線與波段權重總覽加入 v5.2 備註

v5.1 新增：
- 金融業防錯模組（is_finance + 3處guard clause）
- 價值風格估值權重從25%調降至15%，加給成長能力(20%→30%)
- RSI過熱門檻放寬至88（原80）
- ★ 四維權重總覽註解

v4.0 重大改版：
- 所有子項改為五級評分（Excellent=100%, Good=80%, Normal=60%, Weak=30%, Poor=0%）
- 四種風格各有 6 個子項
- 新增 Data Quality Modifier（資料年數調整）
- 新增 Risk Modifier（Penalty/Bonus 機制）
- 每個子項都輸出 breakdown 供前端顯示
"""

import pandas as pd
import numpy as np
from core.scoring_config import (
    SHORT_TERM_WEIGHTS, SHORT_TERM_THRESHOLDS,
    SWING_WEIGHTS, SWING_THRESHOLDS,
    VALUE_WEIGHTS, VALUE_THRESHOLDS,
    DIVIDEND_WEIGHTS, DIVIDEND_THRESHOLDS,
    DATA_QUALITY_MODIFIER,
    RISK_PENALTY, RISK_BONUS,
    REVENUE_MA_CROSS,
    OPERATING_MARGIN_QUALITY,
    INDUSTRY_DEBT_BIAS,
)

# ============================================================
# v5.1 新增：金融業防錯與短線過熱放寬
# ============================================================

# RSI 過熱扣分門檻（原 80，v5.1 放寬至 88 減少強勢股誤殺）
RSI_OVERHEAT_THRESHOLD = 88
RSI_OVERHEAT_PENALTY = -10

# ============================================================
# v5.2 新增：極端動能保護機制（Parabolic Mode）
# ============================================================

# 極端動能偵測門檻
PARABOLIC_CLOSE_MA5_RATIO = 1.06   # 收盤價 > 5MA × 1.06（大於 6% 視為極端強勢）
PARABOLIC_BIAS_PCT = 15            # 60日乖離率 > 15%

def is_parabolic(row: dict) -> bool:
    """偵測是否處於極端動能（妖股/瘋狗浪）模式
    
    v5.2：當股價極度偏離 5MA 或 60日乖離率爆表時，
    視為 parabolic 模式，將豁免 RSI 過熱與乖離率扣分，
    改由 5MA 移動止損護航。
    """
    close = row.get("close", 0)
    ma5 = row.get("MA_5", 0)
    bias = row.get("MA60_Bias", 0)
    
    if pd.notna(close) and pd.notna(ma5) and ma5 > 0 and close / ma5 > PARABOLIC_CLOSE_MA5_RATIO:
        return True
    if pd.notna(bias) and abs(bias) * 100 > PARABOLIC_BIAS_PCT:
        return True
    return False

# 金融業排除清單（產業名 + 常見金融股代碼）
FINANCE_SECTORS = ['金融業']
FINANCE_STOCK_IDS = [
    '2881', '2882', '2883', '2884', '2885', '2886', '2887', '2888',
    '2889', '2890', '2891', '2892',
    '5801', '5802', '5815', '5820', '5836', '5840', '5854',
    '5863', '5871', '5876', '5880', '6005',
]

def is_finance(row: dict) -> bool:
    """判斷 row 是否為金融業（依產業名或股票代碼）
    
    支援兩種欄位名稱：'Industry'（人為設定）和 'industry_category'（FinMind API 原始欄位）
    """
    # 檢查兩種可能的產業欄位名稱
    industry = row.get("Industry", None)
    if industry is None:
        industry = row.get("industry_category", None)
    if isinstance(industry, str) and industry in FINANCE_SECTORS:
        return True
    stock_id = row.get("stock_id", None)
    if isinstance(stock_id, str) and stock_id in FINANCE_STOCK_IDS:
        return True
    if isinstance(stock_id, str) and stock_id.startswith("28") and len(stock_id) == 4:
        return True  # 2xxx 開頭四位數為金融保險類股
    return False


# ============================================================
# 通用輔助函式
# ============================================================

def five_level_score(value, thresholds, reverse=False):
    """
    五級評分通用函式
    
    Parameters:
        value: 實際數值
        thresholds: dict 包含 _excellent, _good, _normal, _weak, _poor 門檻
                    所有 key 皆為可選（若缺少則跳過該級別）
        reverse: True 表示數值越低越好（反向評分）
    
    Returns:
        int: 100, 80, 60, 30, 0
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
            return 80
        if has_normal and value <= thresholds["_normal"]:
            return 60
        if has_weak and value <= thresholds["_weak"]:
            return 30
        if has_poor and value <= thresholds["_poor"]:
            return 0
        # 若數值大於所有已定義門檻（例如 pe_percentile=93.2 超過 weak=80），一律視為最差
        return 0
    else:
        # 正向評分：數值越高越好
        if has_excellent and value >= thresholds["_excellent"]:
            return 100
        elif has_good and value >= thresholds["_good"]:
            return 80
        elif has_normal and value >= thresholds["_normal"]:
            return 60
        elif has_weak and value >= thresholds["_weak"]:
            return 30
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


def apply_risk_modifier(row, base_score, style):
    """
    計算 Risk Modifier（Penalty + Bonus）
    
    v5.1：
    - RSI 過熱門檻放寬至 88（原 80），減少強勢股誤殺
    - 金融業跳過負債過高與營業現金流的扣分
    
    v5.2：
    - Parabolic 模式下 RSI 過熱扣分完全豁免
    - 加入 5MA 移動止損：短線/波段站上 5MA 時強制保底 50 分
    
    Returns:
        int: 調整後的最終分數（限制 0-100）
    """
    total_adjustment = 0
    _fin = is_finance(row)
    _parabolic = is_parabolic(row)
    
    # === Penalty ===
    # RSI 過熱（v5.2：parabolic 模式完全豁免）
    rsi = row.get("RSI_6", 50)
    if not _parabolic and pd.notna(rsi) and rsi > RSI_OVERHEAT_THRESHOLD:
        total_adjustment += RSI_OVERHEAT_PENALTY
    
    # 負債過高（v5.1：金融業跳過）
    debt = row.get("Debt_Ratio", 0)
    if not _fin and pd.notna(debt) and debt > RISK_PENALTY["debt_too_high"]["threshold"]:
        total_adjustment += RISK_PENALTY["debt_too_high"]["penalty"]
    
    # TTM EPS < 0
    ttm_eps = row.get("TTM_EPS", 0)
    if pd.notna(ttm_eps) and ttm_eps < 0:
        total_adjustment += RISK_PENALTY["eps_negative"]["penalty"]
    
    # 盈餘品質不佳（v5.1：金融業跳過營業現金流檢查）
    ttm_ocf = row.get("TTM_OCF", 0)
    payout = row.get("Payout_Ratio", 0)
    if not _fin and pd.notna(ttm_ocf) and pd.notna(payout) and ttm_ocf < 0 and payout > 100:
        total_adjustment += RISK_PENALTY["payout_unsustainable"]["penalty"]

    
    # === Bonus ===
    # RSI 超賣
    if pd.notna(rsi) and rsi < RISK_BONUS["rsi_oversold"]["threshold"]:
        total_adjustment += RISK_BONUS["rsi_oversold"]["bonus"]
    
    # 低負債（v5.1：金融業跳過）
    if not _fin and pd.notna(debt) and debt < RISK_BONUS["low_debt"]["threshold"]:
        total_adjustment += RISK_BONUS["low_debt"]["bonus"]
    
    # 計算最終分數
    final_score = base_score + total_adjustment
    final_score = max(0, min(100, final_score))
    
    # ============================================================
    # v5.2：5MA 移動止損安全鎖（Parabolic 模式保底）
    # ============================================================
    # 短線/波段風格：只要收盤價仍站穩 5MA 之上，分數強制保底 50 分
    # 確保在極端行情中不會因 RSI/乖離率扣分而誤拋，改由 5MA 實質跌破才出場
    if style in ("short_term", "swing"):
        close_val = row.get("close", 0)
        ma5_val = row.get("MA_5", 0)
        if pd.notna(close_val) and pd.notna(ma5_val) and close_val > ma5_val:
            final_score = max(final_score, 50)
    
    return int(round(final_score))


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


def score_momentum(row) -> dict:
    """動能強度評分（權重20%）"""
    t = SHORT_TERM_THRESHOLDS
    
    # RSI 位置
    rsi = row.get("RSI_6", 50)
    if pd.isna(rsi):
        rsi_score = 0
    elif rsi < t["rsi_oversold"]:
        rsi_score = 30  # 超賣區，動能弱但可能是反轉機會
    elif rsi < t["rsi_mid"]:
        rsi_score = 60  # 中性偏弱
    elif rsi < t["rsi_strong"]:
        rsi_score = 80  # 動能良好
    elif rsi < t["rsi_overheat"]:
        rsi_score = 100  # 動能強勁
    else:
        rsi_score = 60  # 過熱區，風險增加
    
    # MACD 狀態（門檻讀取 config）
    close = row.get("close", 0)
    ma5 = row.get("MA_5", 0)
    ma20 = row.get("MA_20", 0)
    if pd.notna(close) and pd.notna(ma5) and pd.notna(ma20):
        macd_line = ma5 - ma20  # 簡化 MACD 計算
        macd_score = five_level_score(macd_line, {
            "_excellent": t["macd_excellent"],
            "_good": t["macd_good"],
            "_normal": t["macd_normal"],
            "_weak": t["macd_weak"],
        })
        # 若 MACD > 0 且價格站上短期均線，升級為 Excellent
        if macd_line > 0 and close > ma5:
            macd_score = max(macd_score, 100)
    else:
        macd_score = 0
    
    # 突破前高（門檻讀取 config）
    high_20d = row.get("High_20D", None)
    if high_20d is None and "close" in row.index:
        # 如果沒有 High_20D，嘗試用 rolling max 計算
        pass
    if pd.notna(high_20d) and pd.notna(close):
        # 計算突破天數：close 站上 N 日高點
        break_days = 0
        if close >= high_20d:
            break_days = 3  # 突破20日高點
        elif close >= row.get("High_10D", close):
            break_days = 2  # 突破10日高點
        elif close >= row.get("High_5D", close):
            break_days = 1  # 突破5日高點
        break_score = five_level_score(break_days, {
            "_excellent": t["break_high_excellent"],
            "_good": t["break_high_good"],
            "_normal": t["break_high_normal"],
        })
    else:
        break_score = 60  # 無資料給中間分
    
    # 綜合評分（RSI 40%, MACD 35%, 突破 25%）
    composite = rsi_score * 0.40 + macd_score * 0.35 + break_score * 0.25
    
    return {
        "score": int(round(composite)),
        "details": {
            "rsi": round(rsi, 1) if pd.notna(rsi) else None,
            "rsi_score": rsi_score,
            "macd_score": macd_score,
            "break_score": break_score,
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
    
    # 10日法人（因資料源無 Inst_10D_Net，用 Inst_20D_Net 近似代替）
    inst_10d = row.get("Inst_20D_Net", 0)
    inst_10d_score = five_level_score(inst_10d, {
        "_excellent": t["inst_10d_excellent"],
        "_good": t["inst_10d_good"],
        "_normal": t["inst_10d_normal"],
        "_weak": t["inst_10d_weak"],
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
    
    # 綜合評分（5日法人 35%, 10日法人 25%, 外資 25%, 投信 15%）
    composite = inst_5d_score * 0.35 + inst_10d_score * 0.25 + foreign_score * 0.25 + trust_score * 0.15
    
    return {
        "score": int(round(composite)),
        "details": {
            "inst_5d_net": int(inst_5d) if pd.notna(inst_5d) else 0,
            "inst_5d_score": inst_5d_score,
            "inst_10d_score": inst_10d_score,
            "inst_10d_is_proxy": True,  # 用 Inst_20D_Net 近似代替 Inst_10D_Net
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


def score_volatility_risk(row) -> dict:
    """波動風險評分（權重10%）— 反向評分：波動越低越好
    
    v5.2：Parabolic 模式下直接豁免，改由 5MA 移動止損護航
    """
    # v5.2：極端動能模式 → 跳過波動扣分，死抱主升段
    if is_parabolic(row):
        return {
            "score": 100,
            "details": {
                "ma60_bias": row.get("MA60_Bias", None),
                "bias_score": 100,
                "atr_score": 100,
                "note": "極端動能模式，跳過乖離率/波動扣分，改由5MA移動止損護航"
            }
        }
    
    t = SHORT_TERM_THRESHOLDS
    
    # 乖離率（反向評分）
    bias = row.get("MA60_Bias", 0)
    bias_score = five_level_score(abs(bias) if pd.notna(bias) else 999, {
        "_excellent": t["bias_excellent"],
        "_good": t["bias_good"],
        "_normal": t["bias_normal"],
        "_weak": t["bias_weak"],
    }, reverse=True)
    
    # ATR（反向評分）
    atr = row.get("ATR", 0)
    if pd.notna(atr) and pd.notna(row.get("close", 0)) and row["close"] > 0:
        atr_pct = atr / row["close"]
        atr_score = five_level_score(atr_pct, {
            "_excellent": t["atr_excellent"],
            "_good": t["atr_good"],
            "_normal": t["atr_normal"],
            "_weak": t["atr_weak"],
        }, reverse=True)
    else:
        atr_score = 60  # 無資料給中間分
    
    # RSI 過熱檢查
    rsi = row.get("RSI_6", 50)
    if pd.notna(rsi) and rsi > t["rsi_overheat_penalty"]:
        rsi_penalty = 30  # 過熱扣分
    else:
        rsi_penalty = 100  # 無過熱
    
    # 綜合評分（乖離率 40%, ATR 30%, RSI 30%）
    composite = bias_score * 0.40 + atr_score * 0.30 + rsi_penalty * 0.30
    
    return {
        "score": int(round(composite)),
        "details": {
            "ma60_bias": round(bias, 4) if pd.notna(bias) else None,
            "bias_score": bias_score,
            "atr_score": atr_score,
            "rsi_penalty_score": rsi_penalty,
        }
    }


def score_short_term(row) -> dict:
    """計算短線總分與子項明細"""
    weights = SHORT_TERM_WEIGHTS
    
    trend = score_trend_structure(row)
    momentum = score_momentum(row)
    volume = score_volume_structure(row)
    inst = score_institutional(row)
    chip = score_chip_health(row)
    risk = score_volatility_risk(row)
    
    breakdown = {
        "trend_structure": trend["score"],
        "momentum": momentum["score"],
        "volume": volume["score"],
        "institutional": inst["score"],
        "chip": chip["score"],
        "risk": risk["score"],
    }
    
    # 加權計算
    weighted_total = (
        trend["score"] * weights["trend_structure"] +
        momentum["score"] * weights["momentum"] +
        volume["score"] * weights["volume"] +
        inst["score"] * weights["institutional"] +
        chip["score"] * weights["chip"] +
        risk["score"] * weights["risk"]
    )
    
    base_score = int(round(weighted_total))
    
    return {
        "total": base_score,
        "breakdown": breakdown,
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
    cagr_score = 60
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
    """中期趨勢評分（權重20%）"""
    t = SWING_THRESHOLDS
    
    close = row.get("close", 0)
    ma20 = row.get("MA_20", 0)
    ma60 = row.get("MA_60", 0)
    
    # 站上MA20
    above_ma20 = 1 if (pd.notna(close) and pd.notna(ma20) and close > ma20) else 0
    ma20_score = five_level_score(above_ma20, {
        "_excellent": t["above_ma20_excellent"],
    })
    
    # 站上MA60
    above_ma60 = 1 if (pd.notna(close) and pd.notna(ma60) and close > ma60) else 0
    ma60_score = five_level_score(above_ma60, {
        "_excellent": t["above_ma60_excellent"],
    })
    
    # MA20乖離
    if pd.notna(close) and pd.notna(ma20) and ma20 > 0:
        ma20_bias = abs((close - ma20) / ma20)
        ma20_bias_score = five_level_score(ma20_bias, {
            "_excellent": t["ma20_bias_excellent"],
            "_good": t["ma20_bias_good"],
            "_normal": t["ma20_bias_normal"],
            "_weak": t["ma20_bias_weak"],
        }, reverse=True)
    else:
        ma20_bias_score = 0
    
    # MA60乖離
    if pd.notna(close) and pd.notna(ma60) and ma60 > 0:
        ma60_bias = abs((close - ma60) / ma60)
        ma60_bias_score = five_level_score(ma60_bias, {
            "_excellent": t["ma60_bias_excellent"],
            "_good": t["ma60_bias_good"],
            "_normal": t["ma60_bias_normal"],
            "_weak": t["ma60_bias_weak"],
        }, reverse=True)
    else:
        ma60_bias_score = 0
    
    # 綜合評分（站上MA20 25%, 站上MA60 25%, MA20乖離 25%, MA60乖離 25%）
    composite = ma20_score * 0.25 + ma60_score * 0.25 + ma20_bias_score * 0.25 + ma60_bias_score * 0.25
    
    return {
        "score": int(round(composite)),
        "details": {
            "above_ma20": above_ma20,
            "above_ma60": above_ma60,
            "ma20_bias_score": ma20_bias_score,
            "ma60_bias_score": ma60_bias_score,
        }
    }


def score_institutional_trend(row) -> dict:
    """籌碼趨勢評分（權重20%）"""
    t = SWING_THRESHOLDS
    
    # 20日法人
    inst_20d = row.get("Inst_20D_Net", 0)
    inst_20d_score = five_level_score(inst_20d, {
        "_excellent": t["inst_20d_excellent"],
        "_good": t["inst_20d_good"],
        "_normal": t["inst_20d_normal"],
        "_weak": t["inst_20d_weak"],
    })
    
    # 借券趨勢
    sbl = row.get("SBL_5D_Change", 0)
    sbl_score = five_level_score(sbl, {
        "_excellent": t["sbl_trend_excellent"],
        "_good": t["sbl_trend_good"],
        "_normal": t["sbl_trend_normal"],
        "_weak": t["sbl_trend_weak"],
    }, reverse=True)
    
    # 法人趨勢（連續買超天數）
    inst_trend = row.get("Inst_Consecutive_Days", 0)
    inst_trend_score = five_level_score(inst_trend, {
        "_excellent": t["inst_trend_excellent"],
        "_good": t["inst_trend_good"],
        "_normal": t["inst_trend_normal"],
    })
    
    # 綜合評分（20日法人 45%, 借券 25%, 法人趨勢 30%）
    composite = inst_20d_score * 0.45 + sbl_score * 0.25 + inst_trend_score * 0.30
    
    return {
        "score": int(round(composite)),
        "details": {
            "inst_20d_net": int(inst_20d) if pd.notna(inst_20d) else 0,
            "inst_20d_score": inst_20d_score,
            "sbl_score": sbl_score,
            "inst_trend_score": inst_trend_score,
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
        pe_score = 60  # 無資料給中間分
    
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
        pb_score = 60
    
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
    """催化因子評分（權重10%）— 資料不存在則略過"""
    # 催化因子需要外部資料（新聞、公告等）
    # 目前先用營收動能作為代理指標
    rev_momentum = row.get("Revenue_Momentum", 0)
    rev_yoy = row.get("Revenue_YoY", 0)
    
    # 如果營收連續加速，視為正面催化
    if pd.notna(rev_momentum) and rev_momentum > 0:
        score = 100
    elif pd.notna(rev_yoy) and rev_yoy > 20:
        score = 80
    elif pd.notna(rev_yoy) and rev_yoy > 10:
        score = 60
    elif pd.notna(rev_yoy) and rev_yoy > 0:
        score = 30
    else:
        score = 60  # 無明顯催化，給中間分
    
    return {
        "score": score,
        "details": {
            "revenue_momentum": int(rev_momentum) if pd.notna(rev_momentum) else 0,
            "catalyst_score": score,
            "note": "催化因子目前以營收動能為代理指標" if score == 60 else "有正面催化"
        }
    }


def score_swing(row, cagr_1_5y=None) -> dict:
    """計算波段總分與子項明細
    
    v4.2：接收 cagr_1_5y 傳入 score_revenue_momentum
    """
    weights = SWING_WEIGHTS
    
    rev = score_revenue_momentum(row, cagr_1_5y)
    mid = score_mid_trend(row)
    inst = score_institutional_trend(row)
    earn = score_earnings_growth(row)
    val = score_valuation_position(row)
    cat = score_catalyst(row)
    
    breakdown = {
        "revenue_momentum": rev["score"],
        "mid_trend": mid["score"],
        "institutional_trend": inst["score"],
        "earnings_growth": earn["score"],
        "valuation": val["score"],
        "catalyst": cat["score"],
    }
    
    weighted_total = (
        rev["score"] * weights["revenue_momentum"] +
        mid["score"] * weights["mid_trend"] +
        inst["score"] * weights["institutional_trend"] +
        earn["score"] * weights["earnings_growth"] +
        val["score"] * weights["valuation"] +
        cat["score"] * weights["catalyst"]
    )
    
    base_score = int(round(weighted_total))
    
    return {
        "total": base_score,
        "breakdown": breakdown,
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
    """估值安全評分（權重25%）— 反向評分：百分位越低越好"""
    t = VALUE_THRESHOLDS
    
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
        pe_score = 60
    
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
        pb_score = 60
    
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


def score_profit_quality(row) -> dict:
    """獲利品質評分（權重20%）"""
    t = VALUE_THRESHOLDS
    
    # ROE
    roe = row.get("ROE_TTM", 0)
    roe_score = five_level_score(roe, {
        "_excellent": t["roe_excellent"],
        "_good": t["roe_good"],
        "_normal": t["roe_normal"],
        "_weak": t["roe_weak"],
    })
    
    # ROA
    roa = row.get("ROA_TTM", 0)
    roa_score = five_level_score(roa, {
        "_excellent": t["roa_excellent"],
        "_good": t["roa_good"],
        "_normal": t["roa_normal"],
        "_weak": t["roa_weak"],
    })
    
    # 毛利率
    gm = row.get("Gross_Margin", 0)
    gm_score = five_level_score(gm, {
        "_excellent": t["gm_excellent"],
        "_good": t["gm_good"],
        "_normal": t["gm_normal"],
        "_weak": t["gm_weak"],
    })
    
    # 綜合評分（ROE 45%, ROA 25%, 毛利率 30%）
    composite = roe_score * 0.45 + roa_score * 0.25 + gm_score * 0.30
    
    return {
        "score": int(round(composite)),
        "details": {
            "roe": round(roe, 2) if pd.notna(roe) else None,
            "roe_score": roe_score,
            "roa_score": roa_score,
            "gross_margin": round(gm, 2) if pd.notna(gm) else None,
            "gm_score": gm_score,
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
        div_score = 60  # 無資料給中間分
    
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


def score_value(row, data_years_available: int = 10) -> dict:
    """計算價值總分與子項明細"""
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
    
    weighted_total = (
        val_safety["score"] * weights["valuation_safety"] +
        profit["score"] * weights["profit_quality"] +
        growth["score"] * weights["growth_ability"] +
        fin_safety["score"] * weights["financial_safety"] +
        cf["score"] * weights["cash_flow_quality"] +
        shareholder["score"] * weights["shareholder_return"]
    )
    
    base_score = int(round(weighted_total))
    
    # 套用 Data Quality Modifier
    dq_modifier = get_data_quality_modifier(data_years_available)
    adjusted_score = int(round(base_score * dq_modifier))
    
    return {
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


# ============================================================
# 定存評分
# ============================================================

def score_dividend_record(row) -> dict:
    """配息紀錄評分（權重25%）"""
    t = DIVIDEND_THRESHOLDS
    
    # 連續配息年數
    div_years = row.get("Dividend_Continuity_Years", 0)
    continuity_score = five_level_score(div_years, {
        "_excellent": t["div_continuity_excellent"],
        "_good": t["div_continuity_good"],
        "_normal": t["div_continuity_normal"],
        "_weak": t["div_continuity_weak"],
    })
    
    return {
        "score": continuity_score,
        "details": {
            "dividend_continuity_years": int(div_years) if pd.notna(div_years) else 0,
            "continuity_score": continuity_score,
        }
    }


def score_dividend_quality(row) -> dict:
    """配息品質評分（權重20%）"""
    t = DIVIDEND_THRESHOLDS
    
    # 配息率
    payout = row.get("Payout_Ratio", None)
    if pd.notna(payout):
        # 配息率越接近 60% 越好
        if payout <= t["payout_ratio_excellent"]:
            # 低於60%：越高越好
            payout_score = five_level_score(payout, {
                "_excellent": t["payout_ratio_excellent"],
                "_good": t["payout_ratio_good_low"],
                "_normal": t["payout_ratio_normal_low"],
                "_weak": t["payout_ratio_weak_low"],
            })
        elif payout <= t["payout_ratio_good_high"]:
            payout_score = 80  # 60-70% 良好
        elif payout <= t["payout_ratio_normal_high"]:
            payout_score = 60  # 70-80% 普通
        elif payout <= t["payout_ratio_weak_high"]:
            payout_score = 30  # 80-90% 偏弱
        else:
            payout_score = 0   # >90% 危險
    else:
        payout_score = 0
    
    # EPS Cover
    ttm_eps = row.get("TTM_EPS", 0)
    cash_div = row.get("cash_dividend_total", 0)
    if pd.notna(ttm_eps) and pd.notna(cash_div) and cash_div > 0 and ttm_eps > 0:
        eps_cover = ttm_eps / cash_div
        eps_cover_score = five_level_score(eps_cover, {
            "_excellent": t["eps_cover_excellent"],
            "_good": t["eps_cover_good"],
            "_normal": t["eps_cover_normal"],
            "_weak": t["eps_cover_weak"],
        })
    else:
        eps_cover_score = 0
    
    # 綜合評分（配息率 60%, EPS Cover 40%）
    composite = payout_score * 0.60 + eps_cover_score * 0.40
    
    return {
        "score": int(round(composite)),
        "details": {
            "payout_ratio": round(payout, 2) if pd.notna(payout) else None,
            "payout_score": payout_score,
            "eps_cover_score": eps_cover_score,
        }
    }


def score_cash_flow_dividend(row) -> dict:
    """現金流評分（權重20%）"""
    t = DIVIDEND_THRESHOLDS
    
    # FCF Cover
    fcf_cover = row.get("FCF_Coverage", 0)
    fcf_score = five_level_score(fcf_cover, {
        "_excellent": t["fcf_cover_excellent"],
        "_good": t["fcf_cover_good"],
        "_normal": t["fcf_cover_normal"],
        "_weak": t["fcf_cover_weak"],
    })
    
    return {
        "score": fcf_score,
        "details": {
            "fcf_coverage": round(fcf_cover, 2) if pd.notna(fcf_cover) else None,
            "fcf_score": fcf_score,
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
    """計算定存總分與子項明細"""
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
    
    weighted_total = (
        record["score"] * weights["dividend_record"] +
        quality["score"] * weights["dividend_quality"] +
        cf["score"] * weights["cash_flow"] +
        fin_safety["score"] * weights["financial_safety"] +
        stability["score"] * weights["profit_stability"] +
        growth["score"] * weights["long_term_growth"]
    )
    
    base_score = int(round(weighted_total))
    
    # 套用 Data Quality Modifier
    dq_modifier = get_data_quality_modifier(data_years_available)
    adjusted_score = int(round(base_score * dq_modifier))
    
    return {
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
    
    # 套用 Risk Modifier
    short_total = apply_risk_modifier(latest, short_result["total"], "short_term")
    swing_total = apply_risk_modifier(latest, swing_result["total"], "swing")
    value_total = apply_risk_modifier(latest, value_result["total"], "value")
    dividend_total = apply_risk_modifier(latest, dividend_result["total"], "dividend")
    
    # === v4.2 流血去庫存質檢（短線/波段打8折） ===
    if om_quality["triggered"]:
        short_total = int(round(short_total * OPERATING_MARGIN_QUALITY["short_term_penalty"]))
        swing_total = int(round(swing_total * OPERATING_MARGIN_QUALITY["swing_penalty"]))
    
    # === v4.2 產業財務去偏誤（價值/定存打85折） ===
    value_bias = apply_industry_debt_bias(latest, value_total, "value", industry_median_debt)
    if value_bias["penalty_applied"]:
        value_total = value_bias["adjusted_score"]
    dividend_bias = apply_industry_debt_bias(latest, dividend_total, "dividend", industry_median_debt)
    if dividend_bias["penalty_applied"]:
        dividend_total = dividend_bias["adjusted_score"]
    
    # 構建結果
    result = {
        "short_term": {
            "total": short_total,
            "breakdown": short_result["breakdown"],
            "details": short_result["details"],
            "modifiers": {},
        },
        "swing": {
            "total": swing_total,
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
    min_window = max(60, min(n, 120))  # 至少 60 筆，但不要超過總長度
    
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
        
        # Risk Modifier
        short_total = apply_risk_modifier(row_dict, short_result["total"], "short_term")
        swing_total = apply_risk_modifier(row_dict, swing_result["total"], "swing")
        value_total = apply_risk_modifier(row_dict, value_result["total"], "value")
        dividend_total = apply_risk_modifier(row_dict, dividend_result["total"], "dividend")
        
        # 流血去庫存
        if om_quality["triggered"]:
            short_total = int(round(short_total * OPERATING_MARGIN_QUALITY["short_term_penalty"]))
            swing_total = int(round(swing_total * OPERATING_MARGIN_QUALITY["swing_penalty"]))
        
        # 產業去偏誤
        value_bias = apply_industry_debt_bias(row_dict, value_total, "value", industry_median_debt)
        if value_bias["penalty_applied"]:
            value_total = value_bias["adjusted_score"]
        dividend_bias = apply_industry_debt_bias(row_dict, dividend_total, "dividend", industry_median_debt)
        if dividend_bias["penalty_applied"]:
            dividend_total = dividend_bias["adjusted_score"]
        
        records.append({
            "date": current_date,
            "short_term_score": short_total,
            "swing_score": swing_total,
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
    print("scorer.py v5.0 - 五級評分制 + 回測功能完成")