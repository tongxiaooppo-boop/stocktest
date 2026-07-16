"""
data/price_adjuster.py
股價還原模組 — 基於 FinMind 官方事件資料（TaiwanStockSplitPrice、
TaiwanStockCapitalReductionReferencePrice、TaiwanStockParValueChange）
計算還原股價 adj_close，確保歷史價格不被分割/減資/變額破壞。

還原因子方向結論（這是標準 practice）：
  factor = after_price / before_price
  套用 adj_close_before = close_before × factor
  
  對減資（22.05→48.15）：factor=2.18 → 歷史價格放大，事件日連續 ✅
  對分割（546→136.5）：factor=0.25 → 歷史價格縮小，事件日連續 ✅
  
  factor 只套用在事件日之前的價格，事件日之後（含）的價格維持不變。

連乘邏輯：
  最早的資料必須經過所有之後事件的調整，所以「從最舊事件開始，依序對之前
  的所有日期乘上 factor」，最早的日期自然被所有後續事件連乘。

使用方式：
    adjuster = PriceAdjuster(token)
    df_adj = adjuster.adjust(stock_id, df_price)
    # df_adj 包含 adj_close, adj_factor, adj_volume 欄位
"""

import requests
import time
import pandas as pd
import numpy as np

FINMIND_BASE_URL = "https://api.finmindtrade.com/api/v4/data"


