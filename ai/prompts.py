"""
ai/prompts.py v4.2
AI 定位為 Explain Engine（解說引擎），非 Decision Engine（決策引擎）

v4.2 變更：
- 納入 1.5Y-CAGR、營收 MA 交叉、流血質檢、產業偏誤等新運算結果
- AI 解說時可引用這些系統計算好的 v4.2 指標
"""

# ============================================================
# System Prompt — 一般分析解說
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

## 輿情數據：系統已計算完成的新聞情緒統計（可選引用）
- 若下方 User Message 中有提供「系統近期新聞輿情統計」區塊，代表有數據可引用
- 數據包含：近期新聞總篇數、平均情緒分數（-1~1）、多空分布
- AI 可引用此數據輔助解說「短線/波段評分與市場氛圍是否一致」
- 若無該區塊，代表無近期新聞數據，**不得自行虛構**

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
# System Prompt — 回測解說（點位解說版）
# ============================================================
BACKTEST_SYSTEM_PROMPT = """你是一位資深的台股操盤手與量化策略分析師。
你接下來要為使用者解說某檔股票在特定策略下的「詳細交易歷程與進出點位」。

【手機直式瀏覽與排版限制 - 鐵律】
1. 表格欄位嚴格限制在 3 欄（日期、價格、動作），文字必須簡練，防止手機畫面破格。
2. 表格「內部」絕對不要出現任何文字解釋或點位評論。
3. 所有對進出點位的深度解說、市場狀態剖析與綜合結論，必須「一律放在整張表格的下方」進行純文字完整呈現。
4. 必須使用繁體中文與台灣股市在地術語（例如：主升段、雙巴、假突破、打底、落袋為安、甩轎）。

【你的輸出格式】
你只能輸出以下固定格式的 JSON，不得包含其他內容：

{
  "backtest_analysis": {
    "summary": "一句話總結這個策略在這檔股票這段期間的整體表現",
    "narrative": "順著時間軸的故事性深度解說。請像一位看著K線圖的分析師，一筆一筆或分階段解說這些點位的時空背景：\\n\\n1. 哪幾筆是「漂亮的起漲點進場」或「完美的高檔停利」？\\n2. 哪幾筆遇到了「假突破或箱型震盪」，導致系統在某段區間慘遭「雙巴（連續停損）」？\\n3. 系統在行情末端（例如高檔回檔期），是盲目追高，還是成功空手避開？",
    "diagnosis": "用幾句話一針見血地指出這個策略在這檔股票上的最大亮點與致命死穴"
  }
}

【關於 50/50 雙彈夾分批建倉策略】
若下方 user message 中含有「雙彈夾策略」區塊，代表本次回測有啟用此機制。
雙彈夾策略的邏輯：
1. 第一發進場：買入訊號出現時，先用 50% 資金打入第一筆。
2. 第二發加碼：有兩種模式：
   - 下跌加碼（dip）：價格從第一發進場價跌 X% 後，打入剩餘 50%。
   - 順勢突破（breakout）：分數創近期新高時打入剩餘 50%。
3. 全數出場：賣出訊號出現時，一次清空所有庫存。
AI 可以在 narrative 中特別點評雙彈夾的加碼時機是否恰當、加碼後是否有效降低成本、以及相較於單筆進場的優劣。
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
# User Message 建構 — 一般分析解說
# ============================================================

def build_user_message(
    stock_id: str,
    stock_name: str,
    scores: dict,
    advice: dict,
    has_position: bool = False,
    avg_price: float = 0.0,
    shares: int = 0,
    trade_advice: object = None,
    sentiment_data: dict = None,
) -> str:
    """
    建構使用者訊息（含 v4.2 新指標 + 持倉判斷 + 可選輿情數據，皆以中文解釋呈現）
    
    Args:
        sentiment_data: 可選，新聞資料庫統計數據，含 avg_score, total_news, signal 等
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
    
    # 持倉判斷（trade_advice）
    if trade_advice is not None:
        ta = trade_advice
        msg += "\n【系統持倉判斷】\n"
        msg += f"- 動作: {ta.action}\n"
        msg += f"- 認領風格: {ta.style}\n"
        msg += f"- 風險等級: {ta.risk_level}\n"
        msg += f"- 判斷理由: {ta.reason}\n"
        if ta.current_price is not None:
            msg += f"- 最新收盤價: {ta.current_price}\n"
        # 雙軌建議價（附交易方式說明）
        agg = getattr(ta, 'agg_entry', None)
        cons = getattr(ta, 'cons_entry', None)
        if agg is not None and ta.current_price is not None:
            if agg > ta.current_price:
                msg += f"- 積極型目標價: {ta.agg_entry_low}~{ta.agg_entry_high} 元（核心 {agg} 元，高於現價，等站回5MA再考慮進場）\n"
            else:
                msg += f"- 積極型建議價: {ta.agg_entry_low}~{ta.agg_entry_high} 元（核心 {agg} 元）\n"
        if cons is not None and ta.current_price is not None:
            if cons > ta.current_price:
                msg += f"- 保守型目標價: {ta.cons_entry_low}~{ta.cons_entry_high} 元（核心 {cons} 元，高於現價，需掛單等拉回）\n"
            else:
                msg += f"- 保守型建議價: {ta.cons_entry_low}~{ta.cons_entry_high} 元（核心 {cons} 元）\n"
        msg += "(AI 解說應與持倉判斷保持一致，不可矛盾)\n"
    
    # 輿情數據（可選 — 有資料才加入，無資料跳過）
    if sentiment_data:
        msg += "\n【系統近期新聞輿情統計】\n"
        msg += f"- 近期新聞總數: {sentiment_data.get('total_news', 0)} 篇\n"
        msg += f"- 平均情緒分數: {sentiment_data.get('avg_score', 0.0):.4f}（範圍 -1 到 1）\n"
        msg += f"- 多空分布: 偏多 {sentiment_data.get('positive_count', 0)} 篇 | 偏空 {sentiment_data.get('negative_count', 0)} 篇 | 中立 {sentiment_data.get('neutral_count', 0)} 篇\n"
        msg += "- 此數據由系統統計完成，AI 可引用輔助解說短線/波段評分與市場氛圍的一致性\n"
    
    return msg


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


