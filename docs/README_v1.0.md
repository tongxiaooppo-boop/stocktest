# 台股AI個人化決策系統 v1.0

> **版本**: v1.0  
> **最後更新**: 2026-07-13  
> **核心設計文件**: `docs/DESIGN_v1.0.md`

> ⚠️ **此程式為個人研究，不構成任何投資建議。**  
> **投資警語**：投資有風險，買賣股票前請自行評估，盈虧自負。本系統的評分與建議僅為輔助參考，不保證獲利。

---

## 📋 目錄

1. [系統概述](#一系統概述)
2. [目錄結構](#二目錄結構)
3. [三層分析架構](#三三層分析架構)
4. [數據管線與母表對齊](#四數據管線與母表對齊)
5. [四種投資風格評分](#五四種投資風格評分)
6. [前端畫面規劃（瀑布流 6 階段）](#六前端畫面規劃瀑布流-6-階段)
7. [完成進度](#七完成進度)
8. [改版歷程](#八改版歷程)
9. [待完成項目（Roadmap）](#九待完成專案roadmap)
10. [Bug 修復記錄](#十bug-修復記錄)
11. [部署方式](#十一部署方式)
12. [測試方式](#十二測試方式)

---

## 一、系統概述

### 1.1 核心目標

從零重寫一套「單一專案、模組化架構、可雲端部署」的台股分析系統，結合：
- **四種投資風格**：短線 / 波段 / 價值 / 定存
- **使用者持股成本與部位**：個人化決策
- **三層分析架構**：純數據打分 + 規則建議 + AI 決策
- **短線面 + 中長線面**：圖表與數據表格

### 1.2 使用情境

| 情境 | 輸入 | 輸出 |
|:---|:---|:---|
| **有持股** | 股票代號 + 均價 + 股數 | 留倉/加碼/賣出/部分賣出（各附理由，標示主要建議） |
| **沒持股** | 股票代號 | 適合維度（短/波/價/定存）或「不建議」+ 理由 |

### 1.3 資料來源

| 來源 | 用途 | 備註 |
|:---|:---|:---|
| **FinMind API** | 所有台股數據（股價、財報、籌碼、股利等） | 免費申請，每小時約可查 20 檔股票 |
| **DeepSeek API** | AI 決策分析 | 需申請 API Key |

### 1.4 資料撈取時間跨度（v1.0 調整後）

| 資料類型 | FinMind 資料集 | 撈取範圍 | 說明 |
|:---|:---|:---:|:---|
| 股價 | TaiwanStockPrice | **近 3 年** | 確保 YoY 趨勢計算有足夠歷史 |
| 大盤指數 | TaiwanStockPrice (TAIEX) | **近 3 年** | 同股價區間 |
| 股票資訊 | TaiwanStockInfo | 即時 | 單筆查詢，無日期範圍 |
| 月營收 | TaiwanStockMonthRevenue | **近 10 年** | 固定撈取 10 年 |
| 損益表 | TaiwanStockFinancialStatements | **近 10 年** | 固定撈取 10 年 |
| 資產負債表 | TaiwanStockBalanceSheet | **近 10 年** | 同上 |
| 現金流量表 | TaiwanStockCashFlowsStatement | **近 10 年** | 同上 |
| 股利 | TaiwanStockDividend | **近 10 年** | 固定撈取 10 年 |
| 本益比歷史 | TaiwanStockPER | **近 1 年** | 同股價區間 |
| 三大法人 | TaiwanStockInstitutionalInvestorsBuySell | **近 1 年** | 籌碼面不需太長歷史 |
| 融資券 | TaiwanStockMarginPurchaseShortSale | **近 1 年** | 同上 |
| 借券 | TaiwanDailyShortSaleBalances | **近 1 年** | 同上 |

> **設計原則**：股價與籌碼面（日頻資料）固定近 1 年；基本面（月營收、財報三表、股利）固定撈取近 10 年，確保長期指標（TTM_EPS、PE/PB_Percentile、配息連續性、Data_Years_Available）有足夠的歷史資料計算。

---

## 二、目錄結構（含功能說明）

```
taiwan-stock-analyzer-v3/          # 專案根目錄
│
├── app.py                         # 【主入口】Streamlit 前端，負責 UI 渲染、瀑布流顯示、呼叫各模組
├── requirements.txt               # Python 依賴套件清單（streamlit, pandas, matplotlib 等）
├── Dockerfile                     # 容器化部署設定（可選，用於 Render 雲端部署）
├── .env.example                   # 環境變數範例（FINMIND_TOKEN, DEEPSEEK_API_KEY）
├── .gitignore                     # Git 忽略規則（排除 __pycache__、.env 等）
│
├── data/                          # 📥 資料層：FinMind API 撈取 + 資料清洗對齊
│   ├── __init__.py                #   模組初始化
│   ├── fetcher.py                 #   FinMind API 呼叫（12 種資料：股價/營收/財報/籌碼/股利...）
│   └── processor.py               #   母表建構：9 種資料 merge_asof 頻率對齊、衍生欄位計算
│
├── stock/                         # 📊 指標層：技術面 + 基本面指標計算
│   ├── __init__.py                #   模組初始化
│   ├── metrics.py                 #   技術指標（RSI/MA/量比/法人累計）+ 財務指標（ROE/毛利率/FCF/配息率）
│   └── screener.py                #   選股篩選（預留，未來擴充用）
│
├── core/                          # 🎯 規則引擎層：純 Python 打分 + 建議
│   ├── __init__.py                #   模組初始化
│   ├── scoring_config.py          #   評分設定檔：四種風格的權重、門檻值（集中管理，方便調整）
│   ├── scorer.py                  #   四風格打分：短線/波段/價值/定存 0-100 分（含子項明細）
│   ├── backtest.py                #   回測分析模組（五種策略獨立追蹤）
│   ├── trade_manager.py           #   買賣建議（型態認領 + 四維度投票 + 飛刀濾網 + 鐵盾）
│   └── advisor.py                 #   基本建議：根據分數區間給出買/持有/賣建議
│
├── ai/                            # 🤖 AI 層：DeepSeek API 整合
│   ├── __init__.py                #   模組初始化
│   ├── analyzer.py                #   DeepSeek API 呼叫、JSON 解析、降級回應（fallback）
│   └── prompts.py                 #   System Prompt：四種風格的 Prompt + 綜合分析 Prompt
│
├── utils/                         # 🔧 共用工具
│   ├── __init__.py                #   模組初始化
│   └── helpers.py                 #   金鑰驗證、錯誤處理、日期格式化、數字格式化
│
├── tests/                         # 🧪 單元測試
│   └── test_core.py               #   核心模組測試
│
├── docs/                          # 📚 設計文件
│   ├── DESIGN_v1.0.md             #   系統架構設計文件
│   ├── SCORING_STANDARDS_v1.0.md  #   評分標準文件
│   ├── CHANGELOG_v0.2.md          #   修改歷程 0.2
│   ├── CHANGELOG_v0.3.md          #   修改歷程 0.3
│   ├── CHART_SPEC_v1.0.md         #   圖表規格文件
│   └── README_v1.0.md             #   本文件，v1.0 完整說明
│
├── bug/                           # 🐛 除錯工具與 low data 輸出
│   ├── check_csv.py               #   CSV 內容檢核（筆數/日期/欄位數值）
│   ├── check_nan.py               #   NaN 檢核（Debt_Ratio_Trend/EPS_YoY）
│   ├── check_finmind_raw.py       #   FinMind 原始資料檢核
│   ├── check_full_pipeline.py     #   完整管線檢核
│   ├── test_debug_from_csv.py     #   從 CSV 除錯測試
│   ├── check_result.txt           #   檢核結果摘要
│   ├── 1216_20260712_152125_debug.csv
│   ├── 1513_20260712_151926_debug.csv
│   └── 2324_20260712_152017_debug.csv
│
└── data/debug/                    # 回測 CSV 輸出目錄
```

---

## 三、三層分析架構

```
┌─────────────────────────────────────────────────────────────────┐
│                        三層分析架構                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  第一層：純數據打分（core/scorer.py）                   │   │
│  │  ├── 輸入：母表（已對齊之財務/籌碼/技術指標）           │   │
│  │  ├── 邏輯：根據四種風格權重，計算 0-100 分             │   │
│  │  ├── 輸出：短線分數 / 波段分數 / 價值分數 / 定存分數   │   │
│  │  └── 特點：純 Python，不依賴 AI，速度極快              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  第二層：交易規則（core/trade_manager.py）               │   │
│  │  ├── 輸入：四種風格分數                                 │   │
│  │  ├── 邏輯：型態認領 + 四維度投票 + 飛刀濾網 + 鐵盾      │   │
│  │  └── 特點：純 Python，可解釋性高                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  第三層：AI 解說（ai/analyzer.py）                       │   │
│  │  ├── 輸入：指標數據 + 打分結果 + 交易建議               │   │
│  │  ├── 邏輯：DeepSeek API                                 │   │
│  │  └── 特點：可選，不影響評分與回測                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 四、數據管線與母表對齊

### 4.1 核心原則

- **主索引頻率：日頻** — 以 `TaiwanStockPrice` 的 `date` 為主軸
- **對齊基準：一律採用「實際公告 / 生效日期」**，而非「所屬期間」
- **四個風格模組僅能唯讀調用母表欄位**，不得重複呼叫 API

### 4.2 各類資料對齊規則

| 資料類型 | 原始頻率 | 對齊規則 |
|:---|:---|:---|
| 股價 / 成交量 | 日 | 主軸，不需對齊 |
| 月營收 | 月 | 以**公告日**（create_time）`merge_asof(direction='backward')` 對齊 |
| 損益表 / 資產負債表 / 現金流量表 | 季 | 以**公告日**（date）對齊，不可用季度結束日 |
| 股利 | 不定期 | 以**公告日**（AnnouncementDate）對齊 |
| 本益比歷史 | 日 | 以 date 直接 merge |
| 三大法人 / 融資券 / 借券 | 日 | 以 date 直接 merge |

### 4.3 衍生欄位計算

| 衍生欄位 | 計算公式 | 防呆邏輯 |
|:---|:---|:---|
| MA_5/10/20/60 | close.rolling().mean() | 不足窗口天數回傳 NaN |
| Vol_MA_5 | volume.rolling(5).mean() | 同上 |
| Revenue_YoY | (當月 - 去年同月) / 去年同月 | 用 revenue_year/month 精準對齊 |
| TTM_EPS | 最新4季單季EPS rolling(4).sum() | 不足4季標記 TTM_EPS_Valid=False |
| TTM_FCF | 4季營業現金流 - 4季資本支出 | 同上 |
| PE/PB_Percentile | 百分位計算 | 先過濾 EPS 為負的區間 |
| Data_Years_Available | 原始財報日期範圍 | 從原始資料計算，不受股價範圍限制 |

### 4.4 母表建構流程

```
build_universal_base_table()
│
├─ 1. 以股價為主軸 (date, stock_id, open, high, low, close, volume)
├─ 2. 預先計算 Data_Years_Available（從原始財報日期）
├─ 3. merge_asof 月營收（以 create_time 公告日 backward）
├─ 4. merge_asof 損益表（以 date 公告日 backward，移除 stock_id）
├─ 5. merge_asof 資產負債表（以 date 公告日 backward，移除 stock_id）
├─ 6. merge_asof 現金流量表（以 date 公告日 backward，移除 stock_id）
├─ 7. merge_asof 股利（以 announce_date 公告日 backward，原始每筆）
├─ 8. merge_asof 本益比（以 date backward）
├─ 9. merge_asof 三大法人（以 date backward）
├─ 10. merge_asof 融資券（以 date backward）
├─ 11. merge_asof 借券（以 date backward）
├─ 12. 移除重複 stock_id + 寫入 Data_Years_Available
│
└─ return base

calculate_derived_columns()
│
├─ 1. MA_5/10/20/60（close rolling）
├─ 2. Vol_MA_5（volume rolling）
├─ 3. Revenue_YoY（revenue_year/month 精準對齊）
├─ 4. TTM_EPS（EPS rolling 4 季）
├─ 5. TTM_FCF（OperatingCF - CAPEX rolling 4 季）
├─ 6. PE/PB Percentile（過濾 EPS 為負後計算）
├─ 7. 保留 Data_Years_Available（不覆蓋）
│
└─ return result
```

---

## 五、四種投資風格評分

### 5.1 評分架構

- **版本**：v1.0（2026-07-13）
- **評分方式**：每個子項採 **五級評分**（Excellent=100, Good=80, Normal=60, Weak=30, Poor=0）
- **權重**：每個風格各有 **6 個子項**，權重總和 100%
- **調整機制**：
  - **Data Quality Modifier**：根據資料年數調整（≥8年×1.00, ≥5年×0.95, ≥3年×0.85, <3年×0.70）
  - **Risk Modifier**：Penalty（RSI過熱-10、負債過高-10、EPS為負-15、發老本配息-15）+ Bonus（RSI超賣+5、低負債+5）
- **門檻集中管理**：`core/scoring_config.py`，調整不影響邏輯

### 5.2 短線評分（6 子項）

| 子項 | 權重 | 評分方式 |
|:---|:---:|:---|
| trend_structure（趨勢結構） | 20% | 均線排列（60%）+ 站上均線數量（40%），五級評分 |
| momentum（動能強度） | 20% | RSI 位置（40%）+ MACD 狀態（35%）+ 突破前高（25%），五級評分 |
| volume（成交量結構） | 20% | Volume Ratio（60%）+ 爆量程度（40%），五級評分 |
| institutional（法人籌碼） | 15% | 5日法人（35%）+ 10日法人（25%）+ 外資（25%）+ 投信（15%），五級評分 |
| chip（籌碼健康） | 15% | 融資變化（40%，反向）+ 融券變化（30%）+ 借券變化（30%，反向），五級評分 |
| risk（波動風險） | 10% | 乖離率（40%，反向）+ ATR（30%，反向）+ RSI過熱檢查（30%），五級評分 |

### 5.3 波段評分（6 子項）

| 子項 | 權重 | 評分方式 |
|:---|:---:|:---|
| revenue_momentum（營收動能） | 25% | Revenue YoY（50%）+ Revenue MoM（25%）+ 營收加速度（25%），五級評分 |
| mid_trend（中期趨勢） | 20% | 站上MA20（25%）+ 站上MA60（25%）+ MA20乖離（25%，反向）+ MA60乖離（25%，反向），五級評分 |
| institutional_trend（籌碼趨勢） | 20% | 20日法人（45%）+ 借券趨勢（25%，反向）+ 法人連續買超天數（30%），五級評分 |
| earnings_growth（獲利成長） | 15% | TTM EPS（60%）+ EPS YoY（40%），五級評分 |
| valuation（估值位置） | 10% | PE Percentile（60%，反向）+ PB Percentile（40%，反向），五級評分 |
| catalyst（催化因子） | 10% | 營收動能代理指標，五級評分 |

### 5.4 價值評分（6 子項）

| 子項 | 權重 | 評分方式 |
|:---|:---:|:---|
| valuation_safety（估值安全） | 15% | PE Percentile（60%，反向）+ PB Percentile（40%，反向），五級評分 |
| profit_quality（獲利品質） | 20% | ROE（45%）+ ROA（25%）+ 毛利率（30%），五級評分 |
| growth_ability（成長能力） | 30% | TTM EPS（60%）+ Revenue YoY（40%），五級評分 |
| financial_safety（財務安全） | 15% | 負債比（60%，反向）+ 流動比率（40%），五級評分 |
| cash_flow_quality（現金流品質） | 10% | TTM FCF + Operating CF，五級評分 |
| shareholder_return（股東報酬） | 10% | 殖利率 + 配息與否，五級評分 |

### 5.5 定存評分（6 子項）

| 子項 | 權重 | 評分方式 |
|:---|:---:|:---|
| dividend_record（配息紀錄） | 25% | 連續配息年數，五級評分 |
| dividend_quality（配息品質） | 20% | 配息率區間 + EPS 覆蓋倍數，五級評分 |
| cash_flow（現金流） | 20% | FCF 覆蓋倍數，五級評分 |
| financial_safety（財務安全） | 15% | 負債比（反向）+ 利息保障倍數，五級評分 |
| profit_stability（獲利穩定） | 10% | ROE 標準差（反向）+ EPS 標準差（反向），五級評分 |
| long_term_growth（長期成長） | 10% | 營收 CAGR + EPS 年成長率，五級評分 |

### 5.6 輸出格式

```python
{
  "short_term": {"total": 78, "breakdown": {"trend_structure": 80, "momentum": 75, ...}},
  "swing": {"total": 65, "breakdown": {...}},
  "value": {"total": 72, "breakdown": {...}},
  "dividend": {"total": 60, "breakdown": {...}},
}
```

---

## 六、前端畫面規劃（瀑布流 6 階段）

### 6.1 瀑布流顯示順序

系統採用 **瀑布流（Waterfall）** 渲染方式，內容逐步顯示，使用者不需等待全部完成即可看到部分結果：

| 階段 | 觸發時機 | 顯示內容 |
|:---|:---|:---|
| **1. 📥 大盤+個股資訊卡** | 撈取資料完成 | 加權指數、漲跌幅、總成交金額、股價、漲跌幅、成交量、本益比 |
| **2. 📊 圖表區** | 計算指標完成 | 短線面（K線+均線/成交量/RSI/法人/融資券）+ 中長線面（ROE/毛利率/EPS/YoY/PE/PB/FCF/股利） |
| **3. 🎯 四維度分析+基本建議** | 評分完成 | 短線/波段/價值/定存 0-100分（含子項明細） |
| **4. 🤖 AI 解說** | AI 分析完成 | 總結、加分/扣分原因、適合族群、風險提醒、後續觀察重點 |
| **5. 📊 回測分析** | 使用者點擊 | 分數走勢圖 + 價格訊號圖 + 五種策略績效 + 交易明細表 |
| **6. ⚠️ 風險提示+除錯面板** | 全部完成 | 高風險提醒（PE過高/負債比高/RSI超買等）+ 撈取資訊/計算欄位/最新數據/母表欄位 |

---

## 七、完成進度

### 7.1 斷點完成狀態

| # | 斷點名稱 | 狀態 | 對應檔案 |
|:---|:---|:---:|:---|
| 0 | 環境骨架 | ✅ | 目錄結構、requirements.txt、Dockerfile |
| 1 | fetcher：股價 + 大盤 | ✅ | data/fetcher.py |
| 2 | fetcher：籌碼面 | ✅ | data/fetcher.py |
| 3 | fetcher：基本面 | ✅ | data/fetcher.py |
| 4 | processor：母表對齊邏輯 | ✅ | data/processor.py |
| 5 | metrics：技術指標 | ✅ | stock/metrics.py |
| 6 | metrics：財務指標 | ✅ | stock/metrics.py |
| 7 | scorer：四風格打分 | ✅ | core/scorer.py + scoring_config.py |
| 8 | advisor / trade_manager：規則建議 | ✅ | core/advisor.py + trade_manager.py |
| 9 | AI prompts + analyzer | ✅ | ai/prompts.py + analyzer.py |
| 10 | 前端骨架（假資料） | ✅ | app.py |
| 11 | 前端串接真實資料 + 圖表 | ✅ | app.py |
| 12 | 回測模組 | ✅ | core/backtest.py |
| 13 | 整合測試 | ⬜ | 待執行 |
| 14 | 部署上 Render | ⬜ | 待執行 |

### 7.2 已完成模組功能清單

| 模組 | 功能 | 說明 |
|:---|:---|:---|
| **data/fetcher.py** | 12 個 FinMind API 呼叫 | 股價、大盤、股票資訊、月營收、損益表、資產負債表、現金流量表、股利、本益比、三大法人、融資券、借券 |
| **data/processor.py** | 母表建構 + 衍生欄位 | 9 種資料 merge_asof 對齊、MA/YoY/TTM/Percentile 計算、防呆邏輯 |
| **stock/metrics.py** | 技術 + 財務指標 | RSI、MA_Alignment、Volume_Ratio、法人累計、籌碼背離、ROE、毛利率、負債比、配息率、FCF 覆蓋 |
| **core/scoring_config.py** | 權重與門檻設定 | 四種風格的權重與門檻值，集中管理 |
| **core/scorer.py** | 四風格打分 | 每個子項獨立函式，輸出含 breakdown 明細 |
| **core/backtest.py** | 回測分析 | 五種策略獨立追蹤，walk-forward 評分 |
| **core/trade_manager.py** | 買賣建議 | 型態認領 + 四維度投票 + 飛刀濾網 + 鐵盾 |
| **core/advisor.py** | 基本建議 | 分數區間 if-else 規則 |
| **ai/prompts.py** | System Prompt | 四種風格 + 綜合 Prompt，含 primary_decision |
| **ai/analyzer.py** | DeepSeek API 呼叫 | JSON 解析、降級回應（fallback） |
| **utils/helpers.py** | 共用工具 | 金鑰驗證、日期格式化、數字格式化 |
| **app.py** | Streamlit 前端 | 瀑布流 6 階段、側邊欄、圖表、數據表格 |

---

## 八、改版歷程

### 0.1 → 0.2（2026-07-11）

| # | 問題 | 原因 | 解決方式 |
|:---|:---|:---|:---|
| 1 | 股利 year 欄位髒資料 | FinMind 回傳「105年」「無資料」等非標準格式 | 支援民國年/西元年/髒資料清洗 |
| 2 | Data_Years_Available 計算錯誤 | 從股價日期計算，受股價範圍限制 | 改從原始財報日期計算 |
| 3 | 營收 YoY 計算不準 | 用日期對齊去年同月，遇到跨年/缺資料會錯位 | 改用 revenue_year/month 精準對齊 |
| 4 | 股利 merge 錯誤 | groupby 後 merge 導致資料錯亂 | 改用原始每筆資料直接 merge_asof |
| 5 | 財報 pivot 後 stock_id 重複 | merge 時重複欄位導致衝突 | merge 前移除重複欄位 |

### 0.2 → 0.3（2026-07-12）

| # | 問題 | 原因 | 解決方式 |
|:---|:---|:---|:---|
| 1 | **EPS_YoY 計算異常** | 股價只撈 1 年，導致部分股票 EPS_YoY 因歷史不足而為 NaN | **股價改撈 3 年**，確保有足夠的財報歷史計算 YoY |
| 2 | **Debt_Ratio_Trend 計算異常** | 同上，1 年股價範圍內財報筆數不足，趨勢無法計算 | 同上，股價改撈 3 年 |
| 3 | 前端圖表空白 | 前端未串接真實資料 | 完成瀑布流 5 階段全部實作 |
| 4 | AI 解說格式不一致 | DeepSeek 回傳格式不固定 | 統一輸出 explanation 格式，含 evidence JSON |
| 5 | 無除錯工具 | 無法快速定位問題 | 建立 bug/ 目錄 + 5 分頁除錯面板 |
| 6 | 重複分析浪費時間 | 每次分析都重新撈取資料 | 實作快取機制，同股票跳過撈取 |

### 0.3 → 0.4（2026-07-13）

| # | 項目 | 說明 |
|:---|:---|:---|
| 1 | **回測模組** | 五種策略回測（短線/波段/價值/定存/綜合），walk-forward 評分 |
| 2 | **倒三角建議** | 型態認領（未持有）+ 四維度投票（已持有）+ 飛刀濾網 + 鐵盾 |
| 3 | **評分權重調整** | 價值風格：估值25%→15%、成長20%→30% |
| 4 | **前端瀑布流 6 階段** | 加入回測分析階段 |
| 5 | **免責聲明** | 頁面頂部與底部加入投資警語 |

### 資料撈取長度演進

```
0.1:  股價 1年  | 籌碼 1年  | 基本面 10年
0.2:  股價 1年  | 籌碼 1年  | 基本面 10年  (Bug 修復)
0.3:  股價 3年  | 籌碼 1年  | 基本面 10年  (因 YoY 異常調整)
0.4:  股價 3年  | 籌碼 1年  | 基本面 10年  (新增回測模組)
```

---

## 九、待完成項目（Roadmap）

### 9.1 短期

| # | 項目 | 優先級 | 說明 |
|:---|:---|:---:|:---|
| 1 | **整合測試自動化** | 🔴 高 | 撰寫 pytest 測試案例，覆蓋各模組 |
| 2 | **Edge Case 處理** | 🔴 高 | 處理股利為 0、EPS 為負、資料不足等特殊情況的評分邏輯 |
| 3 | **評分標準調校** | 🟡 中 | 根據實際跑分結果調整 scoring_config.py 的權重與門檻 |
| 4 | **AI Prompt 優化** | 🟡 中 | 根據 DeepSeek 回傳品質調整 system prompt |
| 5 | **錯誤處理強化** | 🟡 中 | 統一錯誤訊息格式，前端顯示更友善的錯誤提示 |
| 6 | **一天內資料暫存** | 🔴 高 | 同一天內重複查同一支股票時，直接讀取暫存資料 |

### 9.2 中期

| # | 項目 | 優先級 | 說明 |
|:---|:---|:---:|:---|
| 7 | **多股比較功能** | 🟡 中 | 同時分析多檔股票，並排顯示評分結果 |
| 8 | **選股篩選器（screener）** | 🟡 中 | 根據四維度分數過濾全市場股票 |
| 9 | **持股管理功能** | 🟢 低 | 記錄多檔持股、損益計算、加減碼建議 |
| 10 | **通知機制** | 🟢 低 | 當持股評分變化時發送通知（Email/Line） |

### 9.3 長期

| # | 項目 | 優先級 | 說明 |
|:---|:---|:---:|:---|
| 11 | **部署上 Render** | 🟡 中 | 容器化部署至 Render 雲端平台 |
| 12 | **新聞/產業面分析** | 🟢 低 | 加入新聞情緒分析、產業趨勢判斷 |
| 13 | **國際股市連動** | 🟢 低 | 加入美股/陸股/匯率等外部因子 |
| 14 | **使用者帳號系統** | 🟢 低 | 多使用者、個人化設定儲存 |

---

## 十、Bug 修復記錄

### 10.1 0.2 修復項目

| # | 問題 | 狀態 | 說明 |
|:---|:---|:---:|:---|
| 1 | 股利 year 欄位資料清洗 | ✅ | 支援民國年/西元年/髒資料（"105年"→2016、"無資料"→過濾） |
| 2 | Data_Years_Available 計算錯誤 | ✅ | 改從原始財報日期計算，不受股價範圍限制 |
| 3 | 營收 YoY 計算不準 | ✅ | 改用 revenue_year/month 精準對齊去年同月 |
| 4 | 股利 groupby 後 merge 問題 | ✅ | 改用原始每筆資料直接 merge_asof |
| 5 | 財報 pivot 後 stock_id 重複 | ✅ | merge 前移除重複欄位 |

### 10.2 0.3 修復項目

| # | 問題 | 狀態 | 說明 |
|:---|:---|:---:|:---|
| 1 | EPS_YoY 因歷史不足為 NaN | ✅ | 股價改撈 3 年，確保有足夠財報歷史 |
| 2 | Debt_Ratio_Trend 因歷史不足為 NaN | ✅ | 同上，股價改撈 3 年 |
| 3 | 前端圖表空白 | ✅ | 瀑布流 5 階段全部串接真實資料 |
| 4 | AI 解說格式不一致 | ✅ | 統一 explanation 格式 + evidence JSON |
| 5 | 無除錯工具 | ✅ | bug/ 目錄 + 5 分頁除錯面板 |
| 6 | 重複分析浪費時間 | ✅ | 快取機制實作 |

---

## 十一、部署方式

### 11.1 本地開發

```bash
# 安裝依賴
pip install -r requirements.txt

# 啟動（開發模式）
streamlit run app.py

# 模擬 Render 啟動
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

### 11.2 Render 部署

| 項目 | 設定 |
|:---|:---|
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `streamlit run app.py --server.port $PORT --server.address 0.0.0.0` |
| **環境變數** | `FINMIND_TOKEN`、`DEEPSEEK_API_KEY`、`PORT`（自動） |

> **注意**：Streamlit 應用程式不是 WSGI callable，**不可使用** `gunicorn app:app` 啟動。

---

## 十二、測試方式

```bash
# 測試完整管線（需 FinMind Token）
python test_full_pipeline.py

# 啟動前端
streamlit run app.py
```

---

> ⚠️ **免責聲明**：本系統為個人研究專案，僅供學習與參考用途。所有分析結果與建議均不構成投資要約或建議。投資人應獨立判斷，審慎評估風險，並對自己的投資決策負責。股市投資可能導致本金損失，過去績效不代表未來表現。**本程式不保證獲利，使用前請詳閱相關風險說明。**