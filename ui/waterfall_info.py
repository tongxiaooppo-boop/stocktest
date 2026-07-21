"""
ui/waterfall_info.py — 瀑布流 1
"""
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime, timedelta
from ui.components import FIELD_CN_MAP, cn, _radar_chart

def render_waterfall_1(st_obj, base, fetch_info, scores, advice, trade_advice, ai_result,
                  stock_id, stock_name, avg_price, shares, has_position,
                  df_taiex, df_price, df_info, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss,
                  selected_profile=None, deepseek_api_key=None, run_bt=False):
    
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
            scores = get_all_scores(base, profile=selected_profile)
            
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