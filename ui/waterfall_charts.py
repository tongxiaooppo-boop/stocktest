"""
ui/waterfall_charts.py — 瀑布流 2
"""
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime, timedelta
from ui.components import FIELD_CN_MAP, cn, _radar_chart

from data.processor import _pivot_financial_statements
from news.database import get_aggregate_sentiment, get_historical_sentiment
from news.analyzer import get_sentiment_label, get_sentiment_color
from news.fetcher import fetch_news
from news.analyzer import analyze as analyze_news
from news.database import save_news
from core.backtest import _calc_realized_return_sum, _calc_unrealized_return

def render_waterfall_2(st_obj, base, fetch_info, scores, advice, trade_advice, ai_result,
                  stock_id, stock_name, avg_price, shares, has_position,
                  df_taiex, df_price, df_info, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss,
                  selected_profile=None, deepseek_api_key=None, run_bt=False):
            # 大盤資訊卡
            st.subheader("📊 大盤資訊")
            if df_taiex is not None and not df_taiex.empty:
                taiex_latest = df_taiex.tail(1)
                taiex_close = taiex_latest["close"].iloc[-1] if "close" in taiex_latest.columns else None
                taiex_prev = df_taiex["close"].iloc[-2] if len(df_taiex) >= 2 and "close" in df_taiex.columns else None
                taiex_money = taiex_latest["trading_money"].iloc[-1] if "trading_money" in taiex_latest.columns else None
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if taiex_close:
                        st.metric("加權指數", f"{taiex_close:,.2f}")
                with col2:
                    if taiex_close and taiex_prev:
                        change = taiex_close - taiex_prev
                        change_pct = (change / taiex_prev) * 100
                        st.metric("漲跌幅", f"{change_pct:+.2f}%", f"{change:+.2f}")
                with col3:
                    if taiex_money:
                        st.metric("總成交金額", f"{taiex_money/100000000:,.2f} 億")
            else:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("加權指數", "N/A")
                with col2:
                    st.metric("漲跌幅", "N/A")
                with col3:
                    st.metric("總成交量", "N/A")
    
            st.markdown("---")
            
            # 個股資訊卡
            st.subheader(f"📋 個股資訊：{stock_id} {stock_name}")
            
            latest_price = base.tail(1)
            if len(latest_price) > 0:
                close_price = latest_price["close"].iloc[-1] if "close" in latest_price.columns else None
                prev_close = base["close"].iloc[-2] if len(base) >= 2 and "close" in base.columns else None
                volume = latest_price["volume"].iloc[-1] if "volume" in latest_price.columns else None
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    if close_price:
                        st.metric("股價", f"{close_price:,.2f}")
                with col2:
                    if close_price and prev_close:
                        change = close_price - prev_close
                        change_pct = (change / prev_close) * 100
                        st.metric("漲跌幅", f"{change_pct:+.2f}%", f"{change:+.2f}")
                with col3:
                    if volume:
                        st.metric("成交量", f"{volume/1000:,.0f} 張")
                with col4:
                    if "pe_ratio" in latest_price.columns:
                        pe = latest_price["pe_ratio"].iloc[-1]
                        st.metric("本益比", f"{pe:.2f}" if pd.notna(pe) else "N/A")
            else:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("股價", "N/A")
                with col2:
                    st.metric("漲跌幅", "N/A")
                with col3:
                    st.metric("成交量", "N/A")
                with col4:
                    st.metric("本益比", "N/A")
        
        # ===== 瀑布流 2：計算指標完成 → 圖表區 =====
        with waterfall_2.container():
            st.markdown("---")
            st.subheader("📈 圖表分析")
            
            # 回測分析按鈕觸發 — 每次點擊側邊欄都重置觸發鎖，允許重新執行
            if backtest_btn:
                st.session_state["run_backtest"] = True
                st.session_state["_bt_trigger"] = None  # 重置觸發鎖，允許修改邊界後再執行
            
            run_bt = st.session_state.get("run_backtest", False)
            
            # 使用 selectbox 取代 st.tabs，避免 rerun 後跳回第一個 tab
            tab_options = ["短線面", "中長線面", "📊 回測分析", "📰 新聞輿情"]
            tab_default = st.session_state.get("_active_tab", 0)
            if "_active_tab" not in st.session_state:
                st.session_state["_active_tab"] = 0
            tab_labels = " | ".join([f"{'📌' if i == st.session_state['_active_tab'] else '  '} {t}" for i, t in enumerate(tab_options)])
            st.caption(tab_labels)
            
            # 隱藏 tab 按鍵，直接用 columns 按鈕
            col_tab1, col_tab2, col_tab3, col_tab4 = st.columns(4)
            with col_tab1:
                if st.button("短線面", use_container_width=True, 
                             type="primary" if st.session_state["_active_tab"] == 0 else "secondary",
                             key="tab_btn_0"):
                    st.session_state["_active_tab"] = 0
                    st.rerun()
            with col_tab2:
                if st.button("中長線面", use_container_width=True,
                             type="primary" if st.session_state["_active_tab"] == 1 else "secondary",
                             key="tab_btn_1"):
                    st.session_state["_active_tab"] = 1
                    st.rerun()
            with col_tab3:
                if st.button("📊 回測分析", use_container_width=True,
                             type="primary" if st.session_state["_active_tab"] == 2 else "secondary",
                             key="tab_btn_2"):
                    st.session_state["_active_tab"] = 2
                    st.rerun()
            with col_tab4:
                if st.button("📰 新聞輿情", use_container_width=True,
                             type="primary" if st.session_state["_active_tab"] == 3 else "secondary",
                             key="tab_btn_3"):
                    st.session_state["_active_tab"] = 3
                    st.rerun()
            
            # Tab 0: 短線面
            if st.session_state["_active_tab"] == 0:
                st.markdown("**短線面圖表（近 1 個月）**")
                
                # 過濾近 1 個月資料（約 21 個交易日）
                base_short = base.tail(21).copy()
                
                # 圖表 1: K線 + 均線
                fig1, axes = plt.subplots(3, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3, 1, 1]})
                
                # 子圖 1: 股價 + 均線
                ax1 = axes[0]
                if "close" in base_short.columns:
                    ax1.plot(base_short["date"], base_short["close"], label="收盤價", color="black", linewidth=1.5)
                    for ma, color, style in [("MA_5", "red", "--"), ("MA_10", "orange", "--"), ("MA_20", "blue", "--")]:
                        if ma in base_short.columns:
                            ax1.plot(base_short["date"], base_short[ma], label=ma, color=color, linestyle=style, linewidth=1)
                ax1.set_title(f"{stock_id} {stock_name} - 股價與均線（近1個月）")
                ax1.set_ylabel("價格")
                ax1.legend(loc="best")
                ax1.grid(True, alpha=0.3)
                
                # 子圖 2: 成交量
                ax2 = axes[1]
                if "volume" in base_short.columns:
                    colors = ["red" if base_short["close"].iloc[i] >= base_short["open"].iloc[i] else "green" 
                             for i in range(len(base_short))] if "open" in base_short.columns else ["blue"] * len(base_short)
                    ax2.bar(base_short["date"], base_short["volume"], color=colors, alpha=0.6, width=1)
                ax2.set_ylabel("成交量")
                ax2.grid(True, alpha=0.3)
                
                # 子圖 3: RSI
                ax3 = axes[2]
                if "RSI_6" in base_short.columns:
                    ax3.plot(base_short["date"], base_short["RSI_6"], label="RSI(6)", color="purple", linewidth=1.5)
                    ax3.axhline(y=80, color="red", linestyle="--", alpha=0.5, label="超買(80)")
                    ax3.axhline(y=20, color="green", linestyle="--", alpha=0.5, label="超賣(20)")
                ax3.set_ylabel("RSI")
                ax3.set_xlabel("日期")
                ax3.legend(loc="best")
                ax3.grid(True, alpha=0.3)
                
                plt.tight_layout()
                st.pyplot(fig1)
                plt.close()
                
                # 短線面數據表格
                st.markdown("**短線面數據表格（最近10筆）**")
                short_cols = ["date", "close", "volume", "MA_5", "MA_10", "MA_20", "RSI_6", "Inst_5D_Net"]
                available_short = [c for c in short_cols if c in base.columns]
                if available_short:
                    df_short = base[available_short].tail(10).copy()
                    df_short["date"] = df_short["date"].dt.strftime("%Y-%m-%d")
                    for col in df_short.columns:
                        if col != "date":
                            df_short[col] = df_short[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "N/A")
                    df_short = df_short.rename(columns=lambda c: f"{cn(c)} ({c})" if c != "date" else c)
                    st.dataframe(df_short, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                
                # 圖表 2: 法人買賣超 + 股價（近 1 個月）
                fig2, axes2 = plt.subplots(2, 1, figsize=(12, 7))
                
                ax_inst = axes2[0]
                inst_daily = {"Foreign_Net": "外資", "Trust_Net": "投信", "Dealer_Net": "自營商"}
                for col, label in inst_daily.items():
                    if col in base_short.columns:
                        ax_inst.bar(base_short["date"], base_short[col], label=label, alpha=0.6, width=1)
                # 疊加股價線（右軸）
                if "close" in base_short.columns:
                    ax_inst_price = ax_inst.twinx()
                    ax_inst_price.plot(base_short["date"], base_short["close"], label="收盤價", color="black", linewidth=1.5, linestyle="-")
                    ax_inst_price.set_ylabel("股價")
                    ax_inst_price.legend(loc="upper right")
                ax_inst.set_title("三大法人買賣超 + 股價（每日，近1個月）")
                ax_inst.set_ylabel("買賣超")
                ax_inst.legend(loc="upper left")
                ax_inst.grid(True, alpha=0.3)
                
                ax_margin = axes2[1]
                if "Margin_5D_Change" in base_short.columns:
                    ax_margin.bar(base_short["date"], base_short["Margin_5D_Change"], label="融資5日變化", alpha=0.6, width=1, color="orange")
                if "Short_5D_Change" in base_short.columns:
                    ax_margin.bar(base_short["date"], base_short["Short_5D_Change"], label="融券5日變化", alpha=0.6, width=1, color="purple")
                # 疊加股價線（右軸）
                if "close" in base_short.columns:
                    ax_margin_price = ax_margin.twinx()
                    ax_margin_price.plot(base_short["date"], base_short["close"], label="收盤價", color="black", linewidth=1.5, linestyle="-")
                    ax_margin_price.set_ylabel("股價")
                    ax_margin_price.legend(loc="upper right")
                ax_margin.set_title("融資券5日變化 + 股價（近1個月）")
                ax_margin.set_ylabel("變化量")
                ax_margin.legend(loc="upper left")
                ax_margin.grid(True, alpha=0.3)
                
                plt.tight_layout()
                st.pyplot(fig2)
                plt.close()
                
                # 籌碼面數據表格
                st.markdown("**籌碼面數據表格（最近10筆）**")
                chip_cols = ["date"]
                for c in ["Foreign_Net", "Trust_Net", "Dealer_Net"]:
                    chip_cols.append(c)
                chip_cols.extend(["Margin_5D_Change", "Short_5D_Change"])
                available_chip = [c for c in chip_cols if c in base.columns]
                if available_chip:
                    df_chip = base[available_chip].tail(10).copy()
                    df_chip["date"] = df_chip["date"].dt.strftime("%Y-%m-%d")
                    for col in df_chip.columns:
                        if col != "date":
                            df_chip[col] = df_chip[col].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
                    df_chip = df_chip.rename(columns=lambda c: f"{cn(c)} ({c})" if c != "date" else c)
                    st.dataframe(df_chip, use_container_width=True, hide_index=True)
            
            # Tab 1: 中長線面
            elif st.session_state["_active_tab"] == 1:
                # 中長線 → 依三種評分風格權重最高的維度分 tab
                tab2a, tab2b, tab2c = st.tabs(["🟠 波段動能 (營收+趨勢+籌碼)", "🔵 價值成長 (ROE+EPS+毛利率)", "🟢 定存安全 (股利+負債+PE/PB)"])
                
                # ---- 先建好共用的 df_fin_pivot ----
                fin_raw_list = []
                for df_fin_raw in [df_fin, df_bal, df_cf]:
                    if df_fin_raw is not None and not df_fin_raw.empty:
                        fin_raw_list.append(df_fin_raw)
                df_fin_pivot = None
                if fin_raw_list:
                    df_fin_all = pd.concat(fin_raw_list, ignore_index=True)
                    df_fin_pivot = _pivot_financial_statements(df_fin_all)
                    if df_fin_pivot is not None and not df_fin_pivot.empty:
                        df_fin_pivot = df_fin_pivot.sort_values("date")
                        if "EPS" in df_fin_pivot.columns:
                            df_fin_pivot["TTM_EPS"] = df_fin_pivot["EPS"].rolling(window=4, min_periods=4).sum()
                        if "IncomeAfterTaxes" in df_fin_pivot.columns and "Equity" in df_fin_pivot.columns:
                            df_fin_pivot["TTM_NetIncome"] = df_fin_pivot["IncomeAfterTaxes"].rolling(window=4, min_periods=4).sum()
                            df_fin_pivot["ROE_TTM"] = (df_fin_pivot["TTM_NetIncome"] / df_fin_pivot["Equity"].replace(0, np.nan)) * 100
                        if "GrossProfit" in df_fin_pivot.columns and "Revenue" in df_fin_pivot.columns:
                            df_fin_pivot["Gross_Margin"] = (df_fin_pivot["GrossProfit"] / df_fin_pivot["Revenue"].replace(0, np.nan)) * 100
                        if "Liabilities" in df_fin_pivot.columns and "TotalAssets" in df_fin_pivot.columns:
                            df_fin_pivot["Debt_Ratio"] = (df_fin_pivot["Liabilities"] / df_fin_pivot["TotalAssets"].replace(0, np.nan)) * 100
                        if "CashFlowsFromOperatingActivities" in df_fin_pivot.columns and "PropertyAndPlantAndEquipment" in df_fin_pivot.columns:
                            df_fin_pivot["TTM_OperatingCF"] = df_fin_pivot["CashFlowsFromOperatingActivities"].rolling(window=4, min_periods=4).sum()
                            df_fin_pivot["TTM_CAPEX"] = df_fin_pivot["PropertyAndPlantAndEquipment"].rolling(window=4, min_periods=4).sum()
                            df_fin_pivot["TTM_FCF"] = df_fin_pivot["TTM_OperatingCF"] - df_fin_pivot["TTM_CAPEX"]
                
                # ===== tab2a: 波段動能（權重合計 65%） =====
                with tab2a:
                    st.markdown("**波段評分權重最高：營收動能 25% + 中期趨勢 20% + 籌碼趨勢 20%**")
                    
                    # 圖表 1: 營收 YoY + 股價（從母表，約 1 年區間，日頻走勢）
                    fig_sw1, ax_sw1 = plt.subplots(figsize=(12, 4))
                    ax_sw1b = ax_sw1.twinx()
                    if "Revenue_YoY" in base.columns:
                        ax_sw1.plot(base["date"], base["Revenue_YoY"], label="營收 YoY", color="green", linewidth=1.5)
                        ax_sw1.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
                    if "close" in base.columns:
                        ax_sw1b.plot(base["date"], base["close"], label="收盤價", color="black", linewidth=1, linestyle=":", alpha=0.6)
                        ax_sw1b.set_ylabel("股價")
                    ax_sw1.set_ylabel("YoY (%)")
                    ax_sw1.legend(loc="upper left")
                    ax_sw1b.legend(loc="upper right")
                    ax_sw1.grid(True, alpha=0.3)
                    ax_sw1.set_title(f"{stock_id} {stock_name} - 營收年增率 YoY + 股價（權重 25%）")
                    plt.tight_layout()
                    st.pyplot(fig_sw1)
                    plt.close()
                    
                    st.markdown("---")
                    
                    # 圖表 2: 股價 + MA20/MA60（中期趨勢，近 60 日）
                    fig_sw2, ax_sw2 = plt.subplots(figsize=(12, 4))
                    base_sw2 = base.tail(60).copy()
                    if "close" in base_sw2.columns:
                        ax_sw2.plot(base_sw2["date"], base_sw2["close"], label="收盤價", color="black", linewidth=1.5)
                    for ma, color in [("MA_20", "blue"), ("MA_60", "red")]:
                        if ma in base_sw2.columns:
                            ax_sw2.plot(base_sw2["date"], base_sw2[ma], label=ma, color=color, linestyle="--", linewidth=1)
                    ax_sw2.set_title(f"{stock_id} {stock_name} - 股價與中期均線 MA20/MA60（近60日，權重 20%）")
                    ax_sw2.set_ylabel("價格")
                    ax_sw2.legend(loc="best")
                    ax_sw2.grid(True, alpha=0.3)
                    plt.tight_layout()
                    st.pyplot(fig_sw2)
                    plt.close()
                    
                    st.markdown("---")
                    
                    # 圖表 3: 法人 20 日累計買賣超 + 股價（籌碼趨勢，近 20 日）
                    fig_sw3, ax_sw3 = plt.subplots(figsize=(12, 4))
                    base_sw3 = base.tail(20).copy()
                    if "Inst_20D_Net" in base_sw3.columns:
                        ax_sw3.bar(base_sw3["date"], base_sw3["Inst_20D_Net"], label="法人20日累計", alpha=0.6, width=1, color="orange")
                    # 疊加股價線（右軸）
                    if "close" in base_sw3.columns:
                        ax_sw3_price = ax_sw3.twinx()
                        ax_sw3_price.plot(base_sw3["date"], base_sw3["close"], label="收盤價", color="black", linewidth=1.5, linestyle="-")
                        ax_sw3_price.set_ylabel("股價")
                        ax_sw3_price.legend(loc="upper right")
                    ax_sw3.set_title(f"{stock_id} {stock_name} - 法人20日累計買賣超 + 股價（近20日，權重 20%）")
                    ax_sw3.set_ylabel("累計買賣超")
                    ax_sw3.legend(loc="upper left")
                    ax_sw3.grid(True, alpha=0.3)
                    plt.tight_layout()
                    st.pyplot(fig_sw3)
                    plt.close()
                    
                    # 波段數據表格
                    st.markdown("---")
                    st.markdown("**波段動能數據（最近10筆）**")
                    swing_cols = ["date", "Revenue_YoY", "close", "MA_20", "MA_60", "Inst_20D_Net"]
                    available_sw = [c for c in swing_cols if c in base.columns]
                    if available_sw:
                        df_sw = base[available_sw].tail(10).copy()
                        df_sw["date"] = df_sw["date"].dt.strftime("%Y-%m-%d")
                        for col in df_sw.columns:
                            if col != "date":
                                df_sw[col] = df_sw[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "N/A")
                        df_sw = df_sw.rename(columns=lambda c: f"{cn(c)} ({c})" if c != "date" else c)
                        st.dataframe(df_sw, use_container_width=True, hide_index=True)
                
                # ===== tab2b: 價值成長（權重合計 50%） =====
                with tab2b:
                    st.markdown("**價值評分權重最高：成長能力 30% + 獲利品質 20%**")
                    
                    if df_fin_pivot is not None and not df_fin_pivot.empty:
                        # 圖表 1: ROE / 毛利率（獲利品質 20%）+ 股價
                        fig_v1, ax_v1 = plt.subplots(figsize=(12, 4))
                        ax_v1b = ax_v1.twinx()
                        val_chart1 = {"ROE_TTM": "ROE", "Gross_Margin": "毛利率"}
                        for col, label in val_chart1.items():
                            if col in df_fin_pivot.columns:
                                ax_v1.plot(df_fin_pivot["date"], df_fin_pivot[col], label=label, linewidth=1.5, marker="o", markersize=3)
                        if "close" in base.columns:
                            ax_v1b.plot(base["date"], base["close"], label="收盤價", color="black", linewidth=1, linestyle=":", alpha=0.5)
                            ax_v1b.set_ylabel("股價")
                        ax_v1.set_ylabel("百分比 (%)")
                        ax_v1.legend(loc="upper left")
                        ax_v1b.legend(loc="upper right")
                        ax_v1.grid(True, alpha=0.3)
                        ax_v1.set_title(f"{stock_id} {stock_name} - ROE / 毛利率 + 股價（權重 20%）")
                        plt.tight_layout()
                        st.pyplot(fig_v1)
                        plt.close()
                        
                        st.markdown("---")
                        
                        # 圖表 2: TTM EPS + 營收YoY + 股價（成長能力 30%）
                        fig_v2, ax_v2_1 = plt.subplots(figsize=(12, 4))
                        ax_v2_2 = ax_v2_1.twinx()
                        if "TTM_EPS" in df_fin_pivot.columns:
                            ax_v2_1.plot(df_fin_pivot["date"], df_fin_pivot["TTM_EPS"], label="TTM EPS", color="blue", linewidth=1.5, marker="o", markersize=3)
                        ax_v2_1.set_ylabel("TTM EPS", color="blue")
                        if "Revenue_YoY" in base.columns:
                            ax_v2_2.plot(base["date"], base["Revenue_YoY"], label="營收 YoY", color="green", linewidth=1.5, linestyle="--")
                            ax_v2_2.set_ylabel("營收 YoY (%)", color="green")
                        # 第三軸：股價（用 ax_v2_1 的 twinx 再疊一次不明智，改用 ax_v2_2 同軸）
                        if "close" in base.columns:
                            ax_v2_2.plot(base["date"], base["close"], label="收盤價", color="black", linewidth=0.8, linestyle=":", alpha=0.5)
                        ax_v2_1.set_title(f"{stock_id} {stock_name} - TTM EPS / 營收 YoY / 股價（權重 30%）")
                        ax_v2_1.legend(loc="upper left")
                        ax_v2_2.legend(loc="upper right")
                        ax_v2_1.grid(True, alpha=0.3)
                        plt.tight_layout()
                        st.pyplot(fig_v2)
                        plt.close()
                        
                        # 價值數據表格
                        st.markdown("---")
                        st.markdown("**價值成長數據（最近10筆）**")
                        val_cols = ["date", "TTM_EPS", "Revenue_YoY", "ROE_TTM", "Gross_Margin"]
                        available_val_base = [c for c in val_cols if c in base.columns]
                        if available_val_base:
                            df_val = base[available_val_base].tail(10).copy()
                            df_val["date"] = df_val["date"].dt.strftime("%Y-%m-%d")
                            for col in df_val.columns:
                                if col != "date":
                                    df_val[col] = df_val[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "N/A")
                            df_val = df_val.rename(columns=lambda c: f"{cn(c)} ({c})" if c != "date" else c)
                            st.dataframe(df_val, use_container_width=True, hide_index=True)
                    else:
                        st.caption("無財報資料")
                
                # ===== tab2c: 定存安全（權重合計 65%） =====
                with tab2c:
                    st.markdown("**定存評分權重最高：配息紀錄 25% + 配息品質 20% + 現金流 20% + 財務安全 15%**")
                    
                    # 圖表 1: 歷年現金股利（配息紀錄 25%）
                    fig_d1, ax_d1 = plt.subplots(figsize=(12, 4))
                    if df_div is not None and not df_div.empty and "CashEarningsDistribution" in df_div.columns:
                        div_raw = df_div.copy()
                        if "year" in div_raw.columns:
                            def _parse_year(val):
                                if pd.isna(val):
                                    return None
                                val_str = str(val).strip()
                                import re
                                matches = re.findall(r"\d+", val_str)
                                if not matches:
                                    return None
                                num = int(matches[0])
                                return num + 1911 if num <= 150 else num
                            div_raw["year_num"] = div_raw["year"].apply(_parse_year)
                            div_raw = div_raw.dropna(subset=["year_num"])
                            div_raw["year_num"] = div_raw["year_num"].astype(int)
                            div_raw["cash_total"] = div_raw["CashEarningsDistribution"].fillna(0) + div_raw["CashStatutorySurplus"].fillna(0)
                            yearly_div = div_raw.groupby("year_num")["cash_total"].sum()
                            if not yearly_div.empty:
                                ax_d1.bar(yearly_div.index.astype(str), yearly_div.values, alpha=0.7, color="orange")
                                ax_d1.set_title(f"{stock_id} {stock_name} - 歷年現金股利（權重 25%）")
                                ax_d1.set_ylabel("現金股利（元）")
                                ax_d1.grid(True, alpha=0.3)
                                for i, (year, val) in enumerate(yearly_div.items()):
                                    ax_d1.text(i, val + 0.1, f"{val:.1f}", ha="center", fontsize=9)
                    plt.tight_layout()
                    st.pyplot(fig_d1)
                    plt.close()
                    
                    st.markdown("---")
                    
                    # 圖表 2: TTM FCF / 負債比 + 股價（現金流 20% + 財務安全 15%）
                    fig_d2, ax_d2_1 = plt.subplots(figsize=(12, 4))
                    ax_d2_2 = ax_d2_1.twinx()
                    if df_fin_pivot is not None and not df_fin_pivot.empty:
                        if "TTM_FCF" in df_fin_pivot.columns:
                            ax_d2_1.bar(df_fin_pivot["date"], df_fin_pivot["TTM_FCF"], label="TTM FCF", alpha=0.6, width=30, color="green")
                        if "Debt_Ratio" in df_fin_pivot.columns:
                            ax_d2_2.plot(df_fin_pivot["date"], df_fin_pivot["Debt_Ratio"], label="負債比", color="red", linewidth=1.5, marker="o", markersize=3)
                    if "close" in base.columns:
                        ax_d2_2.plot(base["date"], base["close"], label="股價", color="black", linewidth=0.8, linestyle=":", alpha=0.5)
                        ax_d2_2.set_ylabel("負債比 (%) / 股價")
                    ax_d2_1.set_ylabel("TTM FCF", color="green")
                    ax_d2_1.set_title(f"{stock_id} {stock_name} - 自由現金流 / 負債比 + 股價（權重 20%+15%）")
                    ax_d2_1.legend(loc="upper left")
                    ax_d2_2.legend(loc="upper right")
                    ax_d2_1.grid(True, alpha=0.3)
                    plt.tight_layout()
                    st.pyplot(fig_d2)
                    plt.close()
                    
                    st.markdown("---")
                    
                    # 圖表 3: PE/PB + 殖利率 + 股價（估值安全 + 股東報酬）
                    fig_d3, ax_d3_1 = plt.subplots(figsize=(12, 4))
                    ax_d3_2 = ax_d3_1.twinx()
                    if "pe_ratio" in base.columns:
                        ax_d3_1.plot(base["date"], base["pe_ratio"], label="本益比", color="red", linewidth=1.5)
                    if "pb_ratio" in base.columns:
                        ax_d3_1.plot(base["date"], base["pb_ratio"], label="股價淨值比", color="purple", linewidth=1.5, linestyle="--")
                    if "dividend_yield" in base.columns:
                        ax_d3_2.plot(base["date"], base["dividend_yield"], label="殖利率", color="green", linewidth=1.5, linestyle=":")
                    if "close" in base.columns:
                        ax_d3_2.plot(base["date"], base["close"], label="股價", color="black", linewidth=0.8, linestyle="-.", alpha=0.4)
                    ax_d3_1.set_ylabel("PE / PB", color="red")
                    ax_d3_2.set_ylabel("殖利率 (%) / 股價", color="green")
                    ax_d3_1.set_title(f"{stock_id} {stock_name} - 本益比 / 淨值比 / 殖利率 + 股價")
                    ax_d3_1.legend(loc="upper left")
                    ax_d3_2.legend(loc="upper right")
                    ax_d3_1.grid(True, alpha=0.3)
                    plt.tight_layout()
                    st.pyplot(fig_d3)
                    plt.close()
                    
                    # 定存數據表格
                    st.markdown("---")
                    st.markdown("**定存安全數據（最近10筆）**")
                    div_cols = ["date", "dividend_yield", "Payout_Ratio", "FCF_Coverage", "Debt_Ratio"]
                    available_div = [c for c in div_cols if c in base.columns]
                    if available_div:
                        df_div_tbl = base[available_div].tail(10).copy()
                        df_div_tbl["date"] = df_div_tbl["date"].dt.strftime("%Y-%m-%d")
                        for col in df_div_tbl.columns:
                            if col != "date":
                                df_div_tbl[col] = df_div_tbl[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "N/A")
                        df_div_tbl = df_div_tbl.rename(columns=lambda c: f"{cn(c)} ({c})" if c != "date" else c)
                        st.dataframe(df_div_tbl, use_container_width=True, hide_index=True)
        
            # Tab 2: 📊 回測分析（雙策略：積極+保守）
            elif st.session_state["_active_tab"] == 2:
                st.markdown("**📊 回測分析**")
                
                if not run_bt:
                    st.info("請點擊側邊欄「📊 回測分析」按鈕執行回測")
                else:
                    # === A. 參數設定（摺疊） ===
                    with st.expander("⚙️ 回測參數設定", expanded=False):
                        bt_start = st.date_input("回測起始日", value=datetime.now() - timedelta(days=365))
                        bt_end = st.date_input("回測結束日", value=datetime.now())
                        bt_freq = st.selectbox("輸出頻率", options=["W", "M", "D"], index=2, format_func=lambda x: {"W": "每週", "M": "每月", "D": "每日"}.get(x, x))
                        st.caption("📌 回測將同時執行積極(買≥60/賣<40)和保守(買≥70/賣<50)兩種策略")
                        
                        # 50/50 雙彈夾分批建倉
                        bt_dual_bullet = st.checkbox("🔫 啟用 50/50 雙彈夾分批建倉", value=False, key="bt_dual_bullet")
                        if bt_dual_bullet:
                            bt_dual_mode = st.selectbox("加碼方式", options=["dip", "breakout"], index=0,
                                format_func=lambda x: {"dip": "📉 下跌加碼（回檔第二筆）", "breakout": "📈 順勢突破（新高加碼）"}.get(x, x),
                                key="bt_dual_mode")
                            bt_dual_drop = st.number_input("加碼門檻（%）：", value=-8.0, step=1.0, key="bt_dual_drop",
                                help="下跌加碼模式：第一發進場後跌 X% 打入第二發；突破模式：分數高於門檻+10分觸發")
                        
                        # 賣出評分雙軌模式（短線/波段）
                        bt_use_sell_score = st.checkbox("📊 啟用短線/波段賣出評分", value=False, key="bt_use_sell_score",
                            help="啟用後，短線/波段的賣出訊號使用獨立的賣出評分（total_sell），不看買入評分。CSV仍紀錄買入分數不變。")
                        
                        bt_run = st.button("▶️ 執行回測（雙策略）", type="primary")
                    
                    # 清除舊股票的回測殘留（含 AI 解說）
                    if "bt_result" in st.session_state and st.session_state["bt_result"].stock_id != stock_id:
                        for k in ["bt_result", "bt_active", "bt_conservative", 
                                   "_bt_csv_path_a", "_bt_csv_name_a",
                                   "_bt_csv_path_c", "_bt_csv_name_c", "bt_strategy",
                                   "_bt_ai_requested", "_bt_ai_result"]:
                            st.session_state.pop(k, None)
                    
                    # 讀取雙彈夾設定（預設關閉）
                    _bt_dual = st.session_state.get("bt_dual_bullet", False)
                    _bt_dual_mode = st.session_state.get("bt_dual_mode", "dip")
                    _bt_dual_drop = st.session_state.get("bt_dual_drop", -8.0)
                    _bt_use_sell = st.session_state.get("bt_use_sell_score", False)
                    
                    # 每次點擊「執行回測」都重新執行 — 同時跑積極(70/50)和保守(60/40)
                    if bt_run:
                        from core.backtest import run_backtest as _run_backtest
                        db_label = "+ 雙彈夾" if _bt_dual else ""
                        sell_label = "+ 賣出評分" if _bt_use_sell else ""
                        with st.spinner(f"⏳ 執行回測中（積極 60/40 + 保守 70/50 {db_label}{sell_label}）..."):
                            bt_active = _run_backtest(
                                df=base,
                                stock_id=stock_id,
                                start_date=bt_start.strftime("%Y-%m-%d"),
                                end_date=bt_end.strftime("%Y-%m-%d"),
                                freq=bt_freq,
                                buy_threshold=60, sell_threshold=40,
                                strategy="active",
                                dual_bullet=_bt_dual,
                                dual_bullet_mode=_bt_dual_mode,
                                dual_bullet_drop_pct=_bt_dual_drop,
                                use_sell_score=False,
                            )
                            bt_conservative = _run_backtest(
                                df=base,
                                stock_id=stock_id,
                                start_date=bt_start.strftime("%Y-%m-%d"),
                                end_date=bt_end.strftime("%Y-%m-%d"),
                                freq=bt_freq,
                                buy_threshold=70, sell_threshold=50,
                                strategy="conservative",
                                dual_bullet=_bt_dual,
                                dual_bullet_mode=_bt_dual_mode,
                                dual_bullet_drop_pct=_bt_dual_drop,
                                use_sell_score=False,
                            )
                            # 賣出評分版本（如有勾選）
                            bt_active_sell = None
                            bt_conservative_sell = None
                            if _bt_use_sell:
                                bt_active_sell = _run_backtest(
                                    df=base, stock_id=stock_id,
                                    start_date=bt_start.strftime("%Y-%m-%d"),
                                    end_date=bt_end.strftime("%Y-%m-%d"),
                                    freq=bt_freq,
                                    buy_threshold=60, sell_threshold=40,
                                    strategy="active_sell",
                                    dual_bullet=_bt_dual,
                                    dual_bullet_mode=_bt_dual_mode,
                                    dual_bullet_drop_pct=_bt_dual_drop,
                                    use_sell_score=True,
                                )
                                bt_conservative_sell = _run_backtest(
                                    df=base, stock_id=stock_id,
                                    start_date=bt_start.strftime("%Y-%m-%d"),
                                    end_date=bt_end.strftime("%Y-%m-%d"),
                                    freq=bt_freq,
                                    buy_threshold=70, sell_threshold=50,
                                    strategy="conservative_sell",
                                    dual_bullet=_bt_dual,
                                    dual_bullet_mode=_bt_dual_mode,
                                    dual_bullet_drop_pct=_bt_dual_drop,
                                    use_sell_score=True,
                                )
                            st.session_state["bt_active_sell"] = bt_active_sell
                            st.session_state["bt_conservative_sell"] = bt_conservative_sell
                            st.session_state["bt_active"] = bt_active
                            st.session_state["bt_conservative"] = bt_conservative
                            st.session_state["bt_result"] = bt_conservative  # 預設顯示保守
                            st.session_state["bt_strategy"] = "conservative"
                            
                            # CSV 暫存於 session_state（不自動存檔，等用戶下載）
                            if bt_active is not None and not bt_active.signal_history.empty:
                                csv_data_a = bt_active.signal_history.to_csv(index=False, encoding='utf-8-sig')
                                st.session_state["_bt_csv_a"] = csv_data_a
                                csv_data_c = bt_conservative.signal_history.to_csv(index=False, encoding='utf-8-sig')
                                st.session_state["_bt_csv_c"] = csv_data_c
                                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                                st.session_state["_bt_csv_name_a"] = f"backtest_{stock_id}_{ts}_60_40.csv"
                                st.session_state["_bt_csv_name_c"] = f"backtest_{stock_id}_{ts}_70_50.csv"
                    
                    # 顯示回測結果（用 session_state 直接讀取，確保切換立即生效）
                    has_bt_data = ("bt_active" in st.session_state and 
                                   st.session_state["bt_active"] is not None and
                                   st.session_state["bt_active"].stock_id == stock_id)
                    
                    if has_bt_data:
                        # 策略切換按鈕（使用 on_click callback 確保同次執行生效）
                        def _switch_to_conservative():
                            st.session_state["bt_strategy"] = "conservative"
                            st.session_state["bt_result"] = st.session_state.get("bt_conservative")
                        def _switch_to_active():
                            st.session_state["bt_strategy"] = "active"
                            st.session_state["bt_result"] = st.session_state.get("bt_active")
                        
                        cur_strategy = st.session_state.get("bt_strategy", "conservative")
                        bt = st.session_state.get("bt_conservative") if cur_strategy == "conservative" else st.session_state.get("bt_active")
                        
                        col_sw1, col_sw2 = st.columns(2)
                        with col_sw1:
                            is_conservative = cur_strategy == "conservative"
                            st.button("📉 保守 (買≥70/賣<50)", use_container_width=True,
                                      type="primary" if is_conservative else "secondary",
                                      on_click=_switch_to_conservative)
                        with col_sw2:
                            is_active = cur_strategy == "active"
                            st.button("📈 積極 (買≥60/賣<40)", use_container_width=True,
                                      type="primary" if is_active else "secondary",
                                      on_click=_switch_to_active)
                        
                        if is_conservative:
                            bt_buy = 70
                            bt_sell = 50
                            strategy_label = "保守 (70/50)"
                        else:
                            bt_buy = 60
                            bt_sell = 40
                            strategy_label = "積極 (60/40)"
                        
                        st.caption(f"📊 目前顯示：**{strategy_label}** | 買≥{bt_buy} / 賣<{bt_sell}")
                        
                        # === B. 分數走勢圖（分三張：短線、波段、價值+定存） ===
                        st.markdown("**📈 四維度分數走勢**")
                        sh = bt.signal_history
                        if not sh.empty and "date" in sh.columns:
                            # 圖1: 短線（若啟用賣出評分，多畫一條虛線）
                            fig_bt1a, ax1a = plt.subplots(figsize=(12, 3.5))
                            ax1a.plot(sh["date"], sh["short_term_score"], label="短線（買入評分）", color="red", linewidth=2)
                            if _bt_use_sell and "short_term_score_sell" in sh.columns:
                                ax1a.plot(sh["date"], sh["short_term_score_sell"], label="短線（賣出評分）", color="#8B0000", linewidth=1.5, linestyle="--", alpha=0.8)
                            ax1a.axhline(y=bt_buy, color="green", linestyle="--", alpha=0.5, label=f"買入門檻({bt_buy})")
                            ax1a.axhline(y=bt_sell, color="red", linestyle="--", alpha=0.5, label=f"賣出門檻({bt_sell})")
                            ax1a.set_ylabel("分數"); ax1a.set_ylim(0, 100)
                            ax1a.legend(loc="best"); ax1a.grid(True, alpha=0.3)
                            ax1a.set_title(f"{stock_id} {stock_name}（{strategy_label}） - 🔴 短線評分走勢")
                            plt.tight_layout(); st.pyplot(fig_bt1a); plt.close()
                            
                            st.markdown("---")
                            
                            # 圖2: 波段（若啟用賣出評分，多畫一條虛線）
                            fig_bt1b, ax1b = plt.subplots(figsize=(12, 3.5))
                            ax1b.plot(sh["date"], sh["swing_score"], label="波段（買入評分）", color="orange", linewidth=2)
                            if _bt_use_sell and "swing_score_sell" in sh.columns:
                                ax1b.plot(sh["date"], sh["swing_score_sell"], label="波段（賣出評分）", color="#D2691E", linewidth=1.5, linestyle="--", alpha=0.8)
                            ax1b.axhline(y=bt_buy, color="green", linestyle="--", alpha=0.5, label=f"買入門檻({bt_buy})")
                            ax1b.axhline(y=bt_sell, color="red", linestyle="--", alpha=0.5, label=f"賣出門檻({bt_sell})")
                            ax1b.set_ylabel("分數"); ax1b.set_ylim(0, 100)
                            ax1b.legend(loc="best"); ax1b.grid(True, alpha=0.3)
                            ax1b.set_title(f"{stock_id} {stock_name}（{strategy_label}） - 🟠 波段評分走勢")
                            plt.tight_layout(); st.pyplot(fig_bt1b); plt.close()
                            
                            st.markdown("---")
                            
                            # 圖3: 價值 + 定存（同一張，但只有兩條線）
                            fig_bt1c, ax1c = plt.subplots(figsize=(12, 3.5))
                            ax1c.plot(sh["date"], sh["value_score"], label="價值", color="blue", linewidth=2)
                            ax1c.plot(sh["date"], sh["dividend_score"], label="定存", color="green", linewidth=2)
                            ax1c.axhline(y=bt_buy, color="green", linestyle="--", alpha=0.5, label=f"買入門檻({bt_buy})")
                            ax1c.axhline(y=bt_sell, color="red", linestyle="--", alpha=0.5, label=f"賣出門檻({bt_sell})")
                            ax1c.set_ylabel("分數"); ax1c.set_ylim(0, 100)
                            ax1c.legend(loc="best"); ax1c.grid(True, alpha=0.3)
                            ax1c.set_title(f"{stock_id} {stock_name}（{strategy_label}） - 🔵 價值 🟢 定存 評分走勢")
                            plt.tight_layout(); st.pyplot(fig_bt1c); plt.close()
                        
                        # === C. 價格圖 + 買賣訊號標記 ===
                        st.markdown("**📊 價格走勢與買賣訊號**")
                        style_config = {
                            "short_term": ("短線", "red", "^", "v"),
                            "swing": ("波段", "orange", "^", "v"),
                            "value": ("價值", "blue", "^", "v"),
                            "dividend": ("定存", "green", "^", "v"),
                        }
                        
                        fig_bt2, ax_bt2 = plt.subplots(figsize=(12, 5))
                        if "price" in sh.columns:
                            ax_bt2.plot(sh["date"], sh["price"], label="收盤價", color="black", linewidth=1.5)
                            for style_key, (style_cn, color, buy_marker, sell_marker) in style_config.items():
                                trades = bt.styles.get(style_key, {}).get("trades", [])
                                buy_dates = [t.entry_date for t in trades if t.entry_date and pd.notna(t.entry_price)]
                                buy_prices = [t.entry_price for t in trades if t.entry_date and pd.notna(t.entry_price)]
                                sell_dates = [t.exit_date for t in trades if t.exit_date and pd.notna(t.exit_price)]
                                sell_prices = [t.exit_price for t in trades if t.exit_date and pd.notna(t.exit_price)]
                                if buy_dates:
                                    ax_bt2.scatter(buy_dates, buy_prices, marker=buy_marker, color=color, s=100, label=f"{style_cn}買入", zorder=5)
                                if sell_dates:
                                    ax_bt2.scatter(sell_dates, sell_prices, marker=sell_marker, color=color, s=100, label=f"{style_cn}賣出", zorder=5)
                            if avg_price > 0:
                                ax_bt2.axhline(y=avg_price, color="blue", linestyle=":", alpha=0.7, label=f"成本線({avg_price:.2f})")
                        
                        ax_bt2.set_ylabel("價格")
                        ax_bt2.legend(loc="best")
                        ax_bt2.grid(True, alpha=0.3)
                        ax_bt2.set_title(f"{stock_id} {stock_name}（{strategy_label}） - 價格與買賣訊號")
                        plt.tight_layout()
                        st.pyplot(fig_bt2)
                        plt.close()
                        
                        # === D. 績效摘要表（含已實現/未實現損益 + 雙彈夾） ===
                        mode_tags = []
                        if _bt_use_sell:
                            mode_tags.append("賣出策略")
                        if _bt_dual:
                            mode_tags.append("雙彈夾")
                        mode_suffix = f"（{' + '.join(mode_tags)}）" if mode_tags else ""
                        st.markdown(f"**📋 策略績效總覽{mode_suffix}**")
                        style_names = {"short_term": "短線", "swing": "波段", "value": "價值", "dividend": "定存", "composite": "綜合", "dual_bullet": "🔫 雙彈夾"}
                        perf_cols = st.columns(len(style_names))
                        for i, (sk, scn) in enumerate(style_names.items()):
                            with perf_cols[i]:
                                sd = bt.styles.get(sk, {})
                                trades_list = sd.get("trades", [])
                                tc = sd.get("trade_count", 0)
                                ret = sd.get("total_return_pct", 0.0)
                                delta = f"⬆️ +{ret:.1f}%" if ret > 10 else (f"↗️ +{ret:.1f}%" if ret > 0 else (f"➖ 0%" if ret == 0 else f"⬇️ {ret:.1f}%"))
                                st.metric(f"{scn}", f"{tc}筆", delta)
                                # 已實現 / 未實現損益
                                realized_sum = _calc_realized_return_sum(trades_list)
                                unrealized_pct = _calc_unrealized_return(trades_list)
                                if realized_sum != 0:
                                    st.caption(f"✔️ 已實現: {realized_sum:+.2f}%")
                                elif unrealized_pct is not None:
                                    st.caption(f"✔️ 已實現: 0%")
                                if unrealized_pct is not None:
                                    st.caption(f"⏳ 持有中: {unrealized_pct:+.2f}%")
                                st.markdown("---")
                        
                        # 交易明細表
                        st.markdown("**📋 交易明細**")
                        all_trade_rows = []
                        for sk, scn in style_names.items():
                            for t in bt.styles.get(sk, {}).get("trades", []):
                                all_trade_rows.append({
                                    "風格": scn,
                                    "買入日期": t.entry_date.strftime("%Y-%m-%d") if hasattr(t.entry_date, "strftime") else str(t.entry_date),
                                    "買入價": f"{t.entry_price:.2f}" if pd.notna(t.entry_price) else "-",
                                    "賣出日期": t.exit_date.strftime("%Y-%m-%d") if (t.exit_date and hasattr(t.exit_date, "strftime")) else ("-" if t.exit_date is None else str(t.exit_date)),
                                    "賣出價": f"{t.exit_price:.2f}" if (t.exit_price is not None and pd.notna(t.exit_price)) else "-",
                                    "狀態": t.status,
                                    "報酬率": f"{t.return_pct:+.2f}%" if t.return_pct != 0 else "0%",
                                })
                        if all_trade_rows:
                            st.dataframe(pd.DataFrame(all_trade_rows), use_container_width=True, hide_index=True)
                        else:
                            st.caption("無交易記錄")
                        
                        # CSV 下載按鈕（積極/保守各一個，加上賣出評分版本）
                        st.markdown("---")
                        st.markdown("**💾 回測 CSV 除錯輸出**")
                        st.caption(f"📁 已儲存至：`data/debug/` 目錄 | 💡 啟用賣出評分時，額外產生賣出評分版本 CSV")
                        col_dl1, col_dl2, col_dl3, col_dl4 = st.columns(4)
                        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                        with col_dl1:
                            if st.session_state.get("bt_active") is not None:
                                csv_a = st.session_state["bt_active"].signal_history.to_csv(index=False, encoding='utf-8-sig')
                                st.download_button("📥 積極 60/40", data=csv_a, file_name=f"backtest_{stock_id}_{ts}_60_40.csv", mime="text/csv")
                        with col_dl2:
                            if st.session_state.get("bt_conservative") is not None:
                                csv_c = st.session_state["bt_conservative"].signal_history.to_csv(index=False, encoding='utf-8-sig')
                                st.download_button("📥 保守 70/50", data=csv_c, file_name=f"backtest_{stock_id}_{ts}_70_50.csv", mime="text/csv")
                        with col_dl3:
                            bt_as = st.session_state.get("bt_active_sell")
                            if bt_as is not None and bt_as.signal_history is not None and not bt_as.signal_history.empty:
                                csv_as = bt_as.signal_history.to_csv(index=False, encoding='utf-8-sig')
                                st.download_button("📥 積極+賣出評分", data=csv_as, file_name=f"backtest_{stock_id}_{ts}_60_40_sell.csv", mime="text/csv")
                        with col_dl4:
                            bt_cs = st.session_state.get("bt_conservative_sell")
                            if bt_cs is not None and bt_cs.signal_history is not None and not bt_cs.signal_history.empty:
                                csv_cs = bt_cs.signal_history.to_csv(index=False, encoding='utf-8-sig')
                                st.download_button("📥 保守+賣出評分", data=csv_cs, file_name=f"backtest_{stock_id}_{ts}_70_50_sell.csv", mime="text/csv")
                        
                        # 雙彈夾 CSV 下載（如果該策略有雙彈夾資料）
                        _bt_db_a = st.session_state.get("bt_active", None)
                        _bt_db_c = st.session_state.get("bt_conservative", None)
                        if _bt_dual and (_bt_db_a is not None or _bt_db_c is not None):
                            st.markdown("**🔫 雙彈夾交易紀錄**")
                            col_db1, col_db2 = st.columns(2)
                            with col_db1:
                                if _bt_db_a is not None and len(_bt_db_a.styles.get("dual_bullet", {}).get("trades", [])) > 0:
                                    import io
                                    buf = io.StringIO()
                                    buf.write("日期,價格,動作,第一發進場價,第二發進場價,均價,狀態,報酬率\n")
                                    for t in _bt_db_a.styles["dual_bullet"]["trades"]:
                                        p1_date = t.entry_date.strftime('%Y-%m-%d') if hasattr(t.entry_date,'strftime') else str(t.entry_date)
                                        p2_price = f"{t.entry_price_2:.2f}" if t.entry_price_2 is not None else "-"
                                        avg = f"{t.avg_cost:.2f}" if t.avg_cost is not None else "-"
                                        ex_date = t.exit_date.strftime("%Y-%m-%d") if (t.exit_date and hasattr(t.exit_date,'strftime')) else ("-" if t.exit_date is None else str(t.exit_date))
                                        ex_price = f"{t.exit_price:.2f}" if t.exit_price is not None else "-"
                                        buf.write(f"{p1_date},{t.entry_price:.2f},買入(一發),{t.entry_price:.2f},,,\n")
                                        if t.entry_price_2 is not None:
                                            buf.write(f"{ex_date},{p2_price},買入(二發),{t.entry_price:.2f},{p2_price},{avg},\n")
                                        action = "賣出(全數)" if t.status == "已出清" else "持有中"
                                        buf.write(f"{ex_date},{ex_price},{action},{t.entry_price:.2f},{p2_price},{avg},{t.status},{t.return_pct:+.2f}%\n")
                                    buf.seek(0)
                                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                                    st.download_button("🔫 下載 積極+雙彈夾 CSV", data=buf.getvalue(), file_name=f"dual_bullet_{stock_id}_{ts}_60_40.csv", mime="text/csv")
                            with col_db2:
                                if _bt_db_c is not None and len(_bt_db_c.styles.get("dual_bullet", {}).get("trades", [])) > 0:
                                    import io
                                    buf2 = io.StringIO()
                                    buf2.write("日期,價格,動作,第一發進場價,第二發進場價,均價,狀態,報酬率\n")
                                    for t in _bt_db_c.styles["dual_bullet"]["trades"]:
                                        p1_date = t.entry_date.strftime('%Y-%m-%d') if hasattr(t.entry_date,'strftime') else str(t.entry_date)
                                        p2_price = f"{t.entry_price_2:.2f}" if t.entry_price_2 is not None else "-"
                                        avg = f"{t.avg_cost:.2f}" if t.avg_cost is not None else "-"
                                        ex_date = t.exit_date.strftime("%Y-%m-%d") if (t.exit_date and hasattr(t.exit_date,'strftime')) else ("-" if t.exit_date is None else str(t.exit_date))
                                        ex_price = f"{t.exit_price:.2f}" if t.exit_price is not None else "-"
                                        buf2.write(f"{p1_date},{t.entry_price:.2f},買入(一發),{t.entry_price:.2f},,,\n")
                                        if t.entry_price_2 is not None:
                                            buf2.write(f"{ex_date},{p2_price},買入(二發),{t.entry_price:.2f},{p2_price},{avg},\n")
                                        action = "賣出(全數)" if t.status == "已出清" else "持有中"
                                        buf2.write(f"{ex_date},{ex_price},{action},{t.entry_price:.2f},{p2_price},{avg},{t.status},{t.return_pct:+.2f}%\n")
                                    buf2.seek(0)
                                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                                    st.download_button("🔫 下載 保守+雙彈夾 CSV", data=buf2.getvalue(), file_name=f"dual_bullet_{stock_id}_{ts}_70_50.csv", mime="text/csv")
                        
                        # ===== E. 🤖 AI 回測解說（點位解說版） =====
                        st.markdown("---")
                        st.subheader("🤖 AI 回測點位解說")
                        st.caption("AI 像專業分析師一樣，順著時間軸解說每筆進出點位的時空背景")
                        
                        # 兩顆按鈕：保守解說 / 積極解說
                        col_ai1, col_ai2 = st.columns(2)
                        with col_ai1:
                            ai_btn_conservative = st.button(
                                "🤖 解說保守策略 (70/50)",
                                use_container_width=True,
                                type="secondary",
                                key="bt_ai_btn_conservative",
                            )
                        with col_ai2:
                            ai_btn_active = st.button(
                                "🤖 解說積極策略 (60/40)",
                                use_container_width=True,
                                type="secondary",
                                key="bt_ai_btn_active",
                            )
                        
                        # 追蹤被按下的解說按鈕
                        if ai_btn_conservative:
                            st.session_state["_bt_ai_requested"] = "conservative"
                            st.session_state["_bt_ai_result"] = None
                        if ai_btn_active:
                            st.session_state["_bt_ai_requested"] = "active"
                            st.session_state["_bt_ai_result"] = None
                        
                        # 檢查是否有請求 + 是否有 deepseek key
                        _bt_ai_requested = st.session_state.get("_bt_ai_requested", None)
                        _bt_ai_result = st.session_state.get("_bt_ai_result", None)
                        
                        if _bt_ai_requested and _bt_ai_result is None:
                            if _bt_ai_requested == "conservative":
                                _bt_ai_target = st.session_state.get("bt_conservative")
                                _bt_ai_label = "保守 (70/50)"
                            else:
                                _bt_ai_target = st.session_state.get("bt_active")
                                _bt_ai_label = "積極 (60/40)"
                            # 附加策略型態標籤
                            _mode_tags = []
                            if _bt_use_sell:
                                _mode_tags.append("賣出評分雙軌")
                            if _bt_dual:
                                _mode_tags.append("雙彈夾")
                            if _mode_tags:
                                _bt_ai_label += f"（{' + '.join(_mode_tags)}）"
                            
                            if _bt_ai_target is None:
                                st.warning("⚠️ 請先執行回測（點擊「▶️ 執行回測（雙策略）」）")
                            elif not deepseek_api_key:
                                st.info("ℹ️ 請輸入 DeepSeek API Key 以獲得 AI 回測點位解說")
                            else:
                                from ai.analyzer import analyze_backtest_with_deepseek
                                with st.spinner(f"🤖 AI 正在解說 {_bt_ai_label} 策略的進出點位..."):
                                    _bt_ai_result = analyze_backtest_with_deepseek(
                                        stock_id=stock_id,
                                        stock_name=stock_name,
                                        strategy_label=_bt_ai_label,
                                        bt_result=_bt_ai_target,
                                        api_key=deepseek_api_key,
                                    )
                                    st.session_state["_bt_ai_result"] = _bt_ai_result
                        
                        # 顯示 AI 解說結果
                        _bt_ai_result = st.session_state.get("_bt_ai_result", None)
                        if _bt_ai_result is not None:
                            ba = _bt_ai_result.get("backtest_analysis", {})
                            
                            # 1. 一句話總結
                            if ba.get("summary"):
                                st.markdown(f"**📝 一句話總結**")
                                st.info(ba["summary"])
                            
                            # 2. 各風格績效分析（short_term / swing / value / dividend / composite）
                            style_analysis = ba.get("style_analysis", {})
                            if style_analysis:
                                st.markdown("---")
                                st.markdown("**📊 各風格績效分析**")
                                style_labels = {
                                    "short_term": ("🔴 短線", "#E74C3C"),
                                    "swing": ("🟠 波段", "#E67E22"),
                                    "value": ("🔵 價值", "#2980B9"),
                                    "dividend": ("🟢 定存", "#27AE60"),
                                    "composite": ("⚪ 綜合", "#7F8C8D"),
                                }
                                for sk, (label, color) in style_labels.items():
                                    sa = style_analysis.get(sk, {})
                                    if sa:
                                        perf = sa.get("performance", "")
                                        comment = sa.get("comment", "")
                                        st.markdown(f"**{label}**")
                                        st.caption(f"📈 {perf}" if perf else "")
                                        if comment:
                                            st.markdown(comment)
                                        st.markdown("---")
                            
                            # 3. 交易點位深度解說（故事性敘述，含進出點位時空背景）
                            if ba.get("narrative"):
                                st.markdown("**📖 交易點位深度解說**")
                                st.markdown(ba["narrative"])
                                st.markdown("---")
                            
                            # 4. 整體策略核心診斷
                            if ba.get("diagnosis"):
                                st.markdown("**🔍 整體策略核心診斷**")
                                st.warning(ba["diagnosis"])
                        
                        # == 結束 AI 回測解說區塊 ==
                                
                    else:
                        # 如果有上次回測結果，顯示它
                        if st.session_state.get("bt_result") is not None:
                            bt = st.session_state["bt_result"]
                            sh = bt.signal_history
                            if not sh.empty:
                                st.caption(f"📅 上次回測範圍: {bt.start_date} ~ {bt.end_date}")
                                style_names = {
                                    "short_term": "短線", "swing": "波段",
                                    "value": "價值", "dividend": "定存", "composite": "綜合",
                                }
                                perf_cols2 = st.columns(5)
                                for i, (sk, scn) in enumerate(style_names.items()):
                                    sd = bt.styles.get(sk, {})
                                    tc = sd.get("trade_count", 0)
                                    ret = sd.get("total_return_pct", 0.0)
                                    wr = sd.get("win_rate", 0.0)
                                    with perf_cols2[i]:
                                        st.metric(f"{scn}", f"{tc}筆", f"{ret:+.1f}%" if ret != 0 else "0%")
                                        win_rate_str = f"勝率: {wr:.0f}%" if wr is not None else "勝率: -"
                                        st.caption(win_rate_str)
        
            # Tab 3: 📰 新聞輿情
            elif st.session_state["_active_tab"] == 3:
                st.markdown("**📰 新聞輿情分析**")
                st.caption("分析時已自動抓取新聞存入資料庫，下方直接顯示歷史數據。可點「更新新聞」手動重新抓取。")
                
                # 新聞查詢輸入與更新按鈕
                col_news_input, col_news_btn = st.columns([3, 1])
                with col_news_input:
                    news_stock_id = st.text_input("查詢其他股票代號", placeholder=stock_id, max_chars=6, key="news_stock_input")
                with col_news_btn:
                    st.caption("&nbsp;")
                    news_search_btn = st.button("🔄 更新新聞", type="primary", use_container_width=True)
                
                # 決定要顯示哪個股票的：若無手動輸入則自動跟隨側邊欄 stock_id
                display_stock_id = news_stock_id.strip() if news_stock_id and news_stock_id.strip() else stock_id
                
                # 手動更新新聞
                if news_search_btn:
                    with st.spinner(f"⏳ 正在抓取 {display_stock_id} 的最新新聞並進行情緒分析..."):
                        fetched_list = fetch_news(display_stock_id, limit=10)
                        if fetched_list:
                            fetched_list = analyze_news(fetched_list, text_field="title")
                            inserted, total = save_news(fetched_list)
                            if inserted > 0:
                                st.success(f"✅ 新增 {inserted} 篇新聞")
                            else:
                                st.info(f"ℹ️ 無新新聞（已是最新）")
                
                # 無論是否按更新，都從資料庫讀取現有數據顯示
                agg = get_aggregate_sentiment(display_stock_id)
                history = get_historical_sentiment(display_stock_id, limit=50)
                
                if not history:
                    st.info("📭 尚無新聞資料，請先執行「🔍 開始分析」或點「更新新聞」手動抓取")
                else:
                    # 綜合情緒指標
                    if agg:
                        st.markdown("---")
                        st.subheader("📊 綜合情緒統計")
                        avg_score = agg["avg_score"]
                        label = get_sentiment_label(avg_score)
                        
                        col_agg1, col_agg2, col_agg3, col_agg4 = st.columns(4)
                        with col_agg1:
                            st.metric("📰 歷史新聞數", f"{agg['total_news']} 篇")
                        with col_agg2:
                            st.metric("📈 平均情緒", f"{avg_score:.4f}", label)
                        with col_agg3:
                            st.metric("🟢 偏多", f"{agg['positive_count']} 篇")
                        with col_agg4:
                            st.metric("🔴 偏空", f"{agg['negative_count']} 篇")
                        
                        # 情緒分佈條
                        st.markdown("**情緒分佈**")
                        if agg["total_news"] > 0:
                            pos_pct = agg["positive_count"] / agg["total_news"] * 100
                            neg_pct = agg["negative_count"] / agg["total_news"] * 100
                            neu_pct = agg["neutral_count"] / agg["total_news"] * 100
                            st.markdown(
                                f"""
                                <div style="display:flex; height:24px; border-radius:12px; overflow:hidden; margin:8px 0;">
                                    <div style="flex:{pos_pct:.1f}; background:#FF6B6B; display:flex; align-items:center; justify-content:center; font-size:12px; color:white; min-width:30px;">{pos_pct:.0f}%</div>
                                    <div style="flex:{neu_pct:.1f}; background:#DDD; display:flex; align-items:center; justify-content:center; font-size:12px; color:#666; min-width:30px;">{neu_pct:.0f}%</div>
                                    <div style="flex:{neg_pct:.1f}; background:#51CF66; display:flex; align-items:center; justify-content:center; font-size:12px; color:white; min-width:30px;">{neg_pct:.0f}%</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                            st.caption("🔴 偏多 | ⚪ 中性 | 🟢 偏空")
                    
                    # 最新新聞表格
                    st.markdown("---")
                    st.subheader("📋 最新新聞（近 50 筆）")
                    
                    news_rows = []
                    for n in history:
                        score = n["sentiment_score"]
                        news_rows.append({
                            "時間": n["publish_time"][:16],
                            "來源": n["source"],
                            "標題": n["title"],
                            "情緒分數": score,
                            "判定": get_sentiment_label(score),
                        })
                    
                    if news_rows:
                        df_news = pd.DataFrame(news_rows)
                        st.dataframe(
                            df_news,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "情緒分數": st.column_config.NumberColumn(format="%.4f"),
                            }
                        )
                    
                    # 歷史情緒趨勢圖
                    st.markdown("---")
                    st.subheader("📈 歷史情緒趨勢")
                    df_history = pd.DataFrame(history)
                    df_history["publish_time"] = pd.to_datetime(df_history["publish_time"])
                    df_history = df_history.sort_values("publish_time")
                    
                    fig_news, ax_news = plt.subplots(figsize=(12, 4))
                    ax_news.plot(df_history["publish_time"], df_history["sentiment_score"], 
                                color="purple", linewidth=1.5, marker="o", markersize=4)
                    ax_news.axhline(y=0.2, color="red", linestyle="--", alpha=0.5, label="偏多門檻 (+0.2)")
                    ax_news.axhline(y=0, color="gray", linestyle="-", alpha=0.3)
                    ax_news.axhline(y=-0.2, color="green", linestyle="--", alpha=0.5, label="偏空門檻 (-0.2)")
                    ax_news.set_title(f"{news_stock_id} - 新聞情緒趨勢（近50筆）")
                    ax_news.set_ylabel("情緒分數")
                    ax_news.set_xlabel("時間")
                    ax_news.legend(loc="best")
                    ax_news.grid(True, alpha=0.3)
                    plt.tight_layout()
                    st.pyplot(fig_news)
                    plt.close()
        
        # ===== 瀑布流 3：評分完成 → 四維度分析卡 + 基本建議 =====