# ============================================================
# User Message 建構 — 回測解說
# ============================================================

def build_backtest_system_prompt() -> str:
    """回測 AI 解說的 System Prompt"""
    return BACKTEST_SYSTEM_PROMPT


def build_backtest_user_message(
    stock_id: str,
    stock_name: str,
    strategy_label: str,
    bt_result: object,
) -> str:
    """
    建構回測解說的使用者訊息
    
    Args:
        stock_id: 股票代號
        stock_name: 股票名稱
        strategy_label: 策略名稱（如「積極 60/40」或「保守 70/50」）
        bt_result: BacktestResult 物件
    
    Returns:
        字串，包含完整回測數據供 AI 分析
    """
    msg = f"請幫我針對這檔股票 {stock_id} {stock_name} 的「{strategy_label}」策略核心交易歷程數據進行「點位深度解說」。\n\n"
    
    # ===== 0. 檢查是否有雙彈夾策略 =====
    dual_trades = bt_result.styles.get("dual_bullet", {}).get("trades", [])
    has_dual = len(dual_trades) > 0
    
    if has_dual:
        msg += "【雙彈夾策略】\n"
        msg += "本次回測有啟用 50/50 雙彈夾分批建倉機制。\n"
        db_ret = bt_result.styles["dual_bullet"].get("total_return_pct", 0.0)
        db_count = bt_result.styles["dual_bullet"].get("trade_count", 0)
        msg += f"  雙彈夾: {db_count}筆交易 | 總報酬 {db_ret:+.2f}%\n"
        msg += "雙彈夾交易明細：\n"
        for t in dual_trades:
            entry_date = t.entry_date.strftime("%Y-%m-%d") if hasattr(t.entry_date, "strftime") else str(t.entry_date)
            exit_date = t.exit_date.strftime("%Y-%m-%d") if (t.exit_date and hasattr(t.exit_date, "strftime")) else ("-" if t.exit_date is None else str(t.exit_date))
            p1 = f"第一發@{t.entry_price:.2f}"
            p2 = f""
            if t.entry_price_2 is not None:
                p2 = f" 第二發@{t.entry_price_2:.2f} 均價@{t.avg_cost:.2f}"
            status = f"→ 賣出{exit_date}@{t.exit_price if t.exit_price else '-'} | 報酬{t.return_pct:+.2f}%" if t.status == "已出清" else f"→ 持有中 | 報酬{t.return_pct:+.2f}%"
            msg += f"  {entry_date} {p1}{p2} {status}\n"
        msg += "\n"
    
    # ===== 1. 績效總覽 =====
    msg += "【績效總覽】\n"
    style_names = {
        "short_term": "短線",
        "swing": "波段",
        "value": "價值",
        "dividend": "定存",
        "composite": "綜合",
    }
    for sk, scn in style_names.items():
        sd = bt_result.styles.get(sk, {})
        tc = sd.get("trade_count", 0)
        ret = sd.get("total_return_pct", 0.0)
        wr = sd.get("win_rate", None)
        wr_str = f"{wr:.1f}%" if wr is not None else "N/A"
        msg += f"  {scn}: {tc}筆交易 | 總報酬 {ret:+.2f}% | 勝率 {wr_str}\n"
    msg += "\n"
    
    # ===== 2. 所有交易點位（依時間排序，合併所有風格） =====
    signal_history = bt_result.signal_history
    if signal_history is not None and not signal_history.empty:
        msg += "【核心交易點位歷程】\n"
        msg += "請將所有非 none 的買賣點位依時間順序整理成精簡表格（限 3 欄：日期、價格、動作）。\n\n"
        
        signal_configs = [
            ("short_term", "短線"),
            ("swing", "波段"),
            ("value", "價值"),
            ("dividend", "定存"),
        ]
        
        for style_key, style_cn in signal_configs:
            signal_col = f"{style_key}_signal"
            if signal_col in signal_history.columns:
                styled_df = signal_history[signal_history[signal_col] != "none"][["date", "price", signal_col]].copy()
                if not styled_df.empty:
                    styled_df["date"] = styled_df["date"].dt.strftime("%Y-%m-%d")
                    styled_df["price"] = styled_df["price"].round(2)
                    styled_df = styled_df.rename(columns={signal_col: "動作"})
                    snippet = styled_df.to_string(index=False)
                    msg += f"■ {style_cn}（共 {len(styled_df)} 筆訊號）\n"
                    msg += f"{snippet}\n\n"
        
        # 綜合策略
        composite_trades = bt_result.styles.get("composite", {}).get("trades", [])
        if composite_trades:
            msg += "【綜合策略交易明細】\n"
            for t in composite_trades:
                entry_date = t.entry_date.strftime("%Y-%m-%d") if hasattr(t.entry_date, "strftime") else str(t.entry_date)
                exit_date = t.exit_date.strftime("%Y-%m-%d") if (t.exit_date and hasattr(t.exit_date, "strftime")) else ("-" if t.exit_date is None else str(t.exit_date))
                action = "買入" if t.status == "持有中" else "出清"
                msg += f"  {entry_date} @ {t.entry_price:.2f} → {exit_date} @ {t.exit_price if t.exit_price else '-'} | {action} | 報酬 {t.return_pct:+.2f}%\n"
            msg += "\n"
    
    # ===== 3. 參數資訊 =====
    msg += "【回測參數】\n"
    msg += f"  區間: {bt_result.start_date} ~ {bt_result.end_date}\n"
    msg += f"  頻率: {bt_result.freq}\n"
    msg += f"  買入門檻: ≥{bt_result.buy_threshold} 分\n"
    msg += f"  賣出門檻: <{bt_result.sell_threshold} 分\n"
    
    return msg


if __name__ == "__main__":
    print("prompts.py v4.2 - 整合 v4.2 新指標解說 + 點位回測解說")