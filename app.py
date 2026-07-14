"""
台股AI個人化決策系統 v1.0
Streamlit 前端主入口 — 串接真實資料 + 圖表

瀑布流顯示順序：
1. 📥 撈取完成 → 大盤資訊卡 + 個股資訊卡
2. 📊 計算指標完成 → 圖表區
3. 🎯 評分完成 → 四維度分析卡 + 基本建議
4. 🤖 AI 解說完成 → AI 解說區塊
5. 最後 → 風險提示 + 除錯面板
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import sys
import os

# 加入專案路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.fetcher import (
    fetch_stock_price, fetch_month_revenue, fetch_financial_statements,
    fetch_balance_sheet, fetch_cash_flows, fetch_dividend, fetch_per_history,
    fetch_institutional_investors, fetch_margin_purchase, fetch_short_sale_balances,
    fetch_stock_info, fetch_taiex_price
)
from data.processor import build_universal_base_table, calculate_derived_columns, _pivot_financial_statements

from stock.metrics import calculate_technical_indicators, calculate_financial_indicators
from core.scorer import get_all_scores, get_historical_scores
from core.backtest import run_backtest
from core.advisor import get_advice
from core.trade_manager import generate_trade_advice
from ai.analyzer import analyze_with_deepseek

# 設定 matplotlib 支援中文
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ===== 中英欄位對照表（用於細目中文顯示 + 除錯面板） =====
FIELD_CN_MAP = {
    # 技術面
    "close": "收盤價",
    "volume": "成交量",
    "MA_5": "5日均線",
    "MA_10": "10日均線",
    "MA_20": "20日均線",
    "MA_60": "60日均線",
    "High_5D": "5日最高價",
    "High_10D": "10日最高價",
    "High_20D": "20日最高價",
    "Vol_MA_5": "5日均量",
    "RSI_6": "6日RSI",
    "MA_Alignment": "均線排列",
    "Volume_Ratio": "量比",
    "MA60_Bias": "60日乖離率",
    "ATR": "平均真實波幅",
    "Above_MA_5": "站上5日線",
    "Above_MA_10": "站上10日線",
    "Above_MA_20": "站上20日線",
    "Above_MA_60": "站上60日線",
    "Bullish_MA": "多頭排列",
    "Volume_Above_MA5": "量站上5日均量",
    # 籌碼面
    "Foreign_Net": "外資買賣超",
    "Trust_Net": "投信買賣超",
    "Dealer_Net": "自營商買賣超",
    "Inst_Net": "三大法人合計",
    "Inst_5D_Net": "法人5日累計",
    "Inst_20D_Net": "法人20日累計",
    "Chip_Divergence": "籌碼背離",
    "Margin_5D_Change": "融資5日變化",
    "Short_5D_Change": "融券5日變化",
    "SBL_5D_Change": "借券5日變化",
    "Inst_Consecutive_Days": "法人連續天數",
    # 基本面
    "month_revenue": "月營收",
    "revenue_year": "營收年度",
    "revenue_month": "營收月份",
    "Revenue_YoY": "營收年增率",
    "Revenue_MoM": "營收月增率",
    "Revenue_Accelerating": "營收加速",
    "Revenue_Momentum": "營收動能",
    "Price_Revenue_Divergence": "價量背離",
    "TTM_EPS": "近四季EPS",
    "TTM_EPS_Valid": "EPS有效性",
    "TTM_FCF": "近四季自由現金流",
    "TTM_OCF": "近四季營業現金流",
    "TTM_OperatingCF": "近四季營業現金流",
    "TTM_CAPEX": "近四季資本支出",
    "TTM_NetIncome": "近四季稅後淨利",
    "ROE_TTM": "近四季ROE",
    "ROE_Stability": "ROE穩定度",
    "ROA_TTM": "近四季ROA",
    "Gross_Margin": "毛利率",
    "Gross_Margin_Stability": "毛利率穩定度",
    "Operating_Margin": "營業利益率",
    "Current_Ratio": "流動比率",
    "Interest_Coverage": "利息保障倍數",
    "EPS_Stability": "EPS穩定度",
    "EPS_YoY": "EPS年成長率",
    "EPS_YoY_Reason": "EPS成長率原因",
    "Debt_Ratio": "負債比",
    "Debt_Ratio_Trend": "負債比趨勢",
    "PE_Percentile": "本益比百分位",
    "PB_Percentile": "股價淨值比百分位",
    "pe_ratio": "本益比",
    "pb_ratio": "股價淨值比",
    "dividend_yield": "殖利率",
    "cash_dividend_total": "現金股利總額",
    "cash_dividend": "現金股利",
    "cash_statutory": "法定盈餘公積",
    "Payout_Ratio": "配息率",
    "Payout_Ratio_Stability": "配息率穩定度",
    "FCF_Coverage": "FCF覆蓋率",
    "FCF_vs_Dividend": "FCF/股利比",
    "Dividend_Continuity_Years": "連續配息年數",
    "Data_Years_Available": "資料可用年數",
    # 評分相關
    "trend_score": "趨勢評分",
    "momentum_score": "動能評分",
    "volume_score": "量能評分",
    "inst_score": "法人評分",
    "chip_score": "籌碼評分",
    "risk_score": "風險評分",
    "revenue_score": "營收評分",
    "mid_trend_score": "中期趨勢評分",
    "inst_trend_score": "籌碼趨勢評分",
    "earnings_score": "獲利評分",
    "valuation_score": "估值評分",
    "catalyst_score": "催化評分",
    "valuation_safety_score": "估值安全評分",
    "profit_quality_score": "獲利品質評分",
    "growth_score": "成長評分",
    "financial_safety_score": "財務安全評分",
    "cash_flow_quality_score": "現金流品質評分",
    "shareholder_return_score": "股東報酬評分",
    "dividend_record_score": "配息紀錄評分",
    "dividend_quality_score": "配息品質評分",
    "cash_flow_score": "現金流評分",
    "profit_stability_score": "獲利穩定評分",
    "long_term_growth_score": "長期成長評分",
}

def cn(val: str) -> str:
    """將英文欄位名稱轉為中文，若無對照則保留原文"""
    return FIELD_CN_MAP.get(val, val)

st.set_page_config(
    page_title="台股AI個人化決策系統 v1.0",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📈 台股AI個人化決策系統 v1.0")
st.caption("⚠️ 免責聲明：本系統僅供個人分析參考，不構成任何投資建議或推薦。使用者應自行審慎評估，投資有盈虧風險，請自負責任。")
st.markdown("---")

# ===== 側邊欄 =====
with st.sidebar:
    st.header("⚙️ 設定")
    
    st.subheader("🔑 API 金鑰")
    
    # FinMind Token
    with st.expander("📘 點我查看 FinMind 申請教學", expanded=False):
        st.markdown("""
        **FinMind API Token（必填）**
        1. 打開 [FinMind](https://finmindtrade.com) 官網
        2. 點右上角 **Login / Register** → 用 Email 註冊
        3. 登入後進 **Dashboard** → 左邊 **API Token**
        4. 複製那串 Token（長這樣：`eyJ0eXAiOiJKV1Qi...`）
        5. 貼到下面的輸入框
        """)
    finmind_token = st.text_input(
        "FinMind API Token (必填)",
        type="password",
        placeholder="eyJ0eXAiOiJKV1Qi...",
    )
    
    st.markdown("---")
    
    # DeepSeek Key
    with st.expander("🤖 點我查看 DeepSeek 申請教學", expanded=False):
        st.markdown("""
        **DeepSeek API Key（選填）**
        1. 打開 [DeepSeek Platform](https://platform.deepseek.com) 註冊
        2. 登入後點左邊 **API Keys**
        3. 點 **Create API key** → 取名（如 `stock-analyzer`）
        4. 複製 Key 貼到下面的輸入框
        > 沒填也能分析，只是沒 AI 解說
        """)
    deepseek_api_key = st.text_input(
        "DeepSeek API Key (選填)",
        type="password",
        placeholder="不填也能分析，只是沒 AI 解說",
    )
    
    st.markdown("---")
    
    stock_id = st.text_input("股票代號", value="2330", max_chars=6)
    
    st.markdown("---")
    
    st.subheader("💼 個人化持股")
    avg_price = st.number_input("持股均價", min_value=0.0, step=0.5, value=0.0)
    shares = st.number_input("股數", min_value=0, step=100, value=0)
    
    st.markdown("---")
    
    analyze_btn = st.button("🔍 開始分析", type="primary", use_container_width=True)
    
    st.markdown("---")
    backtest_btn = st.button("📊 回測分析", type="secondary", use_container_width=True)

# ===== 追蹤按鈕點擊事件 =====
cache_key = f"cache_{stock_id}"

if backtest_btn:
    if cache_key in st.session_state:
        st.session_state["run_backtest"] = True
        # 點擊回測後自動跳到 tab3
        st.session_state["_active_tab"] = 2
    else:
        st.session_state["run_backtest"] = False

# 透過 session_state 記錄分析完成狀態，避免 rerun 時閃過提示文字
if analyze_btn:
    st.session_state["_analysis_requested"] = True
    st.session_state["_active_tab"] = 0

# ===== 主畫面：檢查是否該開始分析 =====
_has_cache = cache_key in st.session_state
_analysis_done = st.session_state.get("_analysis_requested", False) or _has_cache

if _has_cache:
    # 快取存在，跳過分析流程，直接顯示
    pass
elif _analysis_done:
    # 曾按過分析但快取被清除（極少數狀況），不顯示提示
    pass
elif backtest_btn:
    # 按了回測但尚未分析過
    st.info("請先點擊「🔍 開始分析」完成分析後，再使用「📊 回測分析」")
    st.stop()
elif not analyze_btn:
    # 兩個按鈕都沒有被點擊
    st.info("👈 請在側邊欄輸入股票代號與 API 金鑰，點擊「開始分析」")
    st.stop()

# 檢查必要輸入
if not finmind_token:
    st.error("❌ 請輸入 FinMind API Token")
    st.stop()

# 股價抓 3 年（足夠計算 Debt_Ratio_Trend 需 5 季、EPS_YoY 需 5 季）
# 基本面（營收、財報、股利）抓 10 年（供圖表顯示）
end_str = datetime.now().strftime("%Y-%m-%d")
start_str = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
start_3y = (datetime.now() - timedelta(days=3*365)).strftime("%Y-%m-%d")
start_10y = (datetime.now() - timedelta(days=10*365)).strftime("%Y-%m-%d")

has_position = (avg_price > 0 and shares > 0)

# ===== 進度提示（5 段式） =====
progress_bar = st.progress(0, text="⏳ 準備開始分析...")
status_text = st.empty()

def update_progress(pct: int, msg: str):
    """更新進度條與狀態文字"""
    progress_bar.progress(pct, text=msg)
    status_text.caption(msg)

# ===== 瀑布流容器（預先建立，逐步填入內容） =====
waterfall_1 = st.empty()  # 大盤資訊卡 + 個股資訊卡
waterfall_2 = st.empty()  # 圖表區
waterfall_3 = st.empty()  # 四維度分析卡 + 基本建議
waterfall_4 = st.empty()  # AI 解說
waterfall_5 = st.empty()  # 風險提示 + 除錯面板
waterfall_6 = st.empty()  # 回測結果摘要（若有執行過）

try:
    # ===== 檢查快取：如果已分析過同一支股票，直接從 session_state 讀取 =====
    cache_key = f"cache_{stock_id}"
    _has_cache = cache_key in st.session_state
    
    if _has_cache:
        cache = st.session_state[cache_key]
        
        # 檢查快取中的 trade_advice 是否為舊版（缺 v4.4 雙軌欄位）
        old_ta = cache.get("trade_advice", None)
        if old_ta is not None and not hasattr(old_ta, 'agg_entry'):
            # 舊版快取，清除後強制重新分析
            del st.session_state[cache_key]
            st.session_state["analyzed"] = False
            st.info("🔄 偵測到舊版快取，正在重新分析以啟用雙軌建議價功能...")
            _has_cache = False  # 讓程式碼落入下方的 else 重新分析
        
        if _has_cache:
            base = cache["base"]
            fetch_info = cache["fetch_info"]
            scores = cache["scores"]
            advice = cache["advice"]
            trade_advice = cache.get("trade_advice", None)
            ai_result = cache.get("ai_result", None)
            stock_name = cache.get("stock_name", stock_id)
            df_taiex = cache.get("df_taiex", None)
            df_info = cache.get("df_info", None)
            df_rev = cache.get("df_rev", None)
            df_fin = cache.get("df_fin", None)
            df_bal = cache.get("df_bal", None)
            df_cf = cache.get("df_cf", None)
            df_div = cache.get("df_div", None)
            df_price = cache.get("df_price", None)
            df_per = cache.get("df_per", None)
            df_inst = cache.get("df_inst", None)
            df_margin = cache.get("df_margin", None)
            df_ss = cache.get("df_ss", None)
            
            # 跳過撈取，直接顯示
            progress_bar.empty()
            status_text.empty()
    
    if not _has_cache:
        # ===== 第 1 段：📥 撈取資料 (0-30%) =====
        update_progress(5, "📥 [1/5] 撈取股價資料（3年，足夠計算 Debt_Ratio_Trend/EPS_YoY）...")
        df_price = fetch_stock_price(stock_id, start_3y, end_str, finmind_token)
        df_taiex = fetch_taiex_price(start_3y, end_str, finmind_token)
        df_info = fetch_stock_info(stock_id, finmind_token)
        
        update_progress(12, "📥 [1/5] 撈取基本面資料（營收、財報、股利、本益比）...")
        df_rev = fetch_month_revenue(stock_id, start_10y, end_str, finmind_token)
        df_fin = fetch_financial_statements(stock_id, start_10y, end_str, finmind_token)
        df_bal = fetch_balance_sheet(stock_id, start_10y, end_str, finmind_token)
        df_cf = fetch_cash_flows(stock_id, start_10y, end_str, finmind_token)
        df_div = fetch_dividend(stock_id, start_10y, end_str, finmind_token)
        df_per = fetch_per_history(stock_id, start_str, end_str, finmind_token)
        
        update_progress(22, "📥 [1/5] 撈取籌碼面資料（法人、融資券、借券）...")
        df_inst = fetch_institutional_investors(stock_id, start_str, end_str, finmind_token)
        df_margin = fetch_margin_purchase(stock_id, start_str, end_str, finmind_token)
        df_ss = fetch_short_sale_balances(stock_id, start_str, end_str, finmind_token)
        
        # 收集撈取資訊供除錯面板使用
        fetch_info = {
            "股價 (df_price)": {"rows": len(df_price), "cols": list(df_price.columns) if not df_price.empty else []},
            "大盤 (df_taiex)": {"rows": len(df_taiex), "cols": list(df_taiex.columns) if df_taiex is not None and not df_taiex.empty else []},
            "基本資料 (df_info)": {"rows": len(df_info), "cols": list(df_info.columns) if df_info is not None and not df_info.empty else []},
            "月營收 (df_rev)": {"rows": len(df_rev), "cols": list(df_rev.columns) if not df_rev.empty else []},
            "損益表 (df_fin)": {"rows": len(df_fin), "cols": list(df_fin.columns) if not df_fin.empty else []},
            "資產負債表 (df_bal)": {"rows": len(df_bal), "cols": list(df_bal.columns) if not df_bal.empty else []},
            "現金流量表 (df_cf)": {"rows": len(df_cf), "cols": list(df_cf.columns) if not df_cf.empty else []},
            "股利 (df_div)": {"rows": len(df_div), "cols": list(df_div.columns) if not df_div.empty else []},
            "本益比 (df_per)": {"rows": len(df_per), "cols": list(df_per.columns) if not df_per.empty else []},
            "三大法人 (df_inst)": {"rows": len(df_inst), "cols": list(df_inst.columns) if not df_inst.empty else []},
            "融資券 (df_margin)": {"rows": len(df_margin), "cols": list(df_margin.columns) if not df_margin.empty else []},
            "借券 (df_ss)": {"rows": len(df_ss), "cols": list(df_ss.columns) if not df_ss.empty else []},
        }
        
        if df_price.empty:
            st.error(f"❌ 無法取得股票 {stock_id} 的資料，請確認股票代號是否正確")
            st.stop()
        
        # 取得股票名稱
        stock_name = stock_id
        if df_info is not None and not df_info.empty:
            if "stock_name" in df_info.columns:
                stock_name = df_info["stock_name"].iloc[0]
        
        # ===== 第 2 段：🔄 建構母表 (30-45%) =====
        update_progress(32, "🔄 [2/5] 建構母表（頻率對齊、公告日對齊）...")
        base = build_universal_base_table(
            df_price, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss
        )
        
        # === 加入產業資訊（供 is_finance 金融業防錯判斷） ===
        if df_info is not None and not df_info.empty and "industry_category" in df_info.columns:
            base["Industry"] = df_info["industry_category"].iloc[0]
        
        # ===== 第 3 段：📊 計算指標 (45-65%) =====
        update_progress(47, "📊 [3/5] 計算衍生欄位（MA、TTM、百分位）...")
        base = calculate_derived_columns(base)
        
        update_progress(55, "📊 [3/5] 計算技術指標（RSI、量比、籌碼背離）...")
        base = calculate_technical_indicators(base)
        
        update_progress(62, "📊 [3/5] 計算財務指標（ROE、毛利率、配息率）...")
        base = calculate_financial_indicators(base)
        
        # ===== 第 4 段：🎯 評分分析 (65-80%) =====
        update_progress(67, "🎯 [4/5] 四風格打分（短線、波段、價值、定存）...")
        scores = get_all_scores(base)
        
        update_progress(74, "🎯 [4/5] 產生存股建議（四維度投票）...")
        try:
            trade_advice = generate_trade_advice(
                stock_id=stock_id,
                df=base,
                scores=scores,
                current_shares=shares if has_position else 0,
                average_cost=avg_price if has_position else 0.0,
            )
        except Exception:
            trade_advice = None
        
        update_progress(77, "🎯 [4/5] 產生基本建議...")
        advice = get_advice(scores)
        
        # ===== 第 5 段：🤖 AI 解說 (80-100%) =====
        ai_result = None
        if deepseek_api_key:
            update_progress(82, "🤖 [5/5] AI 解說分析（呼叫 DeepSeek）...")
            ai_result = analyze_with_deepseek(
                stock_id=stock_id,
                stock_name=stock_name,
                scores=scores,
                advice=advice,
                has_position=has_position,
                avg_price=avg_price,
                shares=shares,
                api_key=deepseek_api_key,
                trade_advice=trade_advice,
            )
        else:
            update_progress(95, "🤖 [5/5] 未設定 API Key，跳過 AI 解說")
        
        # 存入快取（包含所有原始資料，供圖表使用）
        st.session_state["analyzed"] = True  # 頂層標記
        st.session_state[cache_key] = {
            "base": base,
            "fetch_info": fetch_info,
            "scores": scores,
            "advice": advice,
            "trade_advice": trade_advice,
            "ai_result": ai_result,
            "stock_name": stock_name,
            "df_taiex": df_taiex,
            "df_info": df_info,
            "df_rev": df_rev,
            "df_fin": df_fin,
            "df_bal": df_bal,
            "df_cf": df_cf,
            "df_div": df_div,
            "df_price": df_price,
            "df_per": df_per,
            "df_inst": df_inst,
            "df_margin": df_margin,
            "df_ss": df_ss,
        }
        
        update_progress(100, "✅ 分析完成！")
        progress_bar.empty()
        status_text.empty()
    
    # ===== 瀑布流 1：撈取完成 → 大盤資訊卡 + 個股資訊卡 =====
    with waterfall_1.container():
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
        
        tab1, tab2, tab3 = st.tabs(["短線面", "中長線面", "📊 回測分析"])
        
        with tab1:
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
        
        with tab2:
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
                
                # 圖表 1: 營收 YoY（從母表，約 1 年區間，日頻走勢）
                fig_sw1, ax_sw1 = plt.subplots(figsize=(12, 4))
                if "Revenue_YoY" in base.columns:
                    ax_sw1.plot(base["date"], base["Revenue_YoY"], label="營收 YoY", color="green", linewidth=1.5)
                    ax_sw1.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
                ax_sw1.set_title(f"{stock_id} {stock_name} - 營收年增率 YoY（權重 25%）")
                ax_sw1.set_ylabel("YoY (%)")
                ax_sw1.legend(loc="best")
                ax_sw1.grid(True, alpha=0.3)
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
                    # 圖表 1: ROE / 毛利率（獲利品質 20%）
                    fig_v1, ax_v1 = plt.subplots(figsize=(12, 4))
                    val_chart1 = {"ROE_TTM": "ROE", "Gross_Margin": "毛利率"}
                    for col, label in val_chart1.items():
                        if col in df_fin_pivot.columns:
                            ax_v1.plot(df_fin_pivot["date"], df_fin_pivot[col], label=label, linewidth=1.5, marker="o", markersize=3)
                    ax_v1.set_title(f"{stock_id} {stock_name} - ROE / 毛利率（權重 20%）")
                    ax_v1.set_ylabel("百分比 (%)")
                    ax_v1.legend(loc="best")
                    ax_v1.grid(True, alpha=0.3)
                    plt.tight_layout()
                    st.pyplot(fig_v1)
                    plt.close()
                    
                    st.markdown("---")
                    
                    # 圖表 2: TTM EPS + 營收YoY（成長能力 30%）
                    fig_v2, ax_v2_1 = plt.subplots(figsize=(12, 4))
                    ax_v2_2 = ax_v2_1.twinx()
                    if "TTM_EPS" in df_fin_pivot.columns:
                        ax_v2_1.plot(df_fin_pivot["date"], df_fin_pivot["TTM_EPS"], label="TTM EPS", color="blue", linewidth=1.5, marker="o", markersize=3)
                    ax_v2_1.set_ylabel("TTM EPS", color="blue")
                    if "Revenue_YoY" in base.columns:
                        ax_v2_2.plot(base["date"], base["Revenue_YoY"], label="營收 YoY", color="green", linewidth=1.5, linestyle="--")
                    ax_v2_2.set_ylabel("營收 YoY (%)", color="green")
                    ax_v2_1.set_title(f"{stock_id} {stock_name} - TTM EPS 與營收成長（權重 30%）")
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
                
                # 圖表 2: TTM FCF / 負債比（現金流 20% + 財務安全 15%）
                fig_d2, ax_d2_1 = plt.subplots(figsize=(12, 4))
                ax_d2_2 = ax_d2_1.twinx()
                if df_fin_pivot is not None and not df_fin_pivot.empty:
                    if "TTM_FCF" in df_fin_pivot.columns:
                        ax_d2_1.bar(df_fin_pivot["date"], df_fin_pivot["TTM_FCF"], label="TTM FCF", alpha=0.6, width=30, color="green")
                    if "Debt_Ratio" in df_fin_pivot.columns:
                        ax_d2_2.plot(df_fin_pivot["date"], df_fin_pivot["Debt_Ratio"], label="負債比", color="red", linewidth=1.5, marker="o", markersize=3)
                ax_d2_1.set_ylabel("TTM FCF", color="green")
                ax_d2_2.set_ylabel("負債比 (%)", color="red")
                ax_d2_1.set_title(f"{stock_id} {stock_name} - 自由現金流 / 負債比（權重 20%+15%）")
                ax_d2_1.legend(loc="upper left")
                ax_d2_2.legend(loc="upper right")
                ax_d2_1.grid(True, alpha=0.3)
                plt.tight_layout()
                st.pyplot(fig_d2)
                plt.close()
                
                st.markdown("---")
                
                # 圖表 3: PE/PB Percentile + 殖利率（估值安全 + 股東報酬）
                fig_d3, ax_d3_1 = plt.subplots(figsize=(12, 4))
                ax_d3_2 = ax_d3_1.twinx()
                if "pe_ratio" in base.columns:
                    ax_d3_1.plot(base["date"], base["pe_ratio"], label="本益比", color="red", linewidth=1.5)
                if "pb_ratio" in base.columns:
                    ax_d3_1.plot(base["date"], base["pb_ratio"], label="股價淨值比", color="purple", linewidth=1.5, linestyle="--")
                if "dividend_yield" in base.columns:
                    ax_d3_2.plot(base["date"], base["dividend_yield"], label="殖利率", color="green", linewidth=1.5, linestyle=":")
                ax_d3_1.set_ylabel("PE / PB", color="red")
                ax_d3_2.set_ylabel("殖利率 (%)", color="green")
                ax_d3_1.set_title(f"{stock_id} {stock_name} - 本益比 / 淨值比 / 殖利率")
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
    
        # ===== Tab 3: 📊 回測分析（雙策略：積極+保守） =====
        with tab3:
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
                    bt_run = st.button("▶️ 執行回測（雙策略）", type="primary")
                
                # 清除舊股票的回測殘留
                if "bt_result" in st.session_state and st.session_state["bt_result"].stock_id != stock_id:
                    for k in ["bt_result", "bt_active", "bt_conservative", 
                               "_bt_csv_path_a", "_bt_csv_name_a",
                               "_bt_csv_path_c", "_bt_csv_name_c", "bt_strategy"]:
                        st.session_state.pop(k, None)
                
                # 每次點擊「執行回測」都重新執行 — 同時跑積極(70/50)和保守(60/40)
                if bt_run:
                    with st.spinner("⏳ 執行回測中（雙策略：積極 60/40 + 保守 70/50）..."):
                        bt_active = run_backtest(
                            df=base,
                            stock_id=stock_id,
                            start_date=bt_start.strftime("%Y-%m-%d"),
                            end_date=bt_end.strftime("%Y-%m-%d"),
                            freq=bt_freq,
                            buy_threshold=60, sell_threshold=40,
                            strategy="active",
                        )
                        bt_conservative = run_backtest(
                            df=base,
                            stock_id=stock_id,
                            start_date=bt_start.strftime("%Y-%m-%d"),
                            end_date=bt_end.strftime("%Y-%m-%d"),
                            freq=bt_freq,
                            buy_threshold=70, sell_threshold=50,
                            strategy="conservative",
                        )
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
                    
                    # === B. 分數走勢圖 ===
                    st.markdown("**📈 四維度分數走勢**")
                    fig_bt1, ax_bt1 = plt.subplots(figsize=(12, 5))
                    sh = bt.signal_history
                    if not sh.empty and "date" in sh.columns:
                        ax_bt1.plot(sh["date"], sh["short_term_score"], label="短線", color="red", linewidth=1.5)
                        ax_bt1.plot(sh["date"], sh["swing_score"], label="波段", color="orange", linewidth=1.5)
                        ax_bt1.plot(sh["date"], sh["value_score"], label="價值", color="blue", linewidth=1.5)
                        ax_bt1.plot(sh["date"], sh["dividend_score"], label="定存", color="green", linewidth=1.5)
                        ax_bt1.axhline(y=bt_buy, color="green", linestyle="--", alpha=0.5, label=f"買入門檻({bt_buy})")
                        ax_bt1.axhline(y=bt_sell, color="red", linestyle="--", alpha=0.5, label=f"賣出門檻({bt_sell})")
                        ax_bt1.set_ylabel("分數")
                        ax_bt1.set_ylim(0, 100)
                        ax_bt1.legend(loc="best")
                        ax_bt1.grid(True, alpha=0.3)
                        ax_bt1.set_title(f"{stock_id} {stock_name}（{strategy_label}） - 歷史評分走勢（{bt.start_date} ~ {bt.end_date}）")
                        plt.tight_layout()
                        st.pyplot(fig_bt1)
                        plt.close()
                    
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
                    
                    # === D. 績效摘要表 ===
                    st.markdown("**📋 五種策略績效總覽**")
                    style_names = {"short_term": "短線", "swing": "波段", "value": "價值", "dividend": "定存", "composite": "綜合"}
                    perf_cols = st.columns(5)
                    for i, (sk, scn) in enumerate(style_names.items()):
                        with perf_cols[i]:
                            sd = bt.styles.get(sk, {})
                            tc = sd.get("trade_count", 0)
                            ret = sd.get("total_return_pct", 0.0)
                            wr = sd.get("win_rate", 0.0)
                            delta = f"⬆️ +{ret:.1f}%" if ret > 10 else (f"↗️ +{ret:.1f}%" if ret > 0 else (f"➖ 0%" if ret == 0 else f"⬇️ {ret:.1f}%"))
                            st.metric(f"{scn}", f"{tc}筆", delta)
                            win_rate_str = f"勝率: {wr:.0f}%" if wr is not None else "勝率: -"
                            st.caption(win_rate_str)
                            holding_trades = [t for t in sd.get("trades", []) if t.status == "持有中"]
                            if holding_trades:
                                for ht in holding_trades:
                                    st.info(f"✅ {ht.style}持有中")
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
                    
                    # CSV 下載按鈕（積極/保守各一個）
                    st.markdown("---")
                    st.markdown("**💾 回測 CSV 除錯輸出**")
                    st.caption(f"📁 已儲存至：`data/debug/` 目錄")
                    col_dl1, col_dl2 = st.columns(2)
                    with col_dl1:
                        path_a = st.session_state.get("_bt_csv_path_a", "")
                        fn_a = st.session_state.get("_bt_csv_name_a", "backtest_active.csv")
                        if st.session_state.get("bt_active") is not None:
                            csv_data_a = st.session_state["bt_active"].signal_history.to_csv(index=False, encoding='utf-8-sig')
                            st.download_button(label="📥 下載 積極(60/40) CSV", data=csv_data_a, file_name=fn_a, mime="text/csv")
                    with col_dl2:
                        path_c = st.session_state.get("_bt_csv_path_c", "")
                        fn_c = st.session_state.get("_bt_csv_name_c", "backtest_conservative.csv")
                        if st.session_state.get("bt_conservative") is not None:
                            csv_data_c = st.session_state["bt_conservative"].signal_history.to_csv(index=False, encoding='utf-8-sig')
                            st.download_button(label="📥 下載 保守(70/50) CSV", data=csv_data_c, file_name=fn_c, mime="text/csv")
                        
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
    
    # ===== 瀑布流 3：評分完成 → 四維度分析卡 + 基本建議 =====
    with waterfall_3.container():
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
        
        cols = st.columns(4)
        for i, (key, (label, icon)) in enumerate(score_labels.items()):
            with cols[i]:
                score_data = scores.get(key, {})
                total = score_data.get("total", 0)
                breakdown = score_data.get("breakdown", {})
                
                if total >= 70:
                    delta = "⬆️ 佳"
                elif total >= 50:
                    delta = "➡️ 普通"
                else:
                    delta = "⬇️ 待加強"
                
                st.metric(f"{icon} {label}", f"{total}/100", delta)
                
                breakdown_labels = {
                    "trend_structure": ("趨勢結構", 20),
                    "momentum": ("動能強度", 20),
                    "volume": ("成交量結構", 20),
                    "institutional": ("法人籌碼", 15),
                    "chip": ("籌碼健康", 15),
                    "risk": ("波動風險", 10),
                    "revenue_momentum": ("營收動能", 25),
                    "mid_trend": ("中期趨勢", 20),
                    "institutional_trend": ("籌碼趨勢", 20),
                    "earnings_growth": ("獲利成長", 15),
                    "valuation": ("估值位置", 10),
                    "catalyst": ("催化因子", 10),
                    "valuation_safety": ("估值安全", 25),
                    "profit_quality": ("獲利品質", 20),
                    "growth_ability": ("成長能力", 20),
                    "financial_safety": ("財務安全", 15),
                    "cash_flow_quality": ("現金流品質", 10),
                    "shareholder_return": ("股東報酬", 10),
                    "dividend_record": ("配息紀錄", 25),
                    "dividend_quality": ("配息品質", 20),
                    "cash_flow": ("現金流", 20),
                    "profit_stability": ("獲利穩定", 10),
                    "long_term_growth": ("長期成長", 10),
                }
                with st.expander("查看細項"):
                    st.markdown("**各子項評分明細**")
                    details = score_data.get("details", {})
                    for sub_key, sub_val in breakdown.items():
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
                    
                    modifiers = score_data.get("modifiers", {})
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
                    "📈 技術面": ["MA_5", "MA_10", "MA_20", "MA_60", "RSI_6", "MA_Alignment", "Volume_Ratio", "MA60_Bias", "ATR", "High_5D", "High_10D", "High_20D", "Vol_MA_5", "Above_MA_5", "Above_MA_10", "Above_MA_20", "Above_MA_60", "Bullish_MA", "Volume_Above_MA5"],
                    "🏦 籌碼面": ["Foreign_Net", "Trust_Net", "Dealer_Net", "Inst_Net", "Inst_5D_Net", "Inst_20D_Net", "Chip_Divergence", "Margin_5D_Change", "Short_5D_Change", "SBL_5D_Change", "Inst_Consecutive_Days"],
                    "📊 基本面": ["Revenue_YoY", "Revenue_MoM", "Revenue_Accelerating", "Revenue_Momentum", "Price_Revenue_Divergence", "TTM_EPS", "TTM_EPS_Valid", "TTM_FCF", "TTM_OCF", "TTM_OperatingCF", "TTM_CAPEX", "TTM_NetIncome", "ROE_TTM", "ROE_Stability", "ROA_TTM", "Gross_Margin", "Gross_Margin_Stability", "Operating_Margin", "Current_Ratio", "Interest_Coverage", "EPS_Stability", "EPS_YoY", "EPS_YoY_Reason", "Debt_Ratio", "Debt_Ratio_Trend", "PE_Percentile", "PB_Percentile", "pe_ratio", "pb_ratio"],
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
                        "📈 技術面": ["close", "volume", "MA_5", "MA_10", "MA_20", "MA_60", "RSI_6", "MA_Alignment", "Volume_Ratio", "MA60_Bias", "ATR"],
                        "🏦 籌碼面": ["Foreign_Net", "Trust_Net", "Dealer_Net", "Inst_5D_Net", "Inst_20D_Net", "Margin_5D_Change", "Short_5D_Change", "SBL_5D_Change", "Inst_Consecutive_Days"],
                        "📊 基本面": ["Revenue_YoY", "Revenue_MoM", "Revenue_Accelerating", "Revenue_Momentum", "TTM_EPS", "TTM_EPS_Valid", "TTM_FCF", "TTM_OCF", "ROE_TTM", "ROE_Stability", "ROA_TTM", "Gross_Margin", "Debt_Ratio", "Current_Ratio", "Interest_Coverage", "PE_Percentile", "PB_Percentile"],
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
                
                # 選擇要匯出的欄位群組
                export_cols = st.multiselect(
                    "選擇要匯出的欄位（預設全部）",
                    options=list(base.columns),
                    default=list(base.columns),
                    key="export_cols"
                )
                
                # 手動按鈕
                if st.button("💾 手動匯出 CSV", type="primary"):
                    export_cols_selected = export_cols if export_cols else list(base.columns)
                    export_df_selected = base[export_cols_selected]
                    csv_data = export_df_selected.to_csv(index=False, encoding='utf-8-sig')
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{stock_id}_{timestamp}_debug.csv"
                    
                    # 存到 bug/ 目錄
                    bug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bug")
                    os.makedirs(bug_dir, exist_ok=True)
                    filepath = os.path.join(bug_dir, filename)
                    with open(filepath, "w", encoding="utf-8-sig") as f:
                        f.write(csv_data)
                    
                    st.success(f"✅ 已儲存至：`{filepath}`")
                    st.caption(f"📊 {len(export_df_selected)} 行 x {len(export_df_selected.columns)} 欄")
                else:
                    st.info("點擊上方按鈕手動匯出 CSV")
    
    # ===== 瀑布流 6：回測結果摘要（若有執行過） =====
    with waterfall_6.container():
        _bt = st.session_state.get("bt_result")
        if _bt is not None and _bt.stock_id == stock_id:
            bt = _bt
            cur_strategy = st.session_state.get("bt_strategy", "active")
            strategy_label = "積極 (60/40)" if cur_strategy == "active" else "保守 (70/50)"
            
            st.markdown("---")
            st.subheader(f"📊 回測結果摘要（{strategy_label}）")
            
            style_names = {
                "short_term": "短線", "swing": "波段",
                "value": "價值", "dividend": "定存", "composite": "綜合",
            }
            
            # 更新摘要顯示（使用瀑布流最後的 latest 指標資訊）
            best_style = ""
            best_return = -999
            for sk, scn in style_names.items():
                sd = bt.styles.get(sk, {})
                ret = sd.get("total_return_pct", 0.0)
                if ret > best_return:
                    best_return = ret
                    best_style = scn
            
            # 五欄 KPI
            bt_cols = st.columns(5)
            for i, (sk, scn) in enumerate(style_names.items()):
                with bt_cols[i]:
                    sd = bt.styles.get(sk, {})
                    tc = sd.get("trade_count", 0)
                    ret = sd.get("total_return_pct", 0.0)
                    wr = sd.get("win_rate", 0.0)
                    
                    if ret > 10:
                        delta = f"⬆️ +{ret:.1f}%"
                    elif ret > 0:
                        delta = f"↗️ +{ret:.1f}%"
                    elif ret == 0:
                        delta = "0%"
                    else:
                        delta = f"⬇️ {ret:.1f}%"
                    
                    st.metric(f"{scn}", f"{tc}筆", delta)
                    win_rate_str = f"勝率 {wr:.0f}%" if wr is not None else "勝率: -"
                    st.caption(win_rate_str)
                    
                    # 持有中標示
                    trades = sd.get("trades", [])
                    holding_trades = [t for t in trades if t.status == "持有中"]
                    if holding_trades:
                        for ht in holding_trades:
                            st.caption(f"✅ 持有中({ht.return_pct:+.1f}%)")
            
            # 瀑布流 6 結束
            st.caption(f"📅 回測區間: {bt.start_date} ~ {bt.end_date} | 📊 最佳策略: {best_style} (+{best_return:.1f}%) | 門檻: 買≥{bt.buy_threshold} / 賣<{bt.sell_threshold}")
    
    # ===== 瀑布流結束後：底部免責聲明 =====
    st.markdown("---")
    st.caption("⚠️ 免責聲明：本系統僅供個人分析參考，不構成任何投資建議或推薦。使用者應自行審慎評估，投資有盈虧風險，請自負責任。")
            
except Exception as e:
    progress_bar.empty()
    status_text.empty()
    st.error(f"❌ 分析過程中發生錯誤：{str(e)}")
    st.exception(e)
    st.stop()