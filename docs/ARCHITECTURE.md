# 系統架構說明

## 目錄結構

```
taiwan-stock-analyzer-v3/
│
├── app.py                         # Streamlit 前端主入口
├── requirements.txt               # Python 依賴
├── Dockerfile                     # 容器化部署
├── refresh_and_restart.bat        # 一鍵清除快取 + 重啟
│
├── data/                          # 📥 資料層
│   ├── fetcher.py                 #   FinMind API 呼叫（12 種資料）
│   ├── processor.py               #   母表建構、對齊、衍生欄位
│   └── price_adjuster.py          #   還原股價（減資/分割）
│
├── stock/                         # 📊 指標層
│   ├── metrics.py                 #   技術指標 + 財務指標
│   └── screener.py                #   選股篩選（預留）
│
├── core/                          # 🎯 規則引擎層
│   ├── scoring_config.py          #   評分權重與門檻設定
│   ├── scorer.py                  #   四風格打分 0-100
│   ├── backtest.py                #   Walk-forward 回測
│   ├── trade_manager.py           #   買賣建議（雙軌四維投票）
│   └── advisor.py                 #   基本建議
│
├── ai/                            # 🤖 AI 層
│   ├── analyzer.py                #   DeepSeek API 呼叫
│   └── prompts.py                 #   System Prompt
│
├── news/                          # 📰 新聞情緒模組
│   ├── fetcher.py
│   ├── analyzer.py
│   └── database.py
│
├── utils/                         # 🔧 共用工具
│   └── helpers.py
│
├── tests/                         # 🧪 單元測試
├── docs/                          # 📚 文件
├── bug/                           # 🐛 除錯工具
└── data/debug/                    # 回測 CSV 輸出
```

---

## 三層分析架構

```
┌─────────────────────────────────────────────────────────────┐
│  第一層：純數據打分（core/scorer.py）                       │
│  ├── 輸入：母表（已對齊之財務/籌碼/技術指標）               │
│  ├── 邏輯：根據四種風格權重，計算 0-100 分                  │
│  ├── 輸出：短線/波段/價值/定存 分數                         │
│  └── 特點：純 Python，不依賴 AI                             │
└───────────────────────┬─────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  第二層：交易規則（core/trade_manager.py）                   │
│  ├── 輸入：四種風格分數                                     │
│  ├── 邏輯：型態認領 + 四維度投票 + 飛刀濾網 + 鐵盾          │
│  │         雙軌建議價（積極型 + 保守型）                     │
│  └── 特點：純 Python，可解釋性高                            │
└───────────────────────┬─────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  第三層：AI 解說（ai/analyzer.py）                           │
│  ├── 輸入：指標數據 + 打分結果 + 交易建議                    │
│  ├── 邏輯：DeepSeek API                                     │
│  └── 特點：可選，不影響評分與回測                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 數據管線

### 對齊規則

所有低頻資料以「公告日」`merge_asof(direction='backward')` 對齊到日頻股價主軸。

| 資料 | 原始頻率 | 對齊欄位 | 對齊方式 |
|:---|:---:|:---:|:---:|
| 股價 | 日 | date | 主軸 |
| 月營收 | 月 | create_time（公告日） | merge_asof backward |
| 損益表 | 季 | date（公告日） | merge_asof backward |
| 資產負債表 | 季 | date（公告日） | merge_asof backward |
| 現金流量表 | 季 | date（公告日） | merge_asof backward |
| 股利 | 不定期 | AnnouncementDate | merge_asof backward |
| 本益比 | 日 | date | merge_asof backward |
| 法人/融資券/借券 | 日 | date | merge_asof backward |

### 還原股價

`data/price_adjuster.py` 使用 FinMind 官方事件資料：
- `TaiwanStockSplitPrice` — 分割
- `TaiwanStockCapitalReductionReferencePrice` — 減資
- `TaiwanStockParValueChange` — 變更面額

計算累積還原因子，產出 `adj_close`，讓技術指標（MA、MACD、RSI）不被價格斷層破壞。

---

## 快取機制

系統有三層快取，避免重複撈取 FinMind：

| 層級 | 儲存位置 | 清除方式 |
|:---|:---|:---|
| Session | `st.session_state` | 側邊欄「強制刷新資料」按鈕 |
| SQLite | `news_sentiment.db` (analysis_cache 表) | `delete_analysis_cache('all')` |
| Parquet | `data/cache/*.parquet` | 手動刪除檔案 |