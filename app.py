"""
台股AI個人化決策系統 v2.0
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
from data.price_adjuster import PriceAdjuster

from stock.metrics import calculate_technical_indicators, calculate_financial_indicators
from core.scorer import get_all_scores, get_historical_scores
from core.backtest import _calc_realized_return_sum, _calc_unrealized_return
from core.advisor import get_advice
from core.trade_manager import generate_trade_advice
from ai.analyzer import analyze_with_deepseek

# 新聞模組（被動查詢，不影響既有分析流程）
from news.fetcher import fetch_news
from news.analyzer import analyze as analyze_news, get_sentiment_label, get_sentiment_color
from news.database import save_news, get_historical_sentiment, get_aggregate_sentiment

# 設定 matplotlib 支援中文（使用內附 Noto Sans TC 字型）
import matplotlib.font_manager as fm
_font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "NotoSansTC-Regular.otf")
if os.path.exists(_font_path):
    fm.fontManager.addfont(_font_path)
    plt.rcParams['font.family'] = fm.FontProperties(fname=_font_path).get_name()
else:
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
    # 短線細項原始資料（sub_details）
    "ma_alignment": "均線排列",
    "ma_alignment_score": "均線排列評分",
    "above_ma_count": "站上均線數",
    "above_ma_score": "站上均線評分",
    "rsi": "RSI(6)",
    "dist_high_5d": "距高點比例",
    "break_low_5d": "破底(5日)",
    "macd_positive": "MACD柱正",
    "volume_ratio": "量比",
    "volume_ratio_score": "量比評分",
    "surge_score": "爆量評分",
    "inst_5d_net": "法人5日淨額",
    "inst_5d_score": "法人5日評分",
    "inst_20d_score": "法人20日評分",
    "inst_20d_is_proxy": "20日為代理",
    "foreign_score": "外資評分",
    "trust_score": "投信評分",
    "margin_5d_change": "融資5日變化",
    "margin_score": "融資評分",
    "short_5d_change": "融券5日變化",
    "short_score": "融券評分",
    "sbl_score": "借券評分",
    "bias_5d": "5日乖離率",
    # note 類
    "note": "備註",
    # 波段細項原始資料（revenue_momentum）
    "revenue_yoy": "營收年增率",
    "yoy_score": "年增率評分",
    "mom_score": "月增率評分",
    "accel_score": "加速度評分",
    "cagr_1_5y": "1.5年CAGR",
    "cagr_score": "CAGR評分",
    # 波段細項（mid_trend）
    "above_ma20": "站上20MA",
    "above_ma60": "站上60MA",
    "ma20_slope": "20MA斜率",
    # 波段細項（institutional_trend）
    "inst_slope_20d": "法人20日斜率",
    "inst_20d_net": "法人20日淨額",
    # 波段細項（earnings_growth）
    "ttm_eps": "近四季EPS",
    "eps_score": "EPS評分",
    "eps_yoy": "EPS年成長率",
    "eps_yoy_score": "EPS年增評分",
    "eps_yoy_available": "EPS年增可用",
    "eps_yoy_note": "EPS年增備註",
    # 波段細項（valuation）
    "pe_percentile": "本益比百分位",
    "pe_score": "本益比評分",
    "pb_percentile": "淨值比百分位",
    "pb_score": "淨值比評分",
    # 波段細項（catalyst）
    "revenue_momentum": "營收動能",
    "catalyst_score": "催化評分",
    # 價值細項（valuation_safety）
    "pe_ttm": "本益比(TTM)",
    # 價值細項（profit_quality）
    "roe": "ROE",
    "gross_margin": "毛利率",
    # 價值細項（growth_ability）
    "rev_score": "營收評分",
    # 價值細項（financial_safety）
    "debt_ratio": "負債比",
    "debt_score": "負債比評分",
    "current_ratio": "流動比率",
    "cr_score": "流動比率評分",
    # 價值細項（cash_flow_quality）
    "ttm_fcf": "近四季FCF",
    "fcf_score": "FCF評分",
    "ocf_score": "營運現金流評分",
    # 價值細項（shareholder_return）
    "dividend_yield": "殖利率",
    "yield_score": "殖利率評分",
    "dividend": "現金股利",
    "div_score": "股利評分",
    # 定存細項（dividend_record）
    "dividend_continuity_years": "連續配息年數",
    # 定存細項（dividend_quality）
    "payout_ratio": "配息率",
    "eps_cover": "EPS覆蓋率",
    # 定存細項（cash_flow）
    "cash_conv_ratio": "現金轉換率",
    "fcf_positive": "FCF正數",
    # 定存細項（financial_safety）
    "interest_coverage": "利息保障倍數",
    "ic_score": "利息保障評分",
    # 定存細項（profit_stability）
    "roe_std": "ROE標準差",
    "eps_std": "EPS標準差",
    # 定存細項（long_term_growth）
    "rev_cagr": "營收CAGR",
    # modifier 相關
    "data_quality": "資料品質",
    "data_years": "資料年數",
    "modifier": "調整係數",
    "adjusted_score": "調整後分數",
    "finance_redistribution": "金融業權重再分配",
}

def cn(val: str) -> str:
    """將英文欄位名稱轉為中文，若無對照則保留原文"""
    return FIELD_CN_MAP.get(val, val)


def _radar_chart(labels: list, values: list, title: str, color: str,
                 label_weights: list = None) -> plt.Figure:
    """繪製六邊形雷達圖（支援 6 子項）"""
    import numpy as np
    N = len(labels)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]
    values_closed = values + values[:1]
    
    fig, ax = plt.subplots(figsize=(3.8, 3.8), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    
    for level in [20, 40, 60, 80, 100]:
        ax.plot(angles, [level] * len(angles), color='gray', linestyle='--', linewidth=0.5, alpha=0.3)
    ax.plot(angles, [0] * len(angles), color='gray', linewidth=0.5, alpha=0.5)
    
    ax.fill(angles, values_closed, alpha=0.15, color=color)
    ax.plot(angles, values_closed, color=color, linewidth=2)
    
    if label_weights:
        tick_labels = [f"{l}\n({w}%)" for l, w in zip(labels, label_weights)]
    else:
        tick_labels = labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(tick_labels, fontsize=8, fontweight='bold')
    
    ax.set_ylim(0, 105)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=7)
    
    ax.set_title(title, fontsize=12, fontweight='bold', pad=18, color=color)
    plt.tight_layout()
    return fig


st.set_page_config(
    page_title="台股AI個人化決策系統 v2.0",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📈 台股AI個人化決策系統 v2.0 🕐 盤後版")
st.caption("⚠️ 免責聲明：本系統僅供個人分析參考，不構成任何投資建議或推薦。使用者應自行審慎評估，投資有盈虧風險，請自負責任。")
st.caption("📌 **資料更新時間說明（依 FinMind 更新時程，非即時報價）**：")
st.caption("   📊 **股價收盤價** — 盤後約 **14:30~15:30** 更新（當日收盤）")
st.caption("   🏦 **三大法人買賣超** — 每日約 **16:00~17:00** 更新")
st.caption("   💰 **融資融券餘額** — 每日約 **20:00~21:30** 更新（含上櫃）")
st.caption("   📰 **新聞輿情** — 自動抓取近期公開新聞")
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
    
    st.markdown("---")
    refresh_cache_btn = st.button("🔄 強制刷新資料", type="secondary", use_container_width=True)
    st.caption("清除今日快取，下次分析將重新撈取 FinMind")
    
    st.markdown("---")
    st.markdown("**📚 文件瀏覽**")
    st.caption("點選後在主畫面顯示")
    _doc_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    _doc_files = [
        ("📘 使用說明書", "USER_GUIDE.md"),
        ("📖 安裝與設定", "SETUP.md"),
        ("🏗️ 系統架構", "ARCHITECTURE.md"),
        ("📊 評分細則", "SCORING.md"),
        ("📋 改版歷程", "CHANGELOG.md"),
    ]
    for _label, _fname in _doc_files:
        if st.button(_label, use_container_width=True, key=f"doc_btn_{_fname}"):
            st.session_state["_doc_to_show"] = _fname
            st.session_state["_doc_to_show_label"] = _label

# ===== 文件瀏覽器（點側邊欄按鈕後顯示在主畫面，放在 st.stop() 之前確保不受影響） =====
_doc_to_show = st.session_state.get("_doc_to_show", None)
_doc_to_show_label = st.session_state.get("_doc_to_show_label", "")
if _doc_to_show:
    _fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", _doc_to_show)
    if os.path.exists(_fpath):
        with open(_fpath, "r", encoding="utf-8") as _fh:
            _content = _fh.read()
        st.info(f"📖 目前閱讀：**{_doc_to_show_label}**")
        with st.container():
            st.markdown(_content)
        if st.button("❌ 關閉文件", type="secondary"):
            st.session_state["_doc_to_show"] = None
            st.rerun()
        st.markdown("---")
    else:
        st.session_state["_doc_to_show"] = None

# ===== 追蹤按鈕點擊事件 =====
cache_key = f"cache_{stock_id}"

if backtest_btn:
    if cache_key in st.session_state:
        st.session_state["run_backtest"] = True
        # 點擊回測後自動跳到 tab3
        st.session_state["_active_tab"] = 2
    else:
        st.session_state["run_backtest"] = False

# 強制刷新：清除 session_state + SQLite + Parquet 快取
if refresh_cache_btn:
    # 清除 session 快取
    if cache_key in st.session_state:
        del st.session_state[cache_key]
    st.session_state["analyzed"] = False
    # 清除 SQLite 快取
    try:
        from news.database import delete_analysis_cache
        delete_analysis_cache(stock_id)
    except Exception:
        pass
    # 清除 Parquet 快取
    try:
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cache")
        parquet_path = os.path.join(cache_dir, f"{stock_id}_base.parquet")
        if os.path.exists(parquet_path):
            os.remove(parquet_path)
    except Exception:
        pass
    st.info(f"✅ 已清除 {stock_id} 的快取，請再次點擊「開始分析」重新撈取")

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
    # ===== 檢查快取：優先 session_state，其次 SQLite (analysis_cache) =====
    cache_key = f"cache_{stock_id}"
    _has_cache = cache_key in st.session_state
    
    # 如果 session_state 沒有快取，嘗試從 SQLite + Parquet 載入
    if not _has_cache:
        try:
            from news.database import load_analysis_cache
            sql_cache = load_analysis_cache(stock_id)
            # Parquet 快取路徑
            cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cache")
            parquet_path = os.path.join(cache_dir, f"{stock_id}_base.parquet")
            
            if sql_cache is not None and os.path.exists(parquet_path):
                # 檢查快取日期：同一天有效，跨天強制重跑（FinMind 資料可能已更新）
                cache_date = sql_cache.get("cache_date", "")
                today = datetime.now().strftime("%Y-%m-%d")
                cache_is_today = cache_date and cache_date.startswith(today)
                
                if cache_is_today:
                    base = pd.read_parquet(parquet_path)
                    sql_cache["base"] = base
                    st.session_state[cache_key] = sql_cache
                    _has_cache = True
                else:
                    # 過期快取，清除後讓系統重新分析
                    from news.database import delete_analysis_cache
                    delete_analysis_cache(stock_id)
                    if os.path.exists(parquet_path):
                        os.remove(parquet_path)
                    # 不顯示提示訊息，靜默重新分析
        except Exception:
            pass
    
    if _has_cache:
        cache = st.session_state[cache_key]
        
        # 檢查快取中的 trade_advice 是否為舊版（缺 v4.4 雙軌欄位）
        # 注意：TradeAdvice 是 dataclass，hasattr 對 agg_entry 永遠 True（有預設值）
        # 改用檢查 agg_entry 是否為 None 來判斷是否真正有雙軌資料
        old_ta = cache.get("trade_advice", None)
        if old_ta is not None:
            is_old_version = (
                old_ta.agg_entry is None
                and old_ta.cons_entry is None
                and old_ta.action in ("買進",)
                and "建議價位區間對照" not in (old_ta.message or "")
            )
            if is_old_version:
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
            
            # 用最新的個人化持股重新產生 trade_advice（快取中的是舊的）
            try:
                trade_advice = generate_trade_advice(
                    stock_id=stock_id,
                    df=base,
                    scores=scores,
                    current_shares=shares if has_position else 0,
                    average_cost=avg_price if has_position else 0.0,
                )
            except Exception:
                pass  # 沿用快取中的 trade_advice
            
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
            st.error(f"❌ 無法取得股票 {stock_id} 的股價資料")
            st.caption("可能原因：")
            st.caption("1. FinMind API Token 有誤或尚未啟用（申請後需幾分鐘才能用）")
            st.caption("2. 股票代號不正確（台股請輸入 4 碼數字，如 2330）")
            st.caption("3. FinMind 伺服器暫時不穩定（可稍後再試）")
            st.caption("4. 可在 Render Log 中查看 [FETCH_ERROR] 詳細錯誤")
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
        
        # === 📌 保留 adj_close（fetch_stock_price 已計算，但 build_universal_base_table 只取 price_cols 丟失了它） ===
        try:
            if "adj_close" in df_price.columns:
                adj_df = df_price[["date", "adj_close", "adj_factor"]].copy()
                if "adj_volume" in df_price.columns:
                    adj_df["adj_volume"] = df_price["adj_volume"]
                adj_df["date"] = pd.to_datetime(adj_df["date"])
                base["date"] = pd.to_datetime(base["date"])
                base = base.merge(adj_df, on="date", how="left")
        except Exception:
            pass

        # === 📌 過濾髒資料（股價 <= 0 的行會導致 rolling MA 全部崩塌） ===
        base = base[base["close"] > 0].copy()

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
        
        # ===== (補充) 📰 跟隨個股分析，自動抓取新聞（先抓，AI 解說時可引用） =====
        news_data = None  # 預設無資料
        sentiment_data = None  # 輿情統計，供 AI 解說引用
        try:
            update_progress(82, "📰 跟隨抓取新聞輿情...")
            fetched_news = fetch_news(stock_id, limit=10)
            if fetched_news:
                # 情緒分析
                fetched_news = analyze_news(fetched_news, text_field="title")
                # 先存入 SQLite（讓資料庫累積歷史 + 本次新增）
                _, _ = save_news(fetched_news)
                news_data = fetched_news
                
                # 短暫 delay 確保 SQLite 檔案寫入完成，再讀取統計供 AI 引用
                import time
                time.sleep(0.3)
                
                # 從 SQLite 讀取完整統計（包含歷史累積 + 本次新增）
                try:
                    from news.database import get_aggregate_sentiment
                    sentiment_data = get_aggregate_sentiment(stock_id)
                except Exception:
                    pass
                
                total = sentiment_data["total_news"] if sentiment_data else 0
                avg = sentiment_data["avg_score"] if sentiment_data else 0
                update_progress(86, f"📰 歷史累計 {total} 篇 | 情緒 {avg:.2f}" if sentiment_data else "📰 新聞無統計")
        except Exception:
            pass  # 新聞沒抓到不影響主分析流程

        # ===== 第 5 段：🤖 AI 解說 (85-100%) =====
        ai_result = None
        if deepseek_api_key:
            update_progress(90, "🤖 [5/5] AI 解說分析（呼叫 DeepSeek，含輿情參考）...")
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
                sentiment_data=sentiment_data,  # 傳入輿情統計（可能為 None）
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
        
        # 將分析結果持久化到磁碟（SQLite + Parquet），F5 後可直接載入
        try:
            from news.database import save_analysis_cache
            save_analysis_cache(
                stock_id=stock_id,
                scores=scores,
                advice=advice,
                ai_result=ai_result,
                trade_advice=trade_advice,
                fetch_info=fetch_info,
                stock_name=stock_name,
            )
            # 母表存為 Parquet
            cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cache")
            os.makedirs(cache_dir, exist_ok=True)
            base.to_parquet(os.path.join(cache_dir, f"{stock_id}_base.parquet"), index=False)
        except Exception:
            pass  # 快取寫入失敗不影響顯示
        
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
        cfg_map = {
            "short_term": ("🔴 短線", "#E74C3C", ["趨勢結構", "動能強度", "成交量", "法人籌碼", "籌碼健康", "波動風險"], [20,20,20,15,15,10], ["trend_structure", "momentum", "volume", "institutional", "chip", "risk"]),
            "swing": ("🟠 波段", "#E67E22", ["營收動能", "中期趨勢", "籌碼趨勢", "獲利成長", "估值位置", "催化因子"], [25,20,20,15,10,10], ["revenue_momentum", "mid_trend", "institutional_trend", "earnings_growth", "valuation", "catalyst"]),
        }
        for idx, (dk, mode, mode_icon) in enumerate(dual_keys):
            with radar_row1[idx]:
                base_title, color, labels, weights, sub_keys = cfg_map[dk]
                sd = st_data[dk]
                bd = sd.get("breakdown", {})
                vals = [bd.get(sk, 0) for sk in sub_keys]
                score = st_buy[dk] if mode == "買" else st_sell[dk]
                full_title = f"{base_title} {mode_icon}{mode} {score}"
                fig = _radar_chart(labels, vals, full_title, color, weights)
                st.pyplot(fig, use_container_width=True)
                plt.close()
                # 短線/波段雷達圖下方也加上「查看細項」
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