def _fetch_finmind(dataset: str, stock_id: str, start_date: str, end_date: str, token: str) -> pd.DataFrame:
    """通用 FinMind API 呼叫"""
    time.sleep(1.5)
    params = {"dataset": dataset, "data_id": stock_id, "start_date": start_date, "end_date": end_date, "token": token}
    try:
        resp = requests.get(FINMIND_BASE_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == 200 and data.get("data"):
            return pd.DataFrame(data["data"])
    except Exception:
        pass
    return pd.DataFrame()


class PriceAdjuster:
    """
    股價還原器：抓取官方事件資料，計算累積還原因子，產出 adj_close。
    
    支援三種事件：
    - TaiwanStockSplitPrice（分割，如 1:4 分割）
    - TaiwanStockCapitalReductionReferencePrice（減資，如現金減資）
    - TaiwanStockParValueChange（變更面額，如 10→5）
    
    注意：減資的 after_price 是理論參考價，實際開盤價可能因市場
    供需偏離 ±10%。還原後的 adj_close 在事件日附近仍會有微小波動，
    但價格斷層已被消除。
    """

    def __init__(self, token: str):
        self.token = token
        self._events_cache = {}

    # ──────────────────────────────────────────────
    # 1. 事件抓取
    # ──────────────────────────────────────────────

    def fetch_split_events(self, stock_id: str) -> pd.DataFrame:
        """
        抓取三種事件資料，輸出統一的 events DataFrame。
        
        factor = after_price / before_price
          - 減資（價格跳升）：factor > 1
          - 分割（價格跳降）：factor < 1
          - 變額（視情況而定）
        
        套用邏輯驗證（以 2014 國巨減資為例）：
          before_price=22.05, after_price=48.15
          factor = 48.15/22.05 = 2.1837
          事件前日 adj_close = 22.05 × 2.1837 = 48.15 ✅ = 事件日參考價
        """
        events_list = []

        # TaiwanStockSplitPrice — 分割
        df = _fetch_finmind("TaiwanStockSplitPrice", stock_id,
                            "2000-01-01", "2026-12-31", self.token)
        if not df.empty:
            for _, row in df.iterrows():
                bp = float(row.get("before_price", 0))
                ap = float(row.get("after_price", 0))
                if bp > 0 and ap > 0:
                    events_list.append({
                        "date": row["date"],
                        "before_price": bp,
                        "after_price": ap,
                        "factor": ap / bp,
                        "event_type": "split",
                    })

        # TaiwanStockCapitalReductionReferencePrice — 減資
        df = _fetch_finmind("TaiwanStockCapitalReductionReferencePrice", stock_id,
                            "2000-01-01", "2026-12-31", self.token)
        if not df.empty:
            for _, row in df.iterrows():
                bp = float(row.get("before_price", 0))
                ap = float(row.get("after_price", 0))
                if bp > 0 and ap > 0:
                    events_list.append({
                        "date": row["date"],
                        "before_price": bp,
                        "after_price": ap,
                        "factor": ap / bp,
                        "event_type": "capital_reduction",
                    })

        # TaiwanStockParValueChange — 變更面額
        df = _fetch_finmind("TaiwanStockParValueChange", stock_id,
                            "2000-01-01", "2026-12-31", self.token)
        if not df.empty:
            for _, row in df.iterrows():
                bp = float(row.get("before_price", 0))
                ap = float(row.get("after_price", 0))
                if bp > 0 and ap > 0:
                    events_list.append({
                        "date": row["date"],
                        "before_price": bp,
                        "after_price": ap,
                        "factor": ap / bp,
                        "event_type": "par_value_change",
                    })

        if not events_list:
            return pd.DataFrame()

        events = pd.DataFrame(events_list)
        events["date"] = pd.to_datetime(events["date"])
        events = events.sort_values("date").reset_index(drop=True)
        return events

    # ──────────────────────────────────────────────
    # 2. 官方 TaiwanStockPriceAdj 驗證（逐檔動態）
    # ──────────────────────────────────────────────

    def fetch_official_adj_price(self, stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
        """抓取 TaiwanStockPriceAdj（官方還原股價表）"""
        return _fetch_finmind("TaiwanStockPriceAdj", stock_id, start_date, end_date, self.token)

    def check_official_adj_coverage(self, stock_id: str, events: pd.DataFrame) -> dict:
        """
        驗證官方 TaiwanStockPriceAdj 是否已覆蓋每個事件。
        
        對每個事件日，取 TaiwanStockPriceAdj 中事件前/後的收盤價比值：
        - 比值 ≈ 1.0 → 官方已處理 ✅
        - 比值 ≈ 事件 factor → 官方未處理 ❌
        
        Returns:
            {"use_manual": bool, ...} — 逐檔動態判定
        """
        if events.empty:
            return {"status": "no_events", "message": "無事件"}

        start = events["date"].min() - pd.Timedelta(days=10)
        end = events["date"].max() + pd.Timedelta(days=10)
        adj_df = self.fetch_official_adj_price(stock_id,
                                                start.strftime("%Y-%m-%d"),
                                                end.strftime("%Y-%m-%d"))
        if adj_df.empty:
            return {"status": "no_adj_data",
                    "message": f"{stock_id} 無 TaiwanStockPriceAdj，需手動還原",
                    "use_manual": True}

        adj_df["date"] = pd.to_datetime(adj_df["date"])
        adj_df = adj_df.sort_values("date")
        close_col = "close" if "close" in adj_df.columns else "adj_close"

        results = []
        for _, evt in events.iterrows():
            evt_date = evt["date"]
            before = adj_df[adj_df["date"] < evt_date].tail(1)
            after = adj_df[adj_df["date"] >= evt_date].head(1)
            if before.empty or after.empty:
                results.append({"event_date": evt_date.strftime("%Y-%m-%d"),
                                "event_type": evt["event_type"],
                                "conclusion": "❌ 無資料"})
                continue
            cb = float(before.iloc[0].get(close_col, np.nan))
            ca = float(after.iloc[0].get(close_col, np.nan))
            if pd.isna(cb) or pd.isna(ca) or cb <= 0:
                results.append({"event_date": evt_date.strftime("%Y-%m-%d"),
                                "event_type": evt["event_type"],
                                "conclusion": "❌ 收盤價無效"})
                continue
            adj_ratio = ca / cb
            factor = evt["factor"]
            if abs(adj_ratio - 1.0) < 0.01:
                conclusion = "✅ 官方已處理（比值≈1）"
            elif abs(adj_ratio - factor) < 0.01 and abs(adj_ratio - 1.0) > 0.01:
                conclusion = "❌ 官方未處理（比值≈事件比例）"
            else:
                conclusion = f"⚠️ 無法判定（比值={adj_ratio:.4f}, 事件={factor:.4f}）"
            results.append({"event_date": evt_date.strftime("%Y-%m-%d"),
                            "event_type": evt["event_type"], "factor": factor,
                            "adj_ratio": adj_ratio, "conclusion": conclusion})

        use_manual = any("未處理" in r.get("conclusion", "") or "無法判定" in r.get("conclusion", "")
                         or "無" in r.get("conclusion", "") for r in results)
        return {"status": "checked", "results": results, "use_manual": use_manual,
                "message": "手動還原" if use_manual else "官方已處理"}

    # ──────────────────────────────────────────────
    # 3. 核心還原邏輯
    # ──────────────────────────────────────────────

    def adjust(self, stock_id: str, df_price: pd.DataFrame) -> pd.DataFrame:
        """
        核心還原函式。
        
        還原理論：
        - 事件日 T，factor = after_price / before_price
        - T 之前的所有價格乘以 factor，讓事件日 T 前後的 adj_close 連續
        - 從最早事件迭代到最晚事件，對之前日期逐一累乘
        - 結果：最早日期被所有其後事件的 factor 連乘
        
        國巨 2327 實測因數範圍 1.00 ~ 9.47
        
        回傳的 DataFrame 新增：
        - adj_factor: 累積還原因子
        - adj_close: 還原收盤價
        - adj_volume: 還原成交量（僅對分割事件調整）
        """
        if df_price.empty:
            return df_price

        df = df_price.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        close_vals = pd.to_numeric(df["close"], errors="coerce").values.astype(np.float64)
        volume_vals = (pd.to_numeric(df["volume"], errors="coerce").values.astype(np.float64)
                       if "volume" in df.columns else None)

        events = self.fetch_split_events(stock_id)
        if events.empty:
            df["adj_factor"] = 1.0
            df["adj_close"] = close_vals
            return df

        n = len(df)
        adj_factor = np.ones(n)

        for _, evt in events.iterrows():
            mask = df["date"] < evt["date"]
            adj_factor[mask] *= evt["factor"]

        df["adj_factor"] = adj_factor
        df["adj_close"] = close_vals * adj_factor

        # 還原 open/high/low
        for col in ["open", "high", "low"]:
            if col in df.columns:
                raw = pd.to_numeric(df[col], errors="coerce").values.astype(np.float64)
                df[f"adj_{col}"] = raw * adj_factor

        # 還原成交量（用於跨期量指標如 Vol_MA_5、Volume_Ratio）
        # 分割（factor<1）：事件前股數變多，成交張數按比例放大 → ×(1/factor)
        # 減資（factor>1）：事件前股數變少，成交張數按比例縮小 → ×(1/factor)
        # 1/factor = before_price / after_price
        # 分割：1/0.25=4，分割前歷史張數×4 → 校正為分割後股數單位的等值量
        # 減資：1/2.18=0.46，減資前歷史張數×0.46 → 校正為減資後股數單位的等值量
        if volume_vals is not None:
            volume_adj_factor = np.ones(n)
            for _, evt in events.iterrows():
                mask = df["date"] < evt["date"]
                volume_adj_factor[mask] *= (1.0 / evt["factor"])
            df["adj_volume"] = volume_vals * volume_adj_factor

        return df

    # ──────────────────────────────────────────────
    # 4. 驗證
    # ──────────────────────────────────────────────

    def verify(self, stock_id: str, start_date: str, end_date: str):
        """
        完整驗證流程：
          抓取 → 檢查官方覆蓋 → 執行還原 → 印出事件日前後價格 → 繪圖
        
        輸出包含「事件日連續性驗證」：檢查第一個事件日前後的 adj_close 比值，
        理想值 = 1.0，偏差 < 1% 即通過。
        """
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm
        import os

        for fp in ["NotoSansTC-Regular.otf", "../NotoSansTC-Regular.otf"]:
            if os.path.exists(fp):
                fm.fontManager.addfont(fp)
                plt.rcParams['font.family'] = fm.FontProperties(fname=fp).get_name()
                break
        else:
            plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei']
        plt.rcParams['axes.unicode_minus'] = False

        from data.fetcher import fetch_stock_price
        print(f"📥 {stock_id} {start_date} ~ {end_date}")
        df_price = fetch_stock_price(stock_id, start_date, end_date, self.token)
        if df_price.empty:
            print("❌ 無資料"); return

        events = self.fetch_split_events(stock_id)
        print(f"\n📋 事件共 {len(events)} 筆")
        if not events.empty:
            for _, e in events.iterrows():
                print(f"   {e['date'].strftime('%Y-%m-%d')} {e['event_type']:20s} "
                      f"before={e['before_price']:.2f} after={e['after_price']:.2f} "
                      f"factor={e['factor']:.4f}")

        print("\n🔍 檢查 TaiwanStockPriceAdj...")
        chk = self.check_official_adj_coverage(stock_id, events)
        print(f"   {chk['message']}")
        if "results" in chk:
            for r in chk["results"]:
                print(f"   {r['event_date']} {r['event_type']:20s} {r['conclusion']}")

        print("\n🔄 執行還原...")
        df_adj = self.adjust(stock_id, df_price)
        print(f"   ✅ {len(df_adj)} 筆，factor {df_adj['adj_factor'].min():.4f} ~ {df_adj['adj_factor'].max():.4f}")

        # 事件日前後價表
        if not events.empty:
            print(f"\n📊 事件日前後 ±3 交易日")
            for _, evt in events.iterrows():
                ed = evt["date"]
                w = df_adj[(df_adj["date"] >= ed - pd.Timedelta(days=5)) &
                           (df_adj["date"] <= ed + pd.Timedelta(days=5))]
                print(f"\n--- {ed.strftime('%Y-%m-%d')} ({evt['event_type']}) factor={evt['factor']:.4f} ---")
                for _, r in w.iterrows():
                    mark = "← 事件日" if r["date"] == ed else ""
                    print(f"  {r['date'].strftime('%Y-%m-%d')} "
                          f"close={r['close']:>8.2f} adj={r['adj_close']:>8.2f} "
                          f"factor={r['adj_factor']:.4f} {mark}")

            # 連續性驗證
            first = events.iloc[0]
            ed = first["date"]
            b = df_adj[df_adj["date"] < ed].tail(1)["adj_close"].values
            a = df_adj[df_adj["date"] >= ed].head(1)["adj_close"].values
            if len(b) > 0 and len(a) > 0 and a[0] > 0:
                r = b[0] / a[0]
                print(f"\n🔬 連續性驗證（{ed.strftime('%Y-%m-%d')}）："
                      f"事件前 adj={b[0]:.2f} → 事件後 adj={a[0]:.2f} "
                      f"比值={r:.4f}（理想=1.0000）{'✅' if abs(r-1.0)<0.01 else '⚠️'}")

        # 繪圖
        fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
        axes[0].plot(df_adj["date"], df_adj["close"], label="原始 close", color="red", lw=1, alpha=0.7)
        axes[0].plot(df_adj["date"], df_adj["adj_close"], label="還原 adj_close", color="blue", lw=1.5)
        for _, e in events.iterrows():
            axes[0].axvline(x=e["date"], color="gray", ls="--", alpha=0.5)
        axes[0].set_ylabel("股價")
        axes[0].set_title(f"{stock_id} 還原前後比較")
        axes[0].legend(); axes[0].grid(True, alpha=0.3)

        axes[1].plot(df_adj["date"], df_adj["adj_factor"], label="累積還原因子", color="green")
        axes[1].set_ylabel("因子"); axes[1].set_xlabel("日期")
        axes[1].legend(); axes[1].grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(f"{stock_id}_adj_comparison.png", dpi=150)
        print(f"\n🖼️ 比較圖：{stock_id}_adj_comparison.png")
        plt.show()