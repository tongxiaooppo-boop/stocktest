# 台股AI個人化決策系統 v1.7

> **版本**: v1.7  
> **最後更新**: 2026-07-14  
> **核心設計文件**: `docs/DESIGN_v1.0.md`  
> **快速部署**: 看下方 [Render 中文部署教學](#render-中文部署教學github--render)

> ⚠️ **此程式為個人研究，不構成任何投資建議。**  
> **投資警語**：投資有風險，買賣股票前請自行評估，盈虧自負。本系統的評分與建議僅為輔助參考，不保證獲利。

## 系統概述

從零重寫一套「單一專案、模組化架構」的台股分析系統，結合：
- **四種投資風格**：短線 / 波段 / 價值 / 定存
- **使用者持股成本與部位**：個人化決策
- **三層分析架構**：純數據打分 + 規則建議 + AI 解說
- **歷史回測**：walk-forward 評分，避免 look-ahead bias
- **短線面 + 中長線面**：圖表與數據表格
- **📰 新聞輿情模組**：Yahoo Finance RSS + Google News RSS 雙來源，SnowNLP 情緒分析，SQLite 累積歷史統計
- **🔫 50/50 雙彈夾分批建倉**：下跌加碼 / 順勢突破加碼，狀態機追蹤，已實現/未實現損益
- **🤖 AI 回測點位解說**：順著時間軸的故事性解說，含雙彈夾點評

### 使用情境

| 情境 | 輸入 | 輸出 |
|:---|:---|:---|
| **有持股** | 股票代號 + 均價 + 股數 | 留倉/加碼/賣出/減碼（四維度投票 + 鐵盾防線） |
| **沒持股** | 股票代號 | 型態認領（波段/短線/價值/定存）或「不建議」+ 飛刀濾網 |

### 資料來源

| 來源 | 用途 |
|:---|:---|
| **FinMind API** | 所有台股數據（股價、財報、籌碼、股利等） |
| **DeepSeek API** | AI 解說分析（非必要，不影響評分與回測） |

---

## 安裝與執行（新電腦設定）

### 第一步：安裝 VS Code + Python

1. **VS Code**：https://code.visualstudio.com/ 下載安裝
2. **Python**：打開 Microsoft Store，搜尋 `Python 3.12` 安裝（或到 https://www.python.org/downloads/ 下載）
3. 打開 VS Code，左邊 Extensions（Ctrl+Shift+X）→ 搜尋 `Python`，安裝微軟官方的那個

### 第二步：複製專案

把 `taiwan-stock-analyzer-v3` 資料夾用隨身碟或網路複製到新電腦

### 第三步：安裝套件

1. VS Code 中 **File → Open Folder** → 選這個專案資料夾
2. **Terminal → New Terminal**（快捷鍵 Ctrl+`）
3. 在終端機輸入：
   ```
   pip install -r requirements.txt
   ```
   （如果 pip 太舊，先跑 `python -m pip install --upgrade pip`）

### 第四步：申請 API Token（免費）

本系統需要 **FinMind API Token**（必填）和 **DeepSeek API Key**（選填）。

#### 🔑 FinMind API Token（必填）

1. 打開 https://finmindtrade.com
2. 點右上角 **Login / Register** → 用 Email 註冊
3. 登入後進 **Dashboard** → **API Token**
4. 複製那串 Token（長這樣：`eyJ0eXAiOiJKV1Qi...`）

#### 🤖 DeepSeek API Key（選填，不影響評分與回測）

1. 打開 https://platform.deepseek.com 註冊
2. 登入後點左邊 **API Keys** → **Create API key**
3. 取名（例如 `stock-analyzer`）→ 複製 Key

> 沒 DeepSeek API Key 也能正常分析，只是沒有 AI 解說那一塊。

### 第五步：啟動

終端機輸入：
```
streamlit run app.py
```
瀏覽器會自動打開 http://localhost:8501

> **第一步使用**：在側邊欄輸入 FinMind Token 與股票代號（例如 2330），點「🔍 開始分析」

---

## 目錄結構

```
taiwan-stock-analyzer-v3/
├── app.py                    # Streamlit 前端（瀑布流 6 階段顯示）
├── data/
│   ├── fetcher.py            # 12 種 FinMind API 呼叫
│   └── processor.py          # 母表建構 + 衍生欄位
├── stock/
│   └── metrics.py            # 技術指標 + 財務指標
├── core/
│   ├── scoring_config.py     # 評分權重與門檻
│   ├── scorer.py             # 四風格×6子項打分 + walk-forward 回測
│   ├── backtest.py           # 回測分析（五種策略 + 50/50 雙彈夾）
│   ├── trade_manager.py      # 買賣建議（型態認領 + 四維度投票 + 飛刀濾網 + 鐵盾 + 建議買價區間）
│   └── advisor.py            # 基本建議（買/賣/持有）
├── ai/
│   ├── analyzer.py           # DeepSeek API 呼叫（含回測解說）
│   └── prompts.py            # AI 提示詞（含雙彈夾解說規則）
├── news/
│   ├── config.py             # RSS URL、資料庫路徑設定
│   ├── fetcher.py            # Yahoo Finance + Google News RSS 雙來源
│   ├── analyzer.py           # SnowNLP 中文情緒分析
│   └── database.py           # SQLite 儲存 + 歷史統計 + 分析快取
├── utils/
│   └── helpers.py            # 共用工具
├── bug/                      # Debug CSV 匯出目錄
├── data/
│   ├── debug/                # 回測 CSV 輸出目錄
│   └── cache/                # 母表 Parquet 快取（F5 保留）
│── news_sentiment.db         # 新聞資料庫（自動建立，不上 git）
```

---

## 核心架構

### 三層分析

```
第一層：純數據打分（scorer.py）     → 四維度×6子項 0-100 分 + modifiers
第二層：規則建議（trade_manager.py） → 未持有：型態認領 + 飛刀濾網
                                      已持有：四維度投票 + 一票通關 + 鐵盾
第三層：AI 解說（analyzer.py）      → DeepSeek API 解說評分結果（可選）
```

### 評分權重總覽

| 風格 | 子項 | 權重 | 備註 |
|:---|:---|:---:|:---|
| **短線** | 趨勢結構 | 20% | 均線排列(60%)+站上均線數(40%) |
| | 動能 | 20% | RSI(40%)+MACD(35%)+突破前高(25%) |
| | 量能 | 20% | Volume Ratio(60%)+爆量幅度(40%) |
| | 法人 | 15% | 5日法人(35%)+10日法人(25%)+外資(25%)+投信(15%) |
| | 籌碼 | 15% | 融資(40%)+融券(30%)+借券(30%) [反向] |
| | 風險 | 10% | 乖離率(40%)+ATR(30%)+RSI過熱(30%) [反向] |
| **波段** | 營收動能 | 25% | 營收年增率+趨勢方向 |
| | 中期趨勢 | 20% | MA排列+股價位置 |
| | 法人趨勢 | 20% | 法人買賣超趨勢 |
| | 獲利成長 | 15% | EPS年增率+毛利率趨勢 |
| | 估值 | 10% | PE/PB百分位 [反向] |
| | 題材動能 | 10% | 營收驚奇+股價動能 |
| **價值** | 估值安全 | 15% | 原25%，v1.0調降，改配給成長能力 |
| | 獲利品質 | 20% | ROE+毛利率穩定度 |
| | 成長能力 | 30% | 原20%，吸收估值釋出權重 |
| | 財務安全 | 15% | [反向] 金融業跳過 |
| | 現金流品質 | 10% | 金融業跳過 |
| | 股東回報 | 10% | 盈餘分配率+庫藏股 |
| **定存** | 配息紀錄 | 25% | 連續配息年數+殖利率 |
| | 配息品質 | 20% | 盈餘分配率+股息穩定性 |
| | 現金流 | 20% | 自由現金流+營業現金流 |
| | 財務安全 | 15% | [反向] 金融業跳過 |
| | 獲利穩定 | 10% | [反向] EPS變異係數 |
| | 長期成長 | 10% | 長期營收+EPS成長率 |

### RSI 過熱扣分（動態門檻）

```
一般情況：RSI > 88 → 扣 10 分
多頭排列（close > 5MA > 10MA > 20MA）：RSI > 95 → 扣 10 分
```
- 多頭排列時放寬至 95 才扣分，減少強勢股誤殺
- RSI > 95 仍會扣分，保留風控底線

### 金融業防錯模組

金融股在以下評分項目中直接給予滿分 100：
- 價值風格：`financial_safety`（跳過負債比評分）
- 價值風格：`cash_flow_quality`（跳過營業現金流評分）
- 定存風格：`financial_safety`（跳過負債比評分）
- Risk Modifier：跳過負債過高與營業現金流的扣分

---

## 回測功能

### 雙策略同時執行

| 策略 | 買入門檻 | 賣出門檻 | 說明 |
|:---|:---:|:---:|:---|
| **積極** | ≥ 60 | < 40 | 較敏感，交易次數較多 |
| **保守** | ≥ 70 | < 50 | 較嚴格，交易次數較少 |

> 按「▶️ 執行回測」同時跑兩種策略，可隨時切換查看。

### 六種策略

| 策略 | 買入條件 | 賣出條件 |
|:---|:---|:---|
| 短線 | 分數 ≥ 買入門檻 | 分數 < 賣出門檻 |
| 波段 | 同上 | 同上 |
| 價值 | 同上 | 同上 |
| 定存 | 同上 | 同上 |
| 綜合 | ≥2 種風格同時通過 | ≥2 種風格跌破門檻 |
| **🔫 雙彈夾** | 第一發+第二發加碼 | 全數清倉 |

### 50/50 雙彈夾分批建倉

**啟用方式**：展開回測參數設定 → 勾選「🔫 啟用 50/50 雙彈夾分批建倉」

**核心邏輯**：
- **state=0（空手）**：分數 ≥ 買入門檻 → 第一發進場（50%資金）
- **state=1（一發）**：分數跌破門檻？全賣。價格跌 X%？第二發加碼
- **state=2（滿倉）**：分數跌破門檻？全賣。

**兩種加碼模式**：
| 模式 | 觸發條件 | 適用場景 |
|:---|:---|:---|
| 📉 下跌加碼 | 股價從第一發跌 X%（預設-8%） | 價值/波段，越跌越買 |
| 📈 順勢突破 | 分數創近期新高（比分數門檻高10分） | 短線/波段，強勢加碼 |

**績效顯示**：
```
🔫 雙彈夾
  交易: 2筆
  ✔️ 已實現: +5.98%
  ⏳ 持有中: +3.20%
```

### AI 回測點位解說

按「🤖 解說保守/積極策略」按鈕，AI 會：
1. 順著時間軸一筆一筆解說進出點位
2. 點評哪筆是漂亮起漲點、哪筆被雙巴
3. 若有啟用雙彈夾，會點評加碼時機是否恰當

### 已實現/未實現損益

每個策略下方顯示：
- **✔️ 已實現**：所有已出清交易的報酬率總和
- **⏳ 持有中**：最後一筆持有中的報酬率

### 輸出

- 瀑布流底部：六欄 KPI 摘要卡
- Tab3 內：分數走勢圖 + 價格訊號圖 + 交易明細表 + AI 解說
- CSV 下載：積極/保守/雙彈夾 專屬 CSV

---

## 啟動方式

```bash
cd d:\TW Stock AI\taiwan-stock-analyzer-v3
streamlit run app.py
```

開啟 http://localhost:8501

## 測試方式

```bash
# 完整管線測試
python test_full_pipeline.py

# 從已匯出 CSV 測試評分
cd bug
python test_debug_from_csv.py --file xxx_debug.csv
```

---

## 開發路線圖（Roadmap）

| 階段 | 項目 | 說明 | 優先級 |
|:---|:---|:---|:---:|
| **1** | **SQLite 持倉資料庫** | 儲存自選股、持股成本、分析歷史，重整頁面資料不消失 | 🔴 最高 |
| **2** | **多檔監控儀表板** | 一頁看所有自選股的評分總覽、觸發買訊警示 | 🟠 中 |
| **3** | **模擬交易盤** | 基於 trade_advice 訊號自動執行模擬單，紀錄交易歷史與損益 | 🟢 低 |

---

## Render 中文部署教學（GitHub → Render）

### 📦 第一步：上傳程式碼到 GitHub

```bash
git init
git add .
git commit -m "v1.7 初始上傳"
git remote add origin https://github.com/YOUR_USER/tw-stock-analyzer.git
git push -u origin main
```

### 🚀 第二步：部署到 Render

1. 打開 https://dashboard.render.com/register → 用 GitHub 登入
2. 點 **New +** → **Web Service** → 選你的倉庫
3. 設定：

| 欄位 | 填法 |
|:---|:---|
| **Runtime** | **Docker** |
| **Instance Type** | **Free** |

4. 環境變數：

| Key | Value |
|:---|:---|
| `FINMIND_TOKEN` | 你的 Token（必填） |
| `DEEPSEEK_API_KEY` | 你的 Key（選填） |

> ⚠️ Render 免費方案閒置 15 分鐘會休眠，訪客觸發時約 30~60 秒啟動。

### ❓ 常見問題

#### Q：如何更新程式碼？
```bash
git add .
git commit -m "修改了 xxx"
git push
```
Render 會自動部署。

#### Q：如何看 Log？
Render Dashboard → 點 Web Service → **Logs** 分頁。

---

## Docker 自行架設

```bash
docker build -t tw-stock-analyzer .
docker run -p 8501:8501 -e FINMIND_TOKEN=你的Token tw-stock-analyzer
```

開啟 http://localhost:8501

---

## 變更記錄

### v1.7 (2026-07-14)

| 新增功能 | 說明 |
|:---|:---|
| **🔫 50/50 雙彈夾分批建倉** | 下跌加碼/順勢突破加碼，狀態機(state=0/1/2)追蹤 |
| **🤖 AI 回測點位解說** | 順時間軸故事性解說，含雙彈夾點評 |
| **✔️ 已實現/⏳ 持有中損益** | 每策略獨立計算，四維+綜合+雙彈夾共6欄 |
| **📥 雙彈夾 CSV 下載** | 含第一發/第二發進場價、均價、報酬率 |
| | |
| **改進** | |
| Tab 切換記憶 | 改用 `columns` 按鈕 + session_state，rerun 不跳回 |
| 切換股票清除殘留 | 自動清除舊股票的回測/AI解說資料 |
| 重複表格移除 | 回測 AI 解說不再重複顯示圖表區已有的表格 |
| run_backtest 簽名更新 | 改用 local import 避免 bytecode 快取問題 |
| 新聞 SQLite 持久化 | 分析快取 + 新聞資料庫 F5 不消失 |

### v1.6 (2026-07-14) — 圖表增強 + 檔案整理
- 短線面圖表新增股價疊加（法人買賣超圖 + 融資券變化圖）
- 波段圖表縮減至評分時間跨度
- 修復回測策略切換按鈕 bug

### v1.5 (2026-07-14) — 回測增強版
- 修復積極/保守 threshold 錯置
- 綜合策略買入條件改為 ≥2 種風格
- signal_history 新增建議價位欄位

### v1.4 — v0.1
請參閱 `docs/README_v1.0.md`

---

> ⚠️ **免責聲明**：本系統為個人研究專案，僅供學習與參考用途。所有分析結果與建議均不構成投資要約或建議。投資人應獨立判斷，審慎評估風險，並對自己的投資決策負責。股市投資可能導致本金損失，過去績效不代表未來表現。**本程式不保證獲利，使用前請詳閱相關風險說明。**