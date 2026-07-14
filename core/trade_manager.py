"""
core/trade_manager.py
買賣建議與帳戶部位處置模組 — 四維度投票 + 雙軌建議價

核心進入函式：generate_trade_advice(stock_id, df, scores, current_shares, average_cost, risk_mode)

執行順序與鐵律：
1. 先讀取帳戶持有部位（最高權限的第一輸入源）
2. 若未持有 (shares == 0) → 依四大風格進行「型態認領」，引入【飛刀濾網】防範盲目接下墜飛刀。
3. 若已持有 (shares > 0) → 觸發「四維度獨立投票」，引入【一票通關】與【基本面鐵盾】防止賤賣優質資產。
4. 所有運算含 pd.isna() / .dropna() / KeyError 完備防禦。
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np


@dataclass
class TradeAdvice:
    """買賣建議結果（v4.4 雙軌建議價 — 積極+保守並存）"""
    # ===== 既有欄位（完全保留，零變動） =====
    action: str = "持有"            # 買進 / 賣出 / 持有 / 加碼 / 減碼 / 觀望 / 不建議
    style: str = ""                 # 認領的風格（短線 / 波段 / 價值 / 定存 / 無）
    entry_price: Optional[float] = None       # 主導風格建議價（依 risk_mode 決定指向誰）
    entry_price_low: Optional[float] = None
    entry_price_high: Optional[float] = None
    stop_loss: Optional[float] = None
    current_price: Optional[float] = None
    reference_ma: Optional[float] = None
    ma_type: str = ""
    reason: str = ""
    message: str = ""
    risk_level: str = "中"
    
    # ===== v4.4 新增：積極型專用欄位 =====
    agg_entry: Optional[float] = None         # 積極型核心建議價
    agg_entry_low: Optional[float] = None     # 積極型區間下限
    agg_entry_high: Optional[float] = None    # 積極型區間上限
    
    # ===== v4.4 新增：保守型專用欄位 =====
    cons_entry: Optional[float] = None        # 保守型核心建議價
    cons_entry_low: Optional[float] = None    # 保守型區間下限
    cons_entry_high: Optional[float] = None   # 保守型區間上限


def generate_trade_advice(
    stock_id: str,
    df: pd.DataFrame,
    scores: dict,
    current_shares: int = 0,
    average_cost: float = 0.0,
    risk_mode: str = "保守",           # 雙風險規範：保守 / 積極
) -> TradeAdvice:
    """買賣建議核心進入函式（v4.4 雙軌建議價）"""
    if df.empty:
        return TradeAdvice(
            action="不建議",
            reason="DataFrame 為空，無法分析",
            message="資料異常，請稍後再試",
        )

    latest = df.iloc[-1]

    # 安全取得指標數據
    def _safe(col_name):
        try:
            val = latest.get(col_name, np.nan)
            return None if pd.isna(val) else val
        except (KeyError, IndexError):
            return None

    close = _safe("close")
    ma_20 = _safe("MA_20")
    ma_5 = _safe("MA_5")
    ma_10 = _safe("MA_10")
    pe_ratio = _safe("pe_ratio")
    pe_pct = _safe("PE_Percentile")
    div_yield = _safe("dividend_yield")

    # 安全取得各風格分數
    short_score = scores.get("short_term", {}).get("total", 0)
    swing_score = scores.get("swing", {}).get("total", 0)
    value_score = scores.get("value", {}).get("total", 0)
    dividend_score = scores.get("dividend", {}).get("total", 0)

    # ================================================================
    # 分支一：未持有狀態（current_shares == 0）→ 型態認領 + 飛刀濾網
    # ================================================================
    if current_shares is None or current_shares <= 0:
        return _handle_no_position(
            stock_id, close, ma_20, ma_5, ma_10,
            short_score, swing_score, value_score, dividend_score,
            pe_pct=pe_pct,
            risk_mode=risk_mode,
        )

    # ================================================================
    # 分支二：已持有狀態（current_shares > 0）→ 四維度投票 + 鐵盾防線
    # ================================================================
    return _handle_has_position(
        stock_id, close, ma_20, ma_5, pe_ratio, pe_pct, div_yield,
        short_score, swing_score, value_score, dividend_score,
        current_shares, average_cost, df,
        risk_mode=risk_mode,
    )


# ================================================================
# 人類風格折扣法 — 建議買價計算輔助函式（v4.3 沿用）
# ================================================================

def _calc_aggressive_entry(
    price: float,
    score: int,
    ma_5: Optional[float],
    ma_20: Optional[float],
    pe_pct: Optional[float] = None,
) -> tuple:
    """
    積極模式（buy≥60）— 人類風格折扣法
    根據回測驗證的參數（基於 2330 / 2454 / 6770 實測）：
    - 分數 ≥80：極強勢，只給 1% 折扣 → 現價 × 0.99
    - 分數 ≥75：強勢，給 1.5% 折扣 → 現價 × 0.985
    - 分數 ≥70：中等，等拉回近均線 → max(MA5×0.995, 現價×0.98)
    - 分數 60~69：邊緣，等較大拉回 → max(MA5×0.985, 現價×0.975)
    
    Returns:
        (核心建議價, 區間下限, 區間上限)
    """
    if score >= 80:
        core = round(price * 0.99, 2)
        low = round(price * 0.98, 2)
        high = round(price * 0.995, 2)
    elif score >= 75:
        core = round(price * 0.985, 2)
        low = round(price * 0.97, 2)
        high = round(price * 0.995, 2)
    elif score >= 70 and ma_5 is not None and ma_5 > 0:
        core = max(round(ma_5 * 0.995, 2), round(price * 0.98, 2))
        low = max(round(ma_5 * 0.98, 2), round(price * 0.96, 2))
        high = round(price * 0.995, 2)
    elif ma_5 is not None and ma_5 > 0:
        # 60~69 分
        p_ma = round(ma_5 * 0.985, 2)
        p_price = round(price * 0.975, 2)
        core = max(p_ma, p_price)
        low = round(ma_5 * 0.97, 2)
        high = round(price * 0.99, 2)
    else:
        # 無 MA_5 時 fallback
        core = round(price * 0.98, 2)
        low = round(price * 0.96, 2)
        high = round(price * 0.99, 2)

    # 邊界檢查：核心價不低於現價的 95%
    floor = round(price * 0.95, 2)
    core = max(core, floor)
    low = max(low, round(price * 0.93, 2))
    if high < core:
        high = core

    return (core, low, high)


def _calc_conservative_entry(
    price: float,
    pe_pct: Optional[float],
    ma_20: Optional[float],
    ma_5: Optional[float],
    score: int,
) -> tuple:
    """
    保守模式 — 折扣明顯大於積極型，確保雙軌有實質價差
    
    核心原則：保守型折扣率 = 積極型折扣率 + 額外 1.5~2%
    例如積極打 98 折時，保守打 96 折
    
    - 有 PE 資料：依百分位打折（3~5% 折扣）
    - 無 PE 資料：統一打 95~97 折（比分數同等積極型多 -2%）
    
    Returns:
        (核心建議價, 區間下限, 區間上限)
    """
    if pe_pct is not None and pe_pct > 50:
        if ma_20 is not None and ma_20 > 0:
            core = max(round(ma_20 * 0.97, 2), round(price * 0.95, 2))
            low = max(round(ma_20 * 0.95, 2), round(price * 0.93, 2))
        else:
            core = round(price * 0.95, 2)
            low = round(price * 0.93, 2)
        high = round(price * 0.97, 2)
    elif pe_pct is not None and pe_pct > 30:
        core = round(price * 0.96, 2)
        low = round(price * 0.94, 2)
        high = round(price * 0.975, 2)
    elif pe_pct is not None and pe_pct <= 30:
        core = round(price * 0.965, 2)
        low = round(price * 0.95, 2)
        high = round(price * 0.98, 2)
    else:
        # 無 PE 資料：保守折扣比分數同等級積極型多 -2%
        # 積極 score≥80→×0.99 → 保守×0.97
        # 積極 score≥75→×0.985 → 保守×0.965
        # 積極 score≥70→max(MA5×0.995, price×0.98) → 保守 max(MA5×0.975, price×0.96)
        # 積極 score<70→max(MA5×0.985, price×0.975) → 保守 max(MA5×0.965, price×0.955)
        if score >= 80:
            core = round(price * 0.97, 2)
            low = round(price * 0.95, 2)
            high = round(price * 0.985, 2)
        elif score >= 75:
            core = round(price * 0.965, 2)
            low = round(price * 0.945, 2)
            high = round(price * 0.98, 2)
        elif ma_5 is not None and ma_5 > 0:
            core = max(round(ma_5 * 0.975, 2), round(price * 0.96, 2))
            low = max(round(ma_5 * 0.955, 2), round(price * 0.94, 2))
            high = round(price * 0.975, 2)
        else:
            core = round(price * 0.96, 2)
            low = round(price * 0.94, 2)
            high = round(price * 0.975, 2)

    floor = round(price * 0.95, 2)
    core = max(core, floor)
    low = max(low, round(price * 0.93, 2))
    if high < core:
        high = core

    # === 現價天花板阻斷（極端市況防禦）===
    # 飛刀暴跌時均線滯後，保守核心價可能高於現價
    # 違反安全邊際原則，core/low/high 全部 ≤ price
    if price is not None and core > price:
        ratio = (price * 0.98) / core
        core = round(price * 0.98, 2)
        if low is not None:
            low = round(min(low * ratio, price * 0.96), 2)
        if high is not None:
            high = round(min(high * ratio, price), 2)

    return (core, low, high)


# ================================================================
# 🆕 v4.4 雙軌輔助函式
# ================================================================

def _calc_dual_entry_prices(
    close: Optional[float],
    pe_pct: Optional[float],
    ma_20: Optional[float],
    ma_5: Optional[float],
    best_score: int,
) -> tuple:
    """
    雙軌並行計算積極型與保守型建議價
    
    鐵律：保守型核心價不得高於積極型核心價
    （保守=更安全=更便宜買，若違反則下修保守型）
    
    Returns:
        (agg_core, agg_low, agg_high, cons_core, cons_low, cons_high)
        若 close 為 None，所有值皆為 None
    """
    if close is None:
        return (None, None, None, None, None, None)
    
    agg_core, agg_low, agg_high = _calc_aggressive_entry(
        close, best_score, ma_5, ma_20, pe_pct
    )
    cons_core, cons_low, cons_high = _calc_conservative_entry(
        close, pe_pct, ma_20, ma_5, best_score
    )
    
    # 鐵律：保守型必須比積極型至少低 3%（確保肉眼可見的差距）
    if cons_core is not None and agg_core is not None:
        max_cons = round(agg_core * 0.97, 2)  # 保守最高只能到積極的 97%
        if cons_core > max_cons:
            # 下修保守型
            adj = max_cons / cons_core
            cons_core = max_cons
            if cons_low is not None:
                cons_low = round(cons_low * adj, 2)
            if cons_high is not None:
                cons_high = round(cons_high * adj, 2)
    
    return (agg_core, agg_low, agg_high, cons_core, cons_low, cons_high)


def _fill_dual_prices(
    ta: TradeAdvice,
    agg_core, agg_low, agg_high,
    cons_core, cons_low, cons_high,
    risk_mode: str,
    force_conservative: bool = False,
) -> TradeAdvice:
    """
    將雙軌價位填入 TradeAdvice，並根據 risk_mode 決定主欄位
    
    鐵律：
    - 飛刀濾網 (force_conservative=True)：主欄位強制保守型（較低價）
    - 保守模式：主欄位為保守型
    - 積極模式：主欄位為積極型
    """
    # 先填入雙軌專用欄位
    ta.agg_entry = agg_core
    ta.agg_entry_low = agg_low
    ta.agg_entry_high = agg_high
    ta.cons_entry = cons_core
    ta.cons_entry_low = cons_low
    ta.cons_entry_high = cons_high
    
    # 決定主欄位（entry_price / entry_price_low / entry_price_high）
    if force_conservative:
        ta.entry_price = cons_core
        ta.entry_price_low = cons_low
        ta.entry_price_high = cons_high
    elif risk_mode == "積極":
        ta.entry_price = agg_core
        ta.entry_price_low = agg_low
        ta.entry_price_high = agg_high
    else:
        ta.entry_price = cons_core
        ta.entry_price_low = cons_low
        ta.entry_price_high = cons_high
    
    return ta


def _build_dual_message(
    action_label: str,
    reason_text: str,
    agg_core, agg_low, agg_high,
    cons_core, cons_low, cons_high,
    add_falling_knife_warning: bool = False,
    short_score: int = 0,
    current_price: Optional[float] = None,
) -> str:
    """
    直式手機瀏覽最佳化的雙軌建議價訊息
    排版原則：每行不超過 35 個中文字元
    """
    parts = [f"{action_label}。{reason_text}"]
    
    has_agg = agg_core is not None
    has_cons = cons_core is not None
    
    if has_agg or has_cons:
        parts.append("")
        parts.append("📊 建議價位區間對照")
        parts.append("━" * 20)
        
        if has_agg:
            agg_note = " ⚠️ 高於現價，等站回5MA再考慮進場" if (current_price is not None and agg_core > current_price) else ""
            parts.append(
                f"⚡ 積極型 (均線拉回)：{agg_note}\n"
                f"   {agg_low:.2f} ~ {agg_high:.2f} 元\n"
                f"   (核心 {agg_core:.2f} 元)"
            )
        
        if has_cons:
            cons_note = " ⚠️ 高於現價，需掛單等拉回" if (current_price is not None and cons_core > current_price) else ""
            parts.append(
                f"🛡️ 保守型 (歷史低估)：{cons_note}\n"
                f"   {cons_low:.2f} ~ {cons_high:.2f} 元\n"
                f"   (核心 {cons_core:.2f} 元)"
            )
        
        parts.append("━" * 20)
        parts.append("💡 若資金允許，可同時設定兩組觀察買單，")
        parts.append("   進行分批布局與空間錨定。")
    
    if add_falling_knife_warning:
        parts.append("")
        parts.append(f"⚠️ 短線動能疲弱 (僅 {short_score} 分)")
        parts.append("   且股價壓在均線下方。")
        parts.append("   請勿現價直接買進。")
    
    return "\n".join(parts)


# ================================================================
# 未持有狀態（v4.4 雙軌並行計算）
# ================================================================

def _handle_no_position(
    stock_id: str,
    close: Optional[float],
    ma_20: Optional[float],
    ma_5: Optional[float],
    ma_10: Optional[float],
    short_score: int,
    swing_score: int,
    value_score: int,
    dividend_score: int,
    pe_pct: Optional[float] = None,
    risk_mode: str = "保守",
) -> TradeAdvice:
    """未持有狀態：P1/P4-B/P5 雙軌並行計算積極+保守建議價區間"""

    all_scores = {
        "swing": swing_score,
        "short_term": short_score,
        "value": value_score,
        "dividend": dividend_score,
    }
    max_style = max(all_scores, key=all_scores.get)
    max_score = all_scores[max_style]

    # 決定動態門檻
    if risk_mode == "積極":
        buy_threshold = 60
    else:
        buy_threshold = 70

    def _get_best_score_for_style() -> tuple:
        style_order = ["short_term", "swing", "value", "dividend"]
        best_s = 0
        best_n = ""
        for s in style_order:
            v = all_scores.get(s, 0)
            if v > best_s:
                best_s = v
                best_n = s
        return (best_s, best_n)

    # ============================================================
    # 優先級 1：全部 < 50 → 極低分，不建議入場（雙軌）
    # ============================================================
    if max_score < 50:
        best_s, _ = _get_best_score_for_style()
        agg_c, agg_l, agg_h, cons_c, cons_l, cons_h = _calc_dual_entry_prices(
            close, pe_pct, ma_20, ma_5, best_s
        )
        
        ta = TradeAdvice(
            action="不建議", style="無", current_price=close,
            reason=f"四大風格最高分僅 {max_score}，低於{buy_threshold}分門檻",
            risk_level="高",
        )
        ta = _fill_dual_prices(ta, agg_c, agg_l, agg_h, cons_c, cons_l, cons_h, risk_mode)
        ta.message = _build_dual_message(
            "不建議布局",
            "成長動能不佳或估值過高，不具備中長線安全邊際",
            agg_c, agg_l, agg_h, cons_c, cons_l, cons_h,
        )
        return ta

    # ============================================================
    # 優先級 2：波段 ≥ buy_threshold → 買進（MA_20±2%, 不高於現價）
    # ============================================================
    if swing_score >= buy_threshold:
        # 建議買價不應高於現價：若現價已低於 MA20，則以現價為基準
        if ma_20 is not None and close is not None and close < ma_20:
            # 現價低於月線 → 以現價附近為買區
            entry_low = round(close * 0.98, 2)
            entry_high = round(close * 1.01, 2)
            entry_core = round(close * 0.99, 2)
            ref_line = close
            ref_label = "現價"
        else:
            # 現價高於月線（正常多頭）→ 月線 ±2%
            entry_low = round(ma_20 * 0.98, 2) if ma_20 else None
            entry_high = round(ma_20 * 1.02, 2) if ma_20 else None
            entry_core = entry_low
            ref_line = ma_20
            ref_label = f"月線 ({ma_20:.2f})"
        stop_loss = round(ma_20 * 0.95, 2) if ma_20 else None
        return TradeAdvice(
            action="買進", style="波段",
            entry_price=entry_core,
            entry_price_low=entry_low,
            entry_price_high=entry_high,
            stop_loss=stop_loss,
            current_price=close, reference_ma=ref_line, ma_type="MA_20",
            reason=f"波段 {swing_score}分 > {buy_threshold}，認領波段主升段",
            message=(
                f"策略認領：波段主升段。當前營收動能具備續航力，"
                f"建議在 {ref_label} 附近逢低分批布局"
                f"（{entry_low:.2f} ~ {entry_high:.2f} 元）。"
            ),
            risk_level="中",
        )

    # ============================================================
    # 優先級 3：短線 ≥ buy_threshold → 買進（5MA附近，不高於現價）
    # ============================================================
    if short_score >= buy_threshold:
        stop_loss = round(ma_20, 2) if ma_20 else None
        # 建議買價不應高於現價
        if ma_5 is not None and close is not None and close < ma_5:
            # 現價已跌至 5MA 下方 → 以現價為基準
            entry_core = round(close * 0.99, 2)
            low_val = round(close * 0.97, 2)
            high_val = round(close * 1.01, 2)
            ref_line = close
            ref_label = f"現價 ({close:.2f})"
        else:
            # 正常：5MA 附近
            entry_core = round(ma_5, 2) if ma_5 else close
            low_val = round(ma_5 * 0.98, 2) if ma_5 else round(close * 0.98, 2) if close else None
            high_val = round(ma_5 * 1.01, 2) if ma_5 else round(close * 1.01, 2) if close else None
            ref_line = ma_5 if ma_5 else close
            ref_label = f"5MA ({ma_5:.2f})" if ma_5 else f"現價 ({close:.2f})"
        return TradeAdvice(
            action="買進", style="短線",
            entry_price=entry_core,
            entry_price_low=low_val,
            entry_price_high=high_val,
            stop_loss=stop_loss,
            current_price=close, reference_ma=ref_line, ma_type="5MA",
            reason=f"短線 {short_score}分 > {buy_threshold} 且波段 {swing_score}分 < {buy_threshold}，認領短線動能",
            message=(
                f"策略認領：中期強勢動能轉折。"
                f"建議在 {ref_label} 附近建立短線部位，"
                f"跌破20MA ({ma_20:.2f}) 無條件停損。"
            ),
            risk_level="中",
        )

    # ============================================================
    # 優先級 4：價值或定存 ≥ buy_threshold → 飛刀濾網分流
    # ============================================================
    if value_score >= buy_threshold or dividend_score >= buy_threshold:
        best_style_name = "價值" if value_score >= dividend_score else "定存"

        is_falling_knife = (
            short_score < 50
            and close is not None
            and ma_5 is not None
            and close < ma_5
        )

        if is_falling_knife:
            # 優先級 4-B：飛刀濾網 → 雙軌 + 主欄位強制保守
            best_s = max(value_score, dividend_score)
            agg_c, agg_l, agg_h, cons_c, cons_l, cons_h = _calc_dual_entry_prices(
                close, pe_pct, ma_20, ma_5, best_s
            )
            
            ta = TradeAdvice(
                action="觀望", style=best_style_name,
                stop_loss=None, current_price=close,
                reason=f"{best_style_name}分 > 70 但觸發飛刀濾網（短線{short_score}分且破5MA）",
                risk_level="低",
            )
            ta = _fill_dual_prices(
                ta, agg_c, agg_l, agg_h, cons_c, cons_l, cons_h,
                risk_mode, force_conservative=True,
            )
            ta.message = _build_dual_message(
                "策略認領：長線安全邊際",
                "資產品質與價值面極佳，但短線動能疲弱，不建議現價直接買進",
                agg_c, agg_l, agg_h, cons_c, cons_l, cons_h,
                add_falling_knife_warning=True,
                short_score=short_score,
                current_price=close,
            )
            return ta
        else:
            # 優先級 4-A：未破位 → 正常現價買進（不高於現價）
            if ma_5 is not None and close is not None and close < ma_5:
                # 現價低於 5MA → 以現價為基準
                low_val = round(close * 0.97, 2)
                high_val = round(close * 1.01, 2)
                entry_core = round(close * 0.99, 2)
            else:
                low_val = round(close * 0.98, 2) if close else None
                high_val = round(close * 1.01, 2) if close else None
                entry_core = close
            return TradeAdvice(
                action="買進", style=best_style_name,
                entry_price=entry_core,
                entry_price_low=low_val,
                entry_price_high=high_val,
                stop_loss=None,
                current_price=close,
                reason=f"{best_style_name}分 > 70 且未觸發飛刀濾網",
                message=(
                    f"策略認領：長線安全邊際。"
                    f"資產品質良好，現價 {close:.2f} 元即可建立基本防禦倉位，"
                    f"建議買入區間 {low_val:.2f} ~ {high_val:.2f} 元，拉回分批定額買進。"
                ),
                risk_level="低",
            )

    # ============================================================
    # 優先級 5：最高分介於 50 ~ buy_threshold 之間 → 中性觀望（雙軌）
    # ============================================================
    label_map = {"swing": "波段", "short_term": "短線", "value": "價值", "dividend": "定存"}
    if 50 <= max_score < buy_threshold:
        best_s, best_n = _get_best_score_for_style()
        agg_c, agg_l, agg_h, cons_c, cons_l, cons_h = _calc_dual_entry_prices(
            close, pe_pct, ma_20, ma_5, best_s
        )
        
        ta = TradeAdvice(
            action="觀望", style=label_map.get(max_style, max_style),
            current_price=close,
            reason=f"最高分 {max_style} = {max_score}，介於50~{buy_threshold}之間，建議觀望",
            risk_level="中",
        )
        ta = _fill_dual_prices(ta, agg_c, agg_l, agg_h, cons_c, cons_l, cons_h, risk_mode)
        ta.message = _build_dual_message(
            f"評分中性（最佳 {label_map.get(max_style, max_style)} {max_score} 分）",
            f"建議觀望，待分數提升至 {buy_threshold} 分以上再確認進場",
            agg_c, agg_l, agg_h, cons_c, cons_l, cons_h,
        )
        return ta

    # 兜底防禦
    return TradeAdvice(
        action="觀望", style=label_map.get(max_style, max_style),
        current_price=close,
        reason=f"最高分 {max_style} = {max_score}，未匹配任何優先級（異常）",
        message=f"評分異常（最佳 {max_score}分），請檢查資料來源。",
        risk_level="中",
    )


# ================================================================
# 已持有狀態（四維度投票 + 鐵盾防線）
# ================================================================

def _handle_has_position(
    stock_id: str,
    close: Optional[float],
    ma_20: Optional[float],
    ma_5: Optional[float],
    pe_ratio: Optional[float],
    pe_pct: Optional[float],
    div_yield: Optional[float],
    short_score: int,
    swing_score: int,
    value_score: int,
    dividend_score: int,
    current_shares: int,
    average_cost: float,
    df: pd.DataFrame,
    risk_mode: str = "保守",
) -> TradeAdvice:
    """已持有狀態：四維度獨立投票機制 + 一票通關 + 鐵盾覆蓋（v4.4 已持有雙軌）"""

    votes = []
    vote_details = {}

    if close is not None and ma_5 is not None and close > ma_5 and short_score >= 50:
        votes.append("短線")
        vote_details["短線"] = f"贊成（收盤{close}>5MA{ma_5}，短線{short_score}分）"
    else:
        vote_details["短線"] = "反對"

    if close is not None and ma_20 is not None and close > ma_20 and swing_score >= 55:
        votes.append("波段")
        vote_details["波段"] = f"贊成（收盤{close}>20MA{ma_20}，波段{swing_score}分）"
    else:
        vote_details["波段"] = "反對"

    is_value_pass = False
    value_reason = ""
    if value_score >= 70:
        is_value_pass = True
        value_reason = f"贊成（⭐一票通關：價值分數{value_score} >= 70）"
    elif pe_ratio is not None and pe_ratio < 12 and value_score >= 50:
        is_value_pass = True
        value_reason = f"贊成（⭐一票通關：本益比{pe_ratio:.2f} < 12 且價值{value_score}分）"
    elif pe_pct is not None and pe_pct < 70 and value_score >= 50:
        is_value_pass = True
        value_reason = f"贊成（PE百分位{pe_pct:.0f}%未過熱，價值{value_score}分）"

    if is_value_pass:
        votes.append("價值")
        vote_details["價值"] = value_reason
    else:
        vote_details["價值"] = f"反對（價值{value_score}分，本益比{pe_ratio}）"

    if dividend_score >= 50:
        votes.append("定存")
        vote_details["定存"] = f"贊成（定存{dividend_score}分）"
    else:
        vote_details["定存"] = f"反對（定存{dividend_score}分）"

    vote_count = len(votes)
    votes_detail_str = "；".join(f"{k}:{v}" for k, v in vote_details.items())

    pnl_str = ""
    if close is not None and average_cost > 0:
        pnl_pct = ((close - average_cost) / average_cost) * 100
        pnl_str = f"（帳面 {pnl_pct:+.2f}%）"

    inst_3d_negative = False
    if "Inst_Net" in df.columns:
        try:
            last_3 = df["Inst_Net"].iloc[-3:].dropna()
            if len(last_3) >= 3:
                inst_3d_negative = all(last_3 < 0)
        except (KeyError, IndexError):
            pass

    is_iron_shield = False
    if (value_score > 70 or dividend_score > 70) and (close is not None and average_cost > 0):
        if close >= (average_cost * 0.95):
            is_iron_shield = True

    # 4票全贊成 → 至少持有，波段強再加碼
    if vote_count >= 4:
        if swing_score > 65:
            # 4票 + 波段>65：加碼
            best_score = max(short_score, swing_score, value_score, dividend_score)
            agg_c, agg_l, agg_h, cons_c, cons_l, cons_h = _calc_dual_entry_prices(
                close, pe_pct, ma_20, ma_5, best_score
            )
            ta = TradeAdvice(
                action="加碼", style="波段",
                stop_loss=round(ma_20 * 0.95, 2) if ma_20 else None,
                current_price=close,
                reason=f"四維度投票{vote_count}票，全部看好。細節：{votes_detail_str}",
                message="",
                risk_level="低",
            )
            ta = _fill_dual_prices(ta, agg_c, agg_l, agg_h, cons_c, cons_l, cons_h, risk_mode)
            pnl_line = f"【建議逢低加碼】{pnl_str}。四維度全數支持持有，趨勢強烈且全面看好，可適度擴大子彈規模。"
            ta.message = pnl_line + "\n\n" + _build_dual_message(
                "📈 加碼區間參考", "依 risk_mode 決定採用哪組建議價",
                agg_c, agg_l, agg_h, cons_c, cons_l, cons_h,
                current_price=close,
            )
            return ta
        else:
            # 4票 + 波段≤65：全數贊成但波段不夠強，繼續持有
            entry_ref = round(ma_20, 2) if ma_20 else None
            return TradeAdvice(
                action="持有", style="波段", current_price=close,
                entry_price=entry_ref,
                entry_price_low=round(entry_ref * 0.98, 2) if entry_ref else None,
                entry_price_high=round(entry_ref * 1.02, 2) if entry_ref else None,
                reason=f"四維度投票{vote_count}票全數贊成，但波段{swing_score}分未達加碼門檻。細節：{votes_detail_str}",
                message=(
                    f"【建議繼續持有】{pnl_str}。"
                    f"四維度全數支持，趨勢全面看好，切勿過早獲利了結。"
                    f"待波段分數提升至 65 以上再考慮加碼。"
                ),
                risk_level="低",
            )

    if vote_count == 3:
        entry_ref = round(ma_20, 2) if ma_20 else None
        add_msg = ""
        if entry_ref:
            add_msg = f"若未來股價拉回至月線 {entry_ref} 元附近，可視為右側趨勢的優質補槍點。"
        # 3票持有 → 雙軌建議價（加碼參考用）
        best_score = max(short_score, swing_score, value_score, dividend_score)
        agg_c, agg_l, agg_h, cons_c, cons_l, cons_h = _calc_dual_entry_prices(
            close, pe_pct, ma_20, ma_5, best_score
        )
        ta = TradeAdvice(
            action="持有", style="波段", current_price=close,
            entry_price=entry_ref,
            entry_price_low=round(entry_ref * 0.98, 2) if entry_ref else None,
            entry_price_high=round(entry_ref * 1.02, 2) if entry_ref else None,
            reason=f"四維度投票{vote_count}票贊成。細節：{votes_detail_str}",
            message="",
            risk_level="低",
        )
        ta = _fill_dual_prices(ta, agg_c, agg_l, agg_h, cons_c, cons_l, cons_h, risk_mode)
        pnl_line = (
            f"【建議繼續持有】{pnl_str}。"
            f"四維度中有三維度支持，切勿因恐高心理過早獲利了結，讓利潤持續奔跑。"
            f"{add_msg}"
        )
        ta.message = pnl_line + "\n\n" + _build_dual_message(
            "📊 補倉區間參考", "若欲逢低加碼，可參考下方雙軌價位",
            agg_c, agg_l, agg_h, cons_c, cons_l, cons_h,
            current_price=close,
        )
        return ta

    if vote_count == 2 and inst_3d_negative:
        return TradeAdvice(
            action="減碼", current_price=close,
            reason=f"四維度投票2票贊成且法人連3日轉負。細節：{votes_detail_str}",
            message=(
                f"【建議逢高減碼】{pnl_str}。"
                f"四維度僅2票支持，且法人連續3日賣超，建議先收回 1/3 ~ 1/2 部位觀望。"
            ),
            risk_level="中",
        )

    if vote_count == 2:
        entry_ref = round(ma_20, 2) if ma_20 else None
        add_msg = ""
        if entry_ref:
            add_msg = (
                f"當前短線動能偏弱，現價請勿盲目攤平。"
                f"若欲加碼，建議靜待股價拉回至月線 {entry_ref} 元附近"
                f"且出現止穩訊號時，再動用新子彈。"
            )
        # 2票持有觀望 → 雙軌建議價（保守加碼參考用）
        best_score = max(short_score, swing_score, value_score, dividend_score)
        agg_c, agg_l, agg_h, cons_c, cons_l, cons_h = _calc_dual_entry_prices(
            close, pe_pct, ma_20, ma_5, best_score
        )
        ta = TradeAdvice(
            action="持有觀望", current_price=close,
            entry_price=entry_ref,
            entry_price_low=round(entry_ref * 0.98, 2) if entry_ref else None,
            entry_price_high=round(entry_ref * 1.02, 2) if entry_ref else None,
            reason=f"四維度投票2票贊成，邊緣持有。細節：{votes_detail_str}",
            message="",
            risk_level="中",
        )
        ta = _fill_dual_prices(ta, agg_c, agg_l, agg_h, cons_c, cons_l, cons_h, risk_mode)
        pnl_line = (
            f"【建議持有觀望】{pnl_str}。"
            f"四維度僅2票支持，方向尚未明確，建議維持現有部位，密切觀察是否出現賣出訊號。"
            f"{add_msg}"
        )
        ta.message = pnl_line + "\n\n" + _build_dual_message(
            "📊 觀望區間參考", "現階段不建議積極加碼，可先設定低接觀察單",
            agg_c, agg_l, agg_h, cons_c, cons_l, cons_h,
            current_price=close,
        )
        return ta

    if is_iron_shield:
        entry_ref = round(ma_20, 2) if ma_20 else None
        add_msg = ""
        if entry_ref:
            add_msg = (
                f"當前短線動能偏弱，現價請勿盲目攤平。"
                f"若欲加碼，建議靜待股價拉回至月線 {entry_ref} 元附近"
                f"且出現止穩訊號時，再動用新子彈。"
            )
        # 鐵盾 → 雙軌建議價（保守型為主的低接參考）
        best_score = max(short_score, swing_score, value_score, dividend_score)
        agg_c, agg_l, agg_h, cons_c, cons_l, cons_h = _calc_dual_entry_prices(
            close, pe_pct, ma_20, ma_5, best_score
        )
        ta = TradeAdvice(
            action="持有觀望", current_price=close,
            entry_price=entry_ref,
            entry_price_low=round(entry_ref * 0.98, 2) if entry_ref else None,
            entry_price_high=round(entry_ref * 1.02, 2) if entry_ref else None,
            reason=(
                f"四維度投票{vote_count}票，但【基本面鐵盾啟動】強制覆蓋。"
                f"細節：{votes_detail_str}"
            ),
            message="",
            risk_level="低",
        )
        ta = _fill_dual_prices(ta, agg_c, agg_l, agg_h, cons_c, cons_l, cons_h, risk_mode)
        pnl_line = (
            f"【建議持有觀望】{pnl_str}。"
            f"雖然技術面破位（僅 {vote_count} 票贊成），"
            f"但因觸發基本面鐵盾防線且虧損在安全範圍內，"
            f"系統強制禁止賤賣資產。請抱緊個股，靜待籌碼落底。"
            f"{add_msg}"
        )
        ta.message = pnl_line + "\n\n" + _build_dual_message(
            "🛡️ 鐵盾低接參考", "基本面無虞，可於保守型價位附近分批低接",
            agg_c, agg_l, agg_h, cons_c, cons_l, cons_h,
            current_price=close,
        )
        return ta

    if vote_count == 1:
        return TradeAdvice(
            action="減碼", current_price=close,
            reason=f"四維度投票1票贊成，鐵盾未啟動。細節：{votes_detail_str}",
            message=(
                f"【建議逢高減碼】{pnl_str}。"
                f"四維度僅1票支持，多數維度已不支持繼續持有，建議收回 1/2 ~ 2/3 部位。"
            ),
            risk_level="高",
        )

    return TradeAdvice(
        action="賣出", current_price=close,
        reason=f"四維度投票0票贊成，全面看空，鐵盾未啟動。細節：{votes_detail_str}",
        message=(
            f"【建議全數賣出】{pnl_str}。"
            f"四維度全數反對繼續持有（0票），紀律出場，落袋為安。"
        ),
        risk_level="高",
    )


if __name__ == "__main__":
    print("trade_manager.py — 四維度投票 + 雙軌建議價")
