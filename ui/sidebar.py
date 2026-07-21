"""
ui/sidebar.py — 側邊欄 UI
"""
import streamlit as st
import os

def render_sidebar():
    """渲染側邊欄，回傳 (stock_id, finmind_token, deepseek_api_key, avg_price, shares, selected_profile, analyze_btn, backtest_btn, refresh_cache_btn)"""
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

        # === v3.0 短線分析師人格選擇 ===
        analyst_profile = st.radio(
            "🧠 短線分析師",
            options=["激進型", "穩重型"],
            format_func=lambda x: f"🔥 {x}" if x == "激進型" else f"🛡️ {x}",
            horizontal=True,
            help="激進型：重動能/慣性突破，適合強勢股追價\n穩重型：重趨勢/法人籌碼，適合盤整或保守進場",
            key="analyst_profile",
        )
        _profile_map = {"激進型": "chaser", "穩重型": "stable"}
        selected_profile = _profile_map[analyst_profile]

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

    return stock_id, finmind_token, deepseek_api_key, avg_price, shares, selected_profile, analyze_btn, backtest_btn, refresh_cache_btn