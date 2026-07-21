"""
ui/waterfall_debug.py — 瀑布流 5
"""
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime, timedelta
from ui.components import FIELD_CN_MAP, cn, _radar_chart

from core.scorer import get_historical_scores

def render_waterfall_5(st_obj, base, fetch_info, scores, advice, trade_advice, ai_result,
                  stock_id, stock_name, avg_price, shares, has_position,
                  df_taiex, df_price, df_info, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss,
                  selected_profile=None, deepseek_api_key=None, run_bt=False):
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
        with waterfall_5.container():
            st.markdown("---")
            st.subheader("⚠️ 風險提示")
            
            risk_items = []
            if ai_result:
                explanation = ai_result.get("explanation", {})
                if explanation:
                    rw = explanation.get("risk_warning", "")
                    if rw and "無法分析" not in rw and "異常" not in rw:
                        risk_items.append(rw)
            
            # 從數據判斷風險
            latest = base.tail(1)
            if "RSI_6" in latest.columns:
                rsi_val = latest["RSI_6"].iloc[-1]
                if pd.notna(rsi_val) and rsi_val > 80:
                    risk_items.append(f"⚠️ RSI({rsi_val:.1f}) > 80，短線過熱風險")
                elif pd.notna(rsi_val) and rsi_val < 20:
                    risk_items.append(f"⚠️ RSI({rsi_val:.1f}) < 20，短線超賣")
            
            if "MA60_Bias" in latest.columns:
                bias = latest["MA60_Bias"].iloc[-1]
                if pd.notna(bias) and abs(bias) > 30:
                    risk_items.append(f"⚠️ 60日乖離率 {bias:.1f}%，偏離過大")
            
            if "Debt_Ratio" in latest.columns:
                dr = latest["Debt_Ratio"].iloc[-1]
                if pd.notna(dr) and dr > 70:
                    risk_items.append(f"⚠️ 負債比 {dr:.1f}% > 70%，財務風險偏高")
            
            if not risk_items:
                risk_items.append("✅ 目前無顯著風險")
            
            for item in risk_items:
                st.markdown(item)
            
            st.markdown("---")
            
            # 除錯面板
            with st.expander("🔧 除錯面板"):
                tab_debug1, tab_debug2, tab_debug3, tab_debug4, tab_debug5 = st.tabs(["撈取資訊", "計算欄位", "最新數據", "母表欄位", "匯出 CSV"])
                
                # ===== 分頁 1：撈取資訊 =====
                with tab_debug1:
                    st.markdown("**📥 撈取資料摘要**")
                    
                    # 分類顯示
                    categories = {
                        "📈 股價 & 大盤": ["股價 (df_price)", "大盤 (df_taiex)", "基本資料 (df_info)"],
                        "📊 基本面": ["月營收 (df_rev)", "損益表 (df_fin)", "資產負債表 (df_bal)", "現金流量表 (df_cf)", "股利 (df_div)", "本益比 (df_per)"],
                        "🏦 籌碼面": ["三大法人 (df_inst)", "融資券 (df_margin)", "借券 (df_ss)"],
                    }
                    
                    for cat_name, keys in categories.items():
                        st.markdown(f"**{cat_name}**")
                        for key in keys:
                            info = fetch_info.get(key, {})
                            rows = info.get("rows", 0)
                            cols = info.get("cols", [])
                            if rows > 0:
                                st.success(f"✅ {key}: {rows} 行, {len(cols)} 欄")
                            else:
                                st.warning(f"⚠️ {key}: 無資料")
                        st.markdown("---")
                    
                    # 日期範圍
                    st.markdown("**📅 日期範圍**")
                    if not base.empty and "date" in base.columns:
                        min_date = base["date"].min()
                        max_date = base["date"].max()
                        days = (max_date - min_date).days
                        st.caption(f"母表日期範圍: {min_date.strftime('%Y-%m-%d')} ~ {max_date.strftime('%Y-%m-%d')}（共 {days} 天）")
                    
                    # 完整性檢查
                    st.markdown("**🔍 完整性檢查**")
                    needed = ["close", "volume", "MA_5", "MA_10", "MA_20", "MA_60", "RSI_6", "TTM_EPS", "ROE_TTM", "Gross_Margin", "Debt_Ratio", "PE_Percentile", "PB_Percentile", "dividend_yield", "Dividend_Continuity_Years"]
                    available = [c for c in needed if c in base.columns]
                    missing = [c for c in needed if c not in base.columns]
                    st.caption(f"✅ 必要欄位存在: {len(available)}/{len(needed)}")
                    if missing:
                        st.caption(f"❌ 缺少: {', '.join(missing)}")
                
                # ===== 分頁 2：計算欄位 =====
                with tab_debug2:
                    st.markdown("**📊 計算欄位（母表中非原始欄位）**")
                    
                    # 分類
                    derived_categories = {
                        "📈 技術面": ["MA_5", "MA_10", "MA_20", "MA_60", "RSI_6", "MA_Alignment", "Volume_Ratio", "MA60_Bias", "ATR", "High_5D", "High_10D", "High_20D", "Vol_MA_5", "Above_MA_5", "Above_MA_10", "Above_MA_20", "Above_MA_60", "Bullish_MA", "Volume_Above_MA5", "Low_10D", "Consec_Up_Days", "Consec_Down_Days"],
                        "🏦 籌碼面": ["Foreign_Net", "Trust_Net", "Dealer_Net", "Inst_Net", "Inst_5D_Net", "Inst_20D_Net", "Chip_Divergence", "Margin_5D_Change", "Short_5D_Change", "SBL_5D_Change", "Inst_Consecutive_Days"],
                        "📊 基本面": ["Revenue_YoY", "Revenue_MoM", "Revenue_Accelerating", "Revenue_12M_High", "Revenue_6M_High", "Revenue_Momentum", "Price_Revenue_Divergence", "TTM_EPS", "TTM_EPS_Valid", "TTM_FCF", "TTM_OCF", "TTM_OperatingCF", "TTM_CAPEX", "TTM_NetIncome", "ROE_TTM", "ROE_Stability", "ROA_TTM", "Gross_Margin", "Gross_Margin_Stability", "Operating_Margin", "Current_Ratio", "Interest_Coverage", "EPS_Stability", "EPS_YoY", "EPS_YoY_Reason", "Debt_Ratio", "Debt_Ratio_Trend", "PE_Percentile", "PB_Percentile", "pe_ratio", "pb_ratio"],
                        "💰 股利面": ["dividend_yield", "cash_dividend_total", "cash_dividend", "cash_statutory", "Payout_Ratio", "Payout_Ratio_Stability", "FCF_Coverage", "FCF_vs_Dividend", "Dividend_Continuity_Years", "Data_Years_Available"],
                    }
                    
                    all_derived = [c for c in base.columns if c not in ["date", "stock_id"]]
                    st.caption(f"共 {len(all_derived)} 個計算欄位")
                    
                    for cat_name, cat_cols in derived_categories.items():
                        found = [c for c in cat_cols if c in base.columns]
                        not_found = [c for c in cat_cols if c not in base.columns]
                        st.markdown(f"**{cat_name}**（存在 {len(found)}/{len(cat_cols)}）")
                        if found:
                            st.success(f"✅ {', '.join(found)}")
                        if not_found:
                            st.warning(f"❌ 缺少: {', '.join(not_found)}")
                        st.markdown("---")
                
                # ===== 分頁 3：最新數據 =====
                with tab_debug3:
                    st.markdown("**📋 最新一筆數據**")
                    if not base.empty:
                        latest_row = base.tail(1).iloc[0]
                        
                        # 分類顯示
                        latest_categories = {
                            "📈 技術面": ["close", "volume", "MA_5", "MA_10", "MA_20", "MA_60", "RSI_6", "MA_Alignment", "Volume_Ratio", "MA60_Bias", "ATR", "Low_10D", "Consec_Up_Days", "Consec_Down_Days"],
                            "🏦 籌碼面": ["Foreign_Net", "Trust_Net", "Dealer_Net", "Inst_5D_Net", "Inst_20D_Net", "Margin_5D_Change", "Short_5D_Change", "SBL_5D_Change", "Inst_Consecutive_Days"],
                            "📊 基本面": ["Revenue_YoY", "Revenue_MoM", "Revenue_Accelerating", "Revenue_12M_High", "Revenue_6M_High", "Revenue_Momentum", "TTM_EPS", "TTM_EPS_Valid", "TTM_FCF", "TTM_OCF", "ROE_TTM", "ROE_Stability", "ROA_TTM", "Gross_Margin", "Debt_Ratio", "Current_Ratio", "Interest_Coverage", "PE_Percentile", "PB_Percentile"],
                            "💰 股利面": ["dividend_yield", "cash_dividend_total", "Payout_Ratio", "FCF_Coverage", "Dividend_Continuity_Years", "Data_Years_Available"],
                        }
                        
                        for cat_name, cat_cols in latest_categories.items():
                            st.markdown(f"**{cat_name}**")
                            cols_data = []
                            for c in cat_cols:
                                if c in latest_row.index:
                                    val = latest_row[c]
                                    if pd.notna(val):
                                        if isinstance(val, float):
                                            cols_data.append(f"{cn(c)}: {val:.4f}")
                                        else:
                                            cols_data.append(f"{cn(c)}: {val}")
                            if cols_data:
                                st.caption(" | ".join(cols_data))
                            st.markdown("---")
                        
                        # 可展開原始 JSON
                        with st.expander("📄 查看原始 JSON"):
                            latest_dict = {}
                            for col in base.columns:
                                val = latest_row[col]
                                if pd.notna(val):
                                    if isinstance(val, float):
                                        latest_dict[cn(col)] = f"{val:.4f}"
                                    else:
                                        latest_dict[cn(col)] = str(val)
                            st.json(latest_dict)
                
                # ===== 分頁 4：母表欄位 =====
                with tab_debug4:
                    st.markdown("**📋 母表所有欄位（共 {} 個）**".format(len(base.columns)))
                    
                    # 分類統計
                    st.markdown("**分類統計**")
                    for cat_name, cat_cols in derived_categories.items():
                        found = [c for c in cat_cols if c in base.columns]
                        st.caption(f"{cat_name}: {len(found)} 個欄位")
                    
                    # 完整列表
                    with st.expander("📄 查看完整欄位列表"):
                        st.write(list(base.columns))
                
                # ===== 分頁 5：匯出 CSV（改為手動） =====
                with tab_debug5:
                    st.markdown("**💾 匯出 Debug CSV**")
                    st.caption("選擇欄位後，點擊按鈕手動匯出母表 CSV 到 bug/ 目錄")
                    
                    # 選擇要匯出的欄位群組（顯示中文 + 英文對照）
                    _export_options = list(base.columns)
                    _export_labels = {col: f"{col}  ({cn(col)})" for col in _export_options}
                    export_cols = st.multiselect(
                        "選擇要匯出的欄位(預設全部)",
                        options=_export_options,
                        default=_export_options,
                        format_func=lambda x: _export_labels.get(x, x),
                        key="export_cols"
                    )
                    
                    # 匯出合併 CSV（特徵 + 評分）
                    if st.button("💾 匯出除錯 CSV", type="primary"):
                        try:
                            # 匯出選定特徵欄位
                            export_cols_selected = export_cols if export_cols else list(base.columns)
                            export_df = base[export_cols_selected].copy()
                            # 計算並合併歷史評分
                            hist_scores = get_historical_scores(base, freq="D")
                            if not hist_scores.empty:
                                export_df = pd.merge(export_df, hist_scores, on="date", how="left")
                            export_df["date"] = pd.to_datetime(export_df["date"]).dt.strftime("%Y-%m-%d")
                            csv_data = export_df.to_csv(index=False, encoding="utf-8-sig")
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"{stock_id}_{timestamp}_debug.csv"
                            bug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bug")
                            os.makedirs(bug_dir, exist_ok=True)
                            filepath = os.path.join(bug_dir, filename)
                            with open(filepath, "w", encoding="utf-8-sig") as f:
                                f.write(csv_data)
                            st.success(f"✅ 已儲存至：`{filepath}`")
                            st.caption(f"📊 {len(export_df)} 行 x {len(export_df.columns)} 欄")
                        except Exception as ex:
                            st.error(f"❌ 匯出失敗：{ex}")
                    else:
                        st.info("點擊按鈕匯出除錯 CSV（含特徵 + 逐日評分）")
        
        # ===== 瀑布流 6：回測結果摘要（若有執行過） =====