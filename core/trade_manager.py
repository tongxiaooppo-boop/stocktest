"""
core/trade_manager.py v4.2 (終極閉環版)
買賣建議與帳戶部位處置模組

核心進入函式：generate_trade_advice(stock_id, current_shares, average_cost, df, scores)

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
    """買賣建議結果"""
    action: str = "持有"            # 買進 / 賣出 / 持有 / 加碼 / 減碼 / 觀望 / 不建議
    style: str = ""                 # 認領的風格（短線 / 波段 / 價值 / 定存 / 無）
    entry_price: Optional[float] = None  # 建議買入價位
    stop_loss: Optional[float] = None    # 建議停損價位
    current_price: Optional[float] = None # 最新收盤價
    reference_ma: Optional[float] = None # 參考均線值
    ma_type: str = ""               # 參考的均線類型 (5MA / 20MA / MA_20)
    reason: str = ""                # 給程式看的判斷理由
    message: str = ""               # 給使用者看的制式文字
    risk_level: str = "中"          # 風險等級


def generate_trade_advice(
    stock_id: str,
    df: pd.DataFrame,
    scores: dict,
    current_shares: int = 0,
    average_cost: float = 0.0,
) -> TradeAdvice:
    """買賣建議核心進入函式"""
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
            stock_id, close, ma_20, ma_5,
            short_score, swing_score, value_score, dividend_score,
        )

    # ================================================================
    # 分支二：已持有狀態（current_shares > 0）→ 四維度投票 + 鐵盾防線
    # ================================================================
    return _handle_has_position(
        stock_id, close, ma_20, ma_5, pe_ratio, pe_pct, div_yield,
        short_score, swing_score, value_score, dividend_score,
        current_shares, average_cost, df,
    )


# ================================================================
# 未持有狀態
# ================================================================

def _handle_no_position(
    stock_id: str,
    close: Optional[float],
    ma_20: Optional[float],
    ma_5: Optional[float],
    short_score: int,
    swing_score: int,
    value_score: int,
    dividend_score: int,
) -> TradeAdvice:
    """未持有狀態：依據五大優先級進行型態認領，包含左側價值飛刀分流"""

    all_scores = {
        "swing": swing_score,
        "short_term": short_score,
        "value": value_score,
        "dividend": dividend_score,
    }
    max_style = max(all_scores, key=all_scores.get)
    max_score = all_scores[max_style]

    # 優先級 1：全部 < 50 分 → 不建議入場
    if max_score < 50:
        return TradeAdvice(
            action="不建議", style="無", current_price=close,
            reason=f"四大風格最高分僅 {max_score}，低於50分門檻",
            message="不建議布局。原因：成長動能不佳或估值過高，不具備中長線安全邊際。",
            risk_level="高",
        )

    # 優先級 2：波段 > 70 → 買進（MA_20±2%）
    if swing_score > 70:
        entry_low = round(ma_20 * 0.98, 2) if ma_20 else None
        entry_high = round(ma_20 * 1.02, 2) if ma_20 else None
        stop_loss = round(ma_20 * 0.95, 2) if ma_20 else None
        return TradeAdvice(
            action="買進", style="波段",
            entry_price=entry_low, stop_loss=stop_loss,
            current_price=close, reference_ma=ma_20, ma_type="MA_20",
            reason=f"波段 {swing_score}分 > 70，認領波段主升段",
            message=(
                f"策略認領：波段主升段。當前營收動能具備續航力，"
                f"建議在月線 ({ma_20:.2f}) 附近 ±2% 內逢低分批布局"
                f"（{entry_low} ~ {entry_high} 元）。"
            ),
            risk_level="中",
        )

    # 優先級 3：短線 > 70 且波段 < 70 → 買進（5MA附近）
    if short_score > 70:
        entry = round(ma_5, 2) if ma_5 else close
        stop_loss = round(ma_20, 2) if ma_20 else None
        return TradeAdvice(
            action="買進", style="短線",
            entry_price=entry, stop_loss=stop_loss,
            current_price=close, reference_ma=ma_5, ma_type="5MA",
            reason=f"短線 {short_score}分 > 70 且波段 {swing_score}分 < 70，認領短線動能",
            message=(
                f"策略認領：中期強勢動能轉折。"
                f"建議在5MA ({ma_5:.2f}) 附近建立短線部位，"
                f"跌破20MA ({ma_20:.2f}) 無條件停損。"
            ),
            risk_level="中",
        )

    # 優先級 4：價值或定存 > 70 → 觸發【飛刀濾網】分流
    if value_score > 70 or dividend_score > 70:
        best_style_name = "價值" if value_score >= dividend_score else "定存"

        # 檢查是否滿足飛刀條件：短線極弱且壓在5MA下方
        is_falling_knife = (
            short_score < 50
            and close is not None
            and ma_5 is not None
            and close < ma_5
        )

        if is_falling_knife:
            # 優先級 4-B：飛刀濾網觸發 → 強制轉為觀望/低吸
            msg = (
                f"策略認領：長線安全邊際。操作建議：雖然資產品質與價值面極佳，"
                f"但當前短線動能疲弱（短線僅 {short_score} 分）且股價壓在均線下方。"
                f"為防範盲目接飛刀風險，【不建議現價直接買進】。"
                f"建議採取左側防守策略，靜待股價回檔至關鍵支撐"
                f"（如整數關卡或前波低點）或短線止穩後，再動用首批子彈分批低吸。"
            )
            return TradeAdvice(
                action="觀望", style=best_style_name,
                entry_price=None, stop_loss=None,
                current_price=close,
                reason=f"{best_style_name}分 > 70 但觸發飛刀濾網（短線{short_score}分且破5MA）",
                message=msg, risk_level="低",
            )
        else:
            # 優先級 4-A：未破位 → 正常現價買進
            return TradeAdvice(
                action="買進", style=best_style_name,
                entry_price=close, stop_loss=None,
                current_price=close,
                reason=f"{best_style_name}分 > 70 且未觸發飛刀濾網",
                message=(
                    f"策略認領：長線安全邊際。"
                    f"資產品質良好，現價 {close:.2f} 元即可建立基本防禦倉位，"
                    f"拉回分批定額買進。"
                ),
                risk_level="低",
            )

    # 優先級 5：最高分介於 50~70 之間 → 中性觀望
    label_map = {"swing": "波段", "short_term": "短線", "value": "價值", "dividend": "定存"}
    return TradeAdvice(
        action="觀望", style=label_map.get(max_style, max_style),
        current_price=close,
        reason=f"最高分 {max_style} = {max_score}，介於50~70之間，建議觀望",
        message=(
            f"評分中性（最佳 {label_map.get(max_style, max_style)} {max_score}分），"
            f"建議觀望，待分數提升至 70 分以上再考慮進場。"
        ),
        risk_level="中",
    )


# ================================================================
# 已持有狀態
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
) -> TradeAdvice:
    """已持有狀態：四維度獨立投票機制 + 一票通關 + 鐵盾覆蓋"""

    votes = []
    vote_details = {}

    # ---------- 短線投票 ----------
    if close is not None and ma_5 is not None and close > ma_5 and short_score >= 50:
        votes.append("短線")
        vote_details["短線"] = f"贊成（收盤{close}>5MA{ma_5}，短線{short_score}分）"
    else:
        vote_details["短線"] = "反對"

    # ---------- 波段投票 ----------
    if close is not None and ma_20 is not None and close > ma_20 and swing_score >= 55:
        votes.append("波段")
        vote_details["波段"] = f"贊成（收盤{close}>20MA{ma_20}，波段{swing_score}分）"
    else:
        vote_details["波段"] = "反對"

    # ---------- 價值投票（含一票通關例外） ----------
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

    # ---------- 定存投票（⭐不看殖利率） ----------
    if dividend_score >= 50:
        votes.append("定存")
        vote_details["定存"] = f"贊成（定存{dividend_score}分）"
    else:
        vote_details["定存"] = f"反對（定存{dividend_score}分）"

    vote_count = len(votes)
    votes_detail_str = "；".join(f"{k}:{v}" for k, v in vote_details.items())

    # 計算損益
    pnl_str = ""
    if close is not None and average_cost > 0:
        pnl_pct = ((close - average_cost) / average_cost) * 100
        pnl_str = f"（帳面 {pnl_pct:+.2f}%）"

    # 檢查法人連續3日轉負（減碼輔助訊號）
    inst_3d_negative = False
    if "Inst_Net" in df.columns:
        try:
            last_3 = df["Inst_Net"].iloc[-3:].dropna()
            if len(last_3) >= 3:
                inst_3d_negative = all(last_3 < 0)
        except (KeyError, IndexError):
            pass

    # ---------- 鐵盾條件 ----------
    # 價值 > 70 或 定存 > 70，且虧損在5%以內
    is_iron_shield = False
    if (value_score > 70 or dividend_score > 70) and (close is not None and average_cost > 0):
        if close >= (average_cost * 0.95):
            is_iron_shield = True

    # ---------- 決策樹（由上而下） ----------

    # 4票 + 波段 > 65 → 加碼
    if vote_count >= 4 and swing_score > 65:
        return TradeAdvice(
            action="加碼", style="波段",
            entry_price=round(close, 2) if close else None,
            stop_loss=round(ma_20 * 0.95, 2) if ma_20 else None,
            current_price=close,
            reason=f"四維度投票{vote_count}票，全部看好。細節：{votes_detail_str}",
            message=(
                f"【建議逢低加碼】{pnl_str}。"
                f"四維度全數支持持有，趨勢強烈且全面看好，可適度擴大子彈規模。"
            ),
            risk_level="低",
        )

    # 3票 → 持有
    if vote_count == 3:
        entry_ref = round(ma_20, 2) if ma_20 else None
        add_msg = ""
        if entry_ref:
            add_msg = f"若未來股價拉回至月線 {entry_ref} 元附近，可視為右側趨勢的優質補槍點。"
        return TradeAdvice(
            action="持有", style="波段", current_price=close,
            entry_price=entry_ref,
            reason=f"四維度投票{vote_count}票贊成。細節：{votes_detail_str}",
            message=(
                f"【建議繼續持有】{pnl_str}。"
                f"四維度中有三維度支持，切勿因恐高心理過早獲利了結，讓利潤持續奔跑。"
                f"{add_msg}"
            ),
            risk_level="低",
        )

    # 2票 + 法人轉負 → 減碼
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

    # 2票 → 持有觀望
    if vote_count == 2:
        entry_ref = round(ma_20, 2) if ma_20 else None
        add_msg = ""
        if entry_ref:
            add_msg = (
                f"當前短線動能偏弱，現價請勿盲目攤平。"
                f"若欲加碼，建議靜待股價拉回至月線 {entry_ref} 元附近"
                f"且出現止穩訊號時，再動用新子彈。"
            )
        return TradeAdvice(
            action="持有觀望", current_price=close,
            entry_price=entry_ref,
            reason=f"四維度投票2票贊成，邊緣持有。細節：{votes_detail_str}",
            message=(
                f"【建議持有觀望】{pnl_str}。"
                f"四維度僅2票支持，方向尚未明確，建議維持現有部位，密切觀察是否出現賣出訊號。"
                f"{add_msg}"
            ),
            risk_level="中",
        )

    # 1票 或 0票 → 先檢查鐵盾
    if is_iron_shield:
        entry_ref = round(ma_20, 2) if ma_20 else None
        add_msg = ""
        if entry_ref:
            add_msg = (
                f"當前短線動能偏弱，現價請勿盲目攤平。"
                f"若欲加碼，建議靜待股價拉回至月線 {entry_ref} 元附近"
                f"且出現止穩訊號時，再動用新子彈。"
            )
        return TradeAdvice(
            action="持有觀望", current_price=close,
            entry_price=entry_ref,
            reason=(
                f"四維度投票{vote_count}票，但【基本面鐵盾啟動】強制覆蓋。"
                f"細節：{votes_detail_str}"
            ),
            message=(
                f"【建議持有觀望】{pnl_str}。"
                f"雖然技術面破位（僅 {vote_count} 票贊成），"
                f"但因觸發基本面鐵盾防線且虧損在安全範圍內，"
                f"系統強制禁止賤賣資產。請抱緊個股，靜待籌碼落底。"
                f"{add_msg}"
            ),
            risk_level="低",
        )

    # 鐵盾未啟動 → 紀律執行
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
    print("trade_manager.py v4.2（終極閉環版）— 型態認領 + 飛刀濾網 + 四維度投票 + 一票通關 + 鐵盾防線")