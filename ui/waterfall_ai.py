"""
ui/waterfall_ai.py — 瀑布流 4
"""
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime, timedelta
from ui.components import FIELD_CN_MAP, cn, _radar_chart

def render_waterfall_4(st_obj, base, fetch_info, scores, advice, trade_advice, ai_result,
                  stock_id, stock_name, avg_price, shares, has_position,
                  df_taiex, df_price, df_info, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss,
                  selected_profile=None, deepseek_api_key=None, run_bt=False):
            st.markdown("---")
            st.subheader("📊 四維度分析")
            st.caption("💡 評分解讀：保守型 ≥ 70 分（佳）| 積極型 ≥ 60 分（可考慮進場）| < 50 分（待加強/觀望）")
            
            with st.expander("📋 實盤操作 SOP", expanded=False):
                st.markdown("""
                | 策略 | 實盤操作指引 |
                |:---|:---|
                | 🔴 **短線** | **時效第一** — 出訊號當天收盤價直接買，絕不留單 |
                | 🟠 **波段** | **趨勢第一** — 出訊號當天收盤價直接買，避免看對卻空手 |
                | 🔵 **價值** | **價格第一** — 保留舊單掛限價 **agg_low**，有效期限 3~5 天 |
                | 🟢 **定存** | **成本第一** — 追求高殖利率，保留舊單掛限價 **cons_low** |
                """)
            
            score_labels = {
                "short_term": ("短線", "🔴"),
                "swing": ("波段", "🟠"),
                "value": ("價值", "🔵"),
                "dividend": ("定存", "🟢"),
            }
            
            # 四維度雷達圖配置
            DIMENSION_CONFIG = {
                "short_term": {
                    "title": "🔴 短線",
                    "color": "#E74C3C",
                    "labels": ["趨勢結構", "動能強度", "成交量", "法人籌碼", "籌碼健康", "波動風險"],
                    "weights": [20, 20, 20, 15, 15, 10],
                    "sub_keys": ["trend_structure", "momentum", "volume", "institutional", "chip", "risk"],
                },
                "swing": {
                    "title": "🟠 波段",
                    "color": "#E67E22",
                    "labels": ["營收動能", "中期趨勢", "籌碼趨勢", "獲利成長", "估值位置", "催化因子"],
                    "weights": [25, 20, 20, 15, 10, 10],
                    "sub_keys": ["revenue_momentum", "mid_trend", "institutional_trend", "earnings_growth", "valuation", "catalyst"],
                },
                "value": {
                    "title": "🔵 價值",
                    "color": "#2980B9",
                    "labels": ["估值安全", "獲利品質", "成長能力", "財務安全", "現金流品質", "股東報酬"],
                    "weights": [15, 20, 30, 15, 10, 10],
                    "sub_keys": ["valuation_safety", "profit_quality", "growth_ability", "financial_safety", "cash_flow_quality", "shareholder_return"],
                },
                "dividend": {
                    "title": "🟢 定存",
                    "color": "#27AE60",
                    "labels": ["配息紀錄", "配息品質", "現金流", "財務安全", "獲利穩定", "長期成長"],
                    "weights": [25, 20, 20, 15, 10, 10],
                    "sub_keys": ["dividend_record", "dividend_quality", "cash_flow", "financial_safety", "profit_stability", "long_term_growth"],
                },
            }
            
            # 第一排雷達圖：短線買 + 短線賣 + 波段買 + 波段賣（4 欄）
            st.markdown("**📊 四維度評分六邊形雷達圖**")
            st.caption("短線/波段顯示買入/賣出雙軌評分，價值/定存顯示單一總分")
            
            # 提取分數
            st_data = {k: scores.get(k, {}) for k in ["short_term", "swing", "value", "dividend"]}
            st_buy = {k: v.get("total_buy", v.get("total", 0)) for k, v in st_data.items()}
            st_sell = {k: v.get("total_sell", st_buy[k]) for k, v in st_data.items()}
            
            # 第一排：短線買、短線賣、波段買、波段賣（4 個雷達圖）
            radar_row1 = st.columns(4)
            dual_keys = [
                ("short_term", "買", "🟢"),
                ("short_term", "賣", "🔴"),
                ("swing", "買", "🟢"),
                ("swing", "賣", "🔴"),
            ]
            # v3.0: short_term 支援 8 子項，從 scores 中讀取 profile 權重決定雷達圖標籤
            _st_profile = st_data["short_term"].get("profile", None)
            _is_v3 = _st_profile is not None and "inertia_break" in st_data["short_term"].get("breakdown", {})
            _st_labels_8 = ["趨勢結構", "動能強度", "成交量", "法人籌碼", "籌碼健康", "波動風險", "慣性突破", "籌碼集中"]
            _st_keys_8 = ["trend_structure", "momentum", "volume", "institutional", "chip", "risk", "inertia_break", "chip_concentration"]
            for idx, (dk, mode, mode_icon) in enumerate(dual_keys):
                with radar_row1[idx]:
                    sd = st_data[dk]
                    bd = sd.get("breakdown", {})
                    sub_keys = _st_keys_8 if _is_v3 and dk == "short_term" else ["revenue_momentum", "mid_trend", "institutional_trend", "earnings_growth", "valuation", "catalyst"]
                    score = st_buy[dk] if mode == "買" else st_sell[dk]
                    # 根據買/賣模式 + profile 決定雷達圖標籤權重
                    if dk == "short_term" and _is_v3:
                        from core.scoring_config import STYLE_PROFILES
                        pw = STYLE_PROFILES[_st_profile]["buy" if mode == "買" else "sell"]
                        weights_8 = [int(pw[k] * 100) for k in _st_keys_8]
                        labels = _st_labels_8
                        color = "#E74C3C"
                        base_title = "🔴 短線"
                    elif dk == "short_term":
                        weights_8 = [20, 20, 20, 15, 15, 10]
                        labels = ["趨勢結構", "動能強度", "成交量", "法人籌碼", "籌碼健康", "波動風險"]
                        color = "#E74C3C"
                        base_title = "🔴 短線"
                    else:
                        weights_8 = [25, 20, 20, 15, 10, 10]
                        labels = ["營收動能", "中期趨勢", "籌碼趨勢", "獲利成長", "估值位置", "催化因子"]
                        color = "#E67E22"
                        base_title = "🟠 波段"
                    vals = [bd.get(sk, 0) for sk in sub_keys]
                    full_title = f"{base_title} {mode_icon}{mode} {score}"
                    fig = _radar_chart(labels, vals, full_title, color, weights_8)
                    st.pyplot(fig, use_container_width=True)
                    plt.close()
                    # v3.0: 短線買賣使用各自權重顯示細項
                    if dk == "short_term" and _is_v3:
                        _pw = pw  # 已計算的買/賣權重
                    else:
                        _pw = None
                    breakdown_labels = {
                        # 短線（short_term）
                        "trend_structure": ("趨勢結構", _pw["trend_structure"] * 100 if _pw else 20),
                        "momentum": ("動能強度", _pw["momentum"] * 100 if _pw else 20),
                        "volume": ("成交量結構", _pw["volume"] * 100 if _pw else 20),
                        "institutional": ("法人籌碼", _pw["institutional"] * 100 if _pw else 15),
                        "chip": ("籌碼健康", _pw["chip"] * 100 if _pw else 15),
                        "risk": ("波動風險", _pw["risk"] * 100 if _pw else 10),
                        "inertia_break": ("慣性突破", _pw["inertia_break"] * 100 if _pw else 0),
                        "chip_concentration": ("籌碼集中", _pw["chip_concentration"] * 100 if _pw else 0),
                        # 波段（swing）
                        "revenue_momentum": ("營收動能", 25),
                        "mid_trend": ("中期趨勢", 20),
                        "institutional_trend": ("籌碼趨勢", 20),
                        "earnings_growth": ("獲利成長", 15),
                        "valuation": ("估值位置", 10),
                        "catalyst": ("催化因子", 10),
                    }
                    with st.expander("查看細項"):
                        st.markdown("**各子項評分明細**")
                        details = sd.get("details", {})
                        for sub_key, sub_val in bd.items():
                            info = breakdown_labels.get(sub_key)
                            if info:
                                cn_name, weight = info
                                pct = sub_val / 100.0
                                if sub_val >= 80:
                                    emoji = "🟢"
                                elif sub_val >= 60:
                                    emoji = "🟡"
                                elif sub_val >= 30:
                                    emoji = "🟠"
                                else:
                                    emoji = "🔴"
                                st.markdown(f"{emoji} **{cn_name}**（權重 {weight}%）: **{sub_val}/100**")
                                st.progress(pct)
                                
                                sub_details = details.get(sub_key, {})
                                if sub_details:
                                    raw_items = []
                                    score_items = []
                                    for dk2, dv in sub_details.items():
                                        if dv is not None and not (isinstance(dv, float) and pd.isna(dv)):
                                            dk_cn = cn(dk2)
                                            if isinstance(dv, float):
                                                text = f"{dk_cn}: {dv:.2f}"
                                            else:
                                                text = f"{dk_cn}: {dv}"
                                            if "_score" in dk2:
                                                score_items.append(text)
                                            else:
                                                raw_items.append(text)
                                    if raw_items:
                                        st.caption("📊 原始數據：")
                                        for item in raw_items:
                                            st.caption(item)
                                    if score_items:
                                        st.caption("📋 評分結果：")
                                        for item in score_items:
                                            st.caption(item)
                            else:
                                st.caption(f"⚪ {sub_key}: {sub_val}/100")
                        
                        modifiers = sd.get("modifiers", {})
                        if modifiers:
                            st.markdown("---")
                            st.markdown("**⚙️ 調整因子**")
                            for mod_key, mod_val in modifiers.items():
                                if isinstance(mod_val, dict):
                                    mod_parts = [f"{mk}: {mv}" for mk, mv in mod_val.items()]
                                    st.caption(f"  {mod_key}: {', '.join(mod_parts)}")
                                else:
                                    st.caption(f"  {mod_key}: {mod_val}")
            
            st.markdown("---")
            
            # 第二排：價值 + 定存（2 欄），附"查看細項"
            radar_row2 = st.columns(2)
            single_keys = ["value", "dividend"]
            single_cfg = {
                "value": ("🔵 價值", "#2980B9", ["估值安全", "獲利品質", "成長能力", "財務安全", "現金流品質", "股東報酬"], [15,20,30,15,10,10], ["valuation_safety", "profit_quality", "growth_ability", "financial_safety", "cash_flow_quality", "shareholder_return"]),
                "dividend": ("🟢 定存", "#27AE60", ["配息紀錄", "配息品質", "現金流", "財務安全", "獲利穩定", "長期成長"], [25,20,20,15,10,10], ["dividend_record", "dividend_quality", "cash_flow", "financial_safety", "profit_stability", "long_term_growth"]),
            }
            for idx, sk in enumerate(single_keys):
                with radar_row2[idx]:
                    base_title, color, labels, weights, sub_keys = single_cfg[sk]
                    sd = st_data[sk]
                    bd = sd.get("breakdown", {})
                    vals = [bd.get(sk, 0) for sk in sub_keys]
                    total = st_buy[sk]
                    full_title = f"{base_title} {total}"
                    fig = _radar_chart(labels, vals, full_title, color, weights)
                    st.pyplot(fig, use_container_width=True)
                    plt.close()
                    st.metric(f"{base_title}", f"{total}/100")
                    # 雷達圖下方直接接「查看細項」
                    breakdown_labels = {
                        # 短線（short_term）
                        "trend_structure": ("趨勢結構", 20),
                        "momentum": ("動能強度", 20),
                        "volume": ("成交量結構", 20),
                        "institutional": ("法人籌碼", 15),
                        "chip": ("籌碼健康", 15),
                        "risk": ("波動風險", 10),
                        # 波段（swing）
                        "revenue_momentum": ("營收動能", 25),
                        "mid_trend": ("中期趨勢", 20),
                        "institutional_trend": ("籌碼趨勢", 20),
                        "earnings_growth": ("獲利成長", 15),
                        "valuation": ("估值位置", 10),
                        "catalyst": ("催化因子", 10),
                        # 價值（value）
                        "valuation_safety": ("估值安全", 15),
                        "profit_quality": ("獲利品質", 20),
                        "growth_ability": ("成長能力", 30),
                        "financial_safety": ("財務安全", 15),
                        "cash_flow_quality": ("現金流品質", 10),
                        "shareholder_return": ("股東報酬", 10),
                        # 定存（dividend）
                        "dividend_record": ("配息紀錄", 25),
                        "dividend_quality": ("配息品質", 20),
                        "cash_flow": ("現金流", 20),
                        "financial_safety": ("財務安全", 15),
                        "profit_stability": ("獲利穩定", 10),
                        "long_term_growth": ("長期成長", 10),
                    }
                    with st.expander("查看細項"):
                        st.markdown("**各子項評分明細**")
                        details = sd.get("details", {})
                        for sub_key, sub_val in bd.items():
                            info = breakdown_labels.get(sub_key)
                            if info:
                                cn_name, weight = info
                                pct = sub_val / 100.0
                                if sub_val >= 80:
                                    emoji = "🟢"
                                elif sub_val >= 60:
                                    emoji = "🟡"
                                elif sub_val >= 30:
                                    emoji = "🟠"
                                else:
                                    emoji = "🔴"
                                st.markdown(f"{emoji} **{cn_name}**（權重 {weight}%）: **{sub_val}/100**")
                                st.progress(pct)
                                
                                sub_details = details.get(sub_key, {})
                                if sub_details:
                                    raw_items = []
                                    score_items = []
                                    for dk, dv in sub_details.items():
                                        if dv is not None and not (isinstance(dv, float) and pd.isna(dv)):
                                            dk_cn = cn(dk)
                                            if isinstance(dv, float):
                                                text = f"{dk_cn}: {dv:.2f}"
                                            else:
                                                text = f"{dk_cn}: {dv}"
                                            if "_score" in dk:
                                                score_items.append(text)
                                            else:
                                                raw_items.append(text)
                                    if raw_items:
                                        st.caption("📊 原始數據：")
                                        for item in raw_items:
                                            st.caption(item)
                                    if score_items:
                                        st.caption("📋 評分結果：")
                                        for item in score_items:
                                            st.caption(item)
                            else:
                                st.caption(f"⚪ {sub_key}: {sub_val}/100")
                        
                        modifiers = sd.get("modifiers", {})
                        if modifiers:
                            st.markdown("---")
                            st.markdown("**⚙️ 調整因子**")
                            for mod_key, mod_val in modifiers.items():
                                if isinstance(mod_val, dict):
                                    mod_parts = [f"{mk}: {mv}" for mk, mv in mod_val.items()]
                                    st.caption(f"  {mod_key}: {', '.join(mod_parts)}")
                                else:
                                    st.caption(f"  {mod_key}: {mod_val}")
            
            st.markdown("---")
            
            # 基本建議
            st.subheader("💡 基本建議")
            advice_text = advice.get("advice", "持有")
            best_style = advice.get("best_style", "")
            best_score = advice.get("best_score", 0)
            style_names = {"short_term": "短線", "swing": "波段", "value": "價值", "dividend": "定存"}
            best_style_name = style_names.get(best_style, best_style)
            
            # 檢查 trade_advice 是否為觀望/不建議（飛刀濾網情境）
            # 若是，覆蓋 get_advice 的買進建議，避免兩種建議矛盾
            ta_action = trade_advice.action if trade_advice else ""
            if trade_advice and ta_action in ("觀望", "不建議"):
                st.info(f"ℹ️ 基本建議：觀望（各風格分數最高為 {best_style_name} {best_score}/100，但觸發安全濾網）")
            elif advice_text in ["強烈買進", "買進"]:
                st.success(f"✅ 建議：{advice_text}（最佳風格：{best_style_name}，{best_score}/100）")
            elif advice_text in ["持有"]:
                st.info(f"ℹ️ 建議：{advice_text}（最佳風格：{best_style_name}，{best_score}/100）")
            else:
                st.warning(f"⚠️ 建議：{advice_text}（最佳風格：{best_style_name}，{best_score}/100）")
            
            # 持倉建議（trade_manager）
            st.subheader("🎯 持倉建議")
            if trade_advice:
                ta = trade_advice
                # 使用 st.markdown 取代 st.info/st.warning，確保 \n 換行正確渲染
                display_msg = ta.message.replace('\n', '  \n')  # markdown 換行需要行尾兩個空格
                if ta.action in ("買進", "加碼"):
                    st.success(display_msg)
                elif ta.action in ("賣出", "減碼", "不建議"):
                    st.warning(display_msg)
                else:
                    st.info(display_msg)
                
                # 顯示詳細資訊
                with st.expander("📋 持倉判斷明細"):
                    st.caption(f"動作：{ta.action}")
                    st.caption(f"認領風格：{ta.style}")
                    
                    # 主導建議買價區間（僅買進/加碼時顯示）
                    is_buy_action = ta.action in ("買進", "加碼")
                    is_watch_action = ta.action in ("觀望", "不建議")
                    if is_buy_action and ta.entry_price is not None:
                        if ta.entry_price_low is not None and ta.entry_price_high is not None:
                            st.caption(f"🎯 主導建議買價區間：{ta.entry_price_low:.2f} ~ {ta.entry_price_high:.2f} 元（核心 {ta.entry_price:.2f} 元）")
                        else:
                            st.caption(f"🎯 建議買入價：{ta.entry_price:.2f} 元")
                    
                    # 雙軌價位已在主訊息中顯示，此處不重複
                    
                    if ta.stop_loss:
                        st.caption(f"建議停損價：{ta.stop_loss:.2f}")
                    if ta.current_price:
                        st.caption(f"最新收盤價：{ta.current_price:.2f}")
                    if ta.reference_ma:
                        st.caption(f"參考均線：{ta.ma_type} = {ta.reference_ma:.2f}")
                    st.caption(f"風險等級：{ta.risk_level}")
                    st.caption(f"判斷理由：{ta.reason}")
            else:
                st.info("持倉判斷暫時無法產生（資料不足）")
        
        # ===== 瀑布流 4：AI 解說完成 → AI 解說區塊 =====
        with waterfall_4.container():
            st.markdown("---")
            st.subheader("🤖 AI 解說")
            
            if ai_result:
                explanation = ai_result.get("explanation", {})
                
                if explanation and "summary" in explanation:
                    st.markdown(f"**📝 總結**")
                    st.info(explanation["summary"])
                    
                    st.markdown("**✅ 加分原因（Top3）**")
                    strengths = explanation.get("strengths", [])
                    if strengths:
                        for s in strengths:
                            rank = s.get("rank", 1)
                            style = s.get("style", "")
                            item = s.get("item", "")
                            score = s.get("score", 0)
                            reason = s.get("reason", "")
                            st.markdown(f"{rank}. **{style} - {item}**：{score} 分")
                            st.caption(reason)
                    else:
                        st.caption("無顯著加分項目")
                    
                    st.markdown("**❌ 扣分原因（Top3）**")
                    weaknesses = explanation.get("weaknesses", [])
                    if weaknesses:
                        for w in weaknesses:
                            rank = w.get("rank", 1)
                            style = w.get("style", "")
                            item = w.get("item", "")
                            score = w.get("score", 0)
                            reason = w.get("reason", "")
                            st.markdown(f"{rank}. **{style} - {item}**：{score} 分")
                            st.caption(reason)
                    else:
                        st.caption("無顯著扣分項目")
                    
                    st.markdown("**👥 適合族群**")
                    suitable = explanation.get("suitable_for", "無法判斷")
                    st.markdown(f"{suitable}")
                    
                    st.markdown("**⚠️ 風險提醒**")
                    risk = explanation.get("risk_warning", "無")
                    st.warning(risk)
                    
                    st.markdown("**🔍 後續觀察重點**")
                    watch_items = explanation.get("watch_items", [])
                    if watch_items:
                        for i, item in enumerate(watch_items, 1):
                            st.markdown(f"{i}. {item}")
                    else:
                        st.caption("無特定觀察重點")
                    
                    if "evidence" in ai_result and ai_result["evidence"]:
                        with st.expander("📋 查看評分證據（Evidence JSON）"):
                            st.json(ai_result["evidence"])
                else:
                    st.info("AI 解說暫時不可用")
            else:
                st.info("🤖 請輸入 DeepSeek API Key 以獲得 AI 解說")
        
        # ===== 瀑布流 5：最後 → 風險提示 + 除錯面板 =====