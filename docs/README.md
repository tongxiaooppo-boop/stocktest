# 台股AI個人化決策系統 v2.2

> **版本**: v2.2  
> **最後更新**: 2026-07-16  

> ⚠️ **此程式為個人研究，不構成任何投資建議。**  
> **投資警語**：投資有風險，買賣股票前請自行評估，盈虧自負。本系統的評分與建議僅為輔助參考，不保證獲利。

---

## 📋 文件索引

本專案的說明文件已拆分為以下五份，依角色取用：

| 文件 | 適合對象 | 內容 |
|:---|:---|:---|
| **`README.md`**（本文件） | 所有人 | 系統簡介、快速安裝、執行方式 |
| **`docs/SETUP.md`** | 新手、部署者 | 申請 API Key 教學、本地環境配置、Render 雲端部署 |
| **`docs/ARCHITECTURE.md`** | 開發者、貢獻者 | 目錄結構、三層分析架構、數據管線對齊規則 |
| **`docs/SCORING.md`** | 策略調校者 | 四種風格評分細則、24 子項權重與門檻、Modifier 疊加規則 |
| **`docs/CHANGELOG.md`** | 維護者 | 改版歷程、Bug 修復記錄、Roadmap |

---

## 🚀 快速安裝

```bash
# 1. 安裝依賴
pip install -r requirements.txt

# 2. 啟動系統
streamlit run app.py
```

> 第一次使用前，請先申請 FinMind API Token（見 `docs/SETUP.md`）。

---

## 🧹 大改版後快取清理

改完程式碼後若發現結果沒變，通常是快取殘留，執行：

```bash
# 方法一：點兩下 refresh_and_restart.bat（Windows）
# 方法二：手動刪除快取再重啟
del data\cache\*.parquet
python -c "from news.database import delete_analysis_cache; delete_analysis_cache('all')"
streamlit run app.py
```

---

## 🏗️ 系統架構一瞥

```
使用者輸入（股票代號 + 庫存）
        │
        ▼
┌──────────────────────────┐
│ data/fetcher.py          │  ← 從 FinMind 撈取 12 種資料
│ data/processor.py        │  ← 對齊頻率、計算衍生欄位
│ data/price_adjuster.py  │  ← 還原減資/分割造成的股價斷層
└──────────┬───────────────┘
           ▼
┌──────────────────────────┐
│ core/scorer.py           │  ← 四風格打分 0-100 分
│ core/trade_manager.py    │  ← 買賣建議（雙軌四維投票）
│ core/backtest.py         │  ← Walk-forward 回測
└──────────┬───────────────┘
           ▼
┌──────────────────────────┐
│ ai/analyzer.py           │  ← DeepSeek AI 解說（選用）
│ app.py                   │  ← Streamlit 前端瀑布流
└──────────────────────────┘
```

詳細架構說明與目錄結構請見 **`docs/ARCHITECTURE.md`**。

---

## 📦 專案模組一覽

| 模組 | 檔案 | 功能 |
|:---|:---|:---|
| 資料層 | `data/fetcher.py` | 12 個 FinMind API 呼叫 |
| | `data/processor.py` | 母表建構 + 衍生欄位計算 |
| | `data/price_adjuster.py` | 還原股價計算（減資/分割） |
| 指標層 | `stock/metrics.py` | 技術 + 財務指標計算 |
| 規則引擎 | `core/scorer.py` | 四風格打分 |
| | `core/trade_manager.py` | 買賣建議（雙軌四維投票） |
| | `core/backtest.py` | Walk-forward 回測 |
| AI 層 | `ai/analyzer.py` | DeepSeek API 呼叫 |
| 前端 | `app.py` | Streamlit 瀑布流 UI |

---

> ⚠️ **免責聲明**：本系統為個人研究專案，僅供學習與參考用途。所有分析結果與建議均不構成投資要約或建議。投資人應獨立判斷，審慎評估風險，並對自己的投資決策負責。股市投資可能導致本金損失，過去績效不代表未來表現。**本程式不保證獲利，使用前請詳閱相關風險說明。**