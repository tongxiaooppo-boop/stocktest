# 台股AI個人化決策系統 v5.1.1

> **版本**: v5.1.1 (回測增強版)  
> **最後更新**: 2026-07-13 12:55  
> **核心設計文件**: `docs/DESIGN_v3.1.md`

## 系統概述

從零重寫一套「單一專案、模組化架構」的台股分析系統，結合：
- **四種投資風格**：短線 / 波段 / 價值 / 定存
- **使用者持股成本與部位**：個人化決策
- **三層分析架構**：純數據打分 + 規則建議 + AI 解說
- **歷史回測**：walk-forward 評分，避免 look-ahead bias
- **短線面 + 中長線面**：圖表與數據表格

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

### 第四步：註冊 API Token（免費）

到 https://finmindtrade.com 註冊 → 取得 FinMind API Token

### 第五步：啟動

終端機輸入：
```
streamlit run app.py
```
瀏覽器會自動打開 http://localhost:8501

> **DeepSeek API Key** 是選項，不輸入也能分析，只是沒有 AI 解說

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
│   ├── backtest.py           # 回測分析模組（五種策略獨立追蹤）
│   ├── trade_manager.py      # 買賣建議（型態認領 + 四維度投票 + 飛刀濾網 + 鐵盾）
│   └── advisor.py            # 基本建議（買/賣/持有）
├── ai/
│   ├── analyzer.py           # DeepSeek API 呼叫
│   └── prompts.py            # AI 提示詞
├── utils/
│   └── helpers.py            # 共用工具
├── bug/                      # Debug CSV 匯出目錄
└── data/debug/               # 回測 CSV 輸出目錄
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

### v5.1 評分權重總覽

| 風格 | 子項 | 權重 | 備註 |
|:---|:---|:---:|:---|
| **短線** | trend_structure | 20% | 均線排列(60%)+站上均線數(40%) |
| | momentum | 20% | RSI(40%)+MACD(35%)+突破前高(25%) |
| | volume | 20% | Volume Ratio(60%)+爆量幅度(40%) |
| | institutional | 15% | 5日法人(35%)+10日法人(25%)+外資(25%)+投信(15%) |
| | chip | 15% | 融資(40%)+融券(30%)+借券(30%) [反向] |
| | risk | 10% | 乖離率(40%)+ATR(30%)+RSI過熱(30%) [反向] |
| **波段** | revenue_momentum | 25% | |
| | mid_trend | 20% | |
| | institutional_trend | 20% | |
| | earnings_growth | 15% | |
| | valuation | 10% | PE/PB Percentile [反向] |
| | catalyst | 10% | |
| **價值** | valuation_safety | **15%** | 原25%，v5.1調降，改配給成長能力 |
| | profit_quality | 20% | |
| | growth_ability | **30%** | 原20%，吸收估值釋出權重 |
| | financial_safety | 15% | [反向] 金融業跳過 |
| | cash_flow_quality | 10% | 金融業跳過 |
| | shareholder_return | 10% | |
| **定存** | dividend_record | 25% | |
| | dividend_quality | 20% | |
| | cash_flow | 20% | |
| | financial_safety | 15% | [反向] 金融業跳過 |
| | profit_stability | 10% | [反向] |
| | long_term_growth | 10% | |

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

### 未持有決策邏輯（5 級優先）

| 優先級 | 條件 | 結果 |
|:---|:---|:---|
| 1 | 全風格 < 50 | 不建議 |
| 2 | 波段 > 70 | 買進（MA_20±2%） |
| 3 | 短線 > 70 且波段 < 70 | 買進（5MA，破20MA停損） |
| 4-A | 價值/定存 > 70，短線站5MA | 買進（現價） |
| **4-B** | **價值/定存 > 70 + 短線<50且破5MA** | **⭐ 飛刀濾網：觀望** |
| 5 | 50~70 | 觀望 |

### 已持有決策邏輯（四維度投票）

**投票規則：**

| 維度 | 贊成條件 | 例外（一票通關） |
|:---|:---|:---|
| 短線 | close>MA_5 且短線≥50 | — |
| 波段 | close>MA_20 且波段≥55 | — |
| 價值 | PE百分位<70 且價值≥50 | **⭐ 價值≥70 直接贊成**、**⭐ PE<12 直接贊成** |
| 定存 | 定存≥50 | **⭐ 不看殖利率** |

**決策樹：**

| 票數 | 條件 | 結果 |
|:---|:---|:---|
| 4票 | + 波段 > 65 | 加碼 |
| 3票 | — | 持有（附 MA_20 補槍參考價） |
| 2票 | + 法人連3轉負 | 減碼 |
| 2票 | 法人未轉負 | 持有觀望（附 MA_20 參考價） |
| 1/0票 | **⭐ 鐵盾啟動** | **持有觀望（基本面鐵盾覆蓋）** |
| 1票 | 鐵盾未啟動 | 減碼 |
| 0票 | 鐵盾未啟動 | 賣出 |

**鐵盾條件：** 價值>70 或 定存>70，且虧損 ≤ 5%

---

## 回測功能

### 預設參數

| 參數 | 預設值 | 說明 |
|:---|:---:|:---|
| 輸出頻率 | **每日 (D)** | 每交易日評分一次，可改每週(W)或每月(M) |
| 買入門檻 | **60** | 分數 ≥ 60 觸發買入訊號（原 70，v5.1.1 調降提高交易敏感度） |
| 賣出門檻 | **40** | 分數 < 40 觸發賣出訊號（原 50，配合買入門檻同步調降） |

### 操作流程

1. 完成分析後點擊側邊欄「📊 回測分析」按鈕
2. 切換到圖表區第 3 個 Tab「📊 回測分析」
3. 展開「⚙️ 回測參數設定」調整參數 → 按「▶️ 執行回測」
4. 查看結果：分數走勢圖、價格訊號圖、五種策略績效總覽、交易明細表
5. 修改任一參數後可再次按「▶️ 執行回測」重新運算（無需鎖定）

### 五種策略

| 策略 | 買入條件 | 賣出條件 |
|:---|:---|:---|
| 短線 | 分數 ≥ 買入門檻（預設 **60**） | 分數 < 賣出門檻（預設 **40**） |
| 波段 | 同上 | 同上 |
| 價值 | 同上 | 同上 |
| 定存 | 同上 | 同上 |
| **綜合** | **任一風格觸發買入** | **≥2 種風格觸發賣出** |

### 輸出

- 瀑布流底部：五欄 KPI 摘要卡
- Tab3 內：分數走勢圖 + 價格訊號圖 + 交易明細表
- CSV 除錯：自動存至 `data/debug/backtest_{stock_id}_{timestamp}.csv`

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

## v5.1.1 變更記錄 (2026-07-13)

| 檔案 | 變更 |
|:---|:---|
| `app.py` | 回測輸出頻率預設改為「每日」(D)；買入門檻預設改為 60、賣出門檻預設改為 40 |
| `app.py` | 修復修改邊界後無法重新執行回測的問題（移除 _bt_trigger 鎖定機制） |
| `core/backtest.py` | 總報酬率改為已出清交易平均，持有中策略顯示未實現損益 |
| `app.py` | 新增頁面頂部與底部免責聲明、評分解讀提示、修復價格圖空白問題 |
| `README.md` | 更新預設參數說明與操作流程、新增新電腦安裝教學 |

## v5.1 變更記錄 (2026-07-11)

| 檔案 | 變更 |
|:---|:---|
| `core/scorer.py` | 回測引擎(get_historical_scores)、金融業防錯(is_finance)、權重調整(v5.1)、動態RSI門檻 |
| `core/backtest.py` | **新檔案** - 五種策略回測(TradeRecord/BacktestResult/run_backtest) |
| `core/scoring_config.py` | VALUE_WEIGHTS 估值25%→15%, 成長20%→30% |
| `app.py` | 回測Tab + waterfall_6摘要 + Industry欄位merge + 快取邏輯修復 |