# 台股AI個人化決策系統 v1.4

> **版本**: v1.6  
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
│   ├── backtest.py           # 回測分析模組（五種策略獨立追蹤）
│   ├── trade_manager.py      # 買賣建議（型態認領 + 四維度投票 + 飛刀濾網 + 鐵盾 + 建議買價區間 v4.3）
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

### v1.3 評分權重總覽

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
| **價值** | valuation_safety | **15%** | 原25%，v1.0調降，改配給成長能力 |
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

### 未持有決策邏輯（5 級優先 + 雙風險規範 v4.3）

| 優先級 | 條件（保守/積極） | 結果 |
|:---|:---|:---|
| 1 | 全風格 < **70/60** | **不建議（附建議買價區間）** 🆕 |
| 2 | 波段 ≥ **70/60** | 買進（MA_20±2%，附區間） 🆕 |
| 3 | 短線 ≥ **70/60** | 買進（5MA，破20MA停損，附區間） 🆕 |
| 4-A | 價值/定存 ≥ **70/60**，短線站5MA | 買進（附建議買入區間） 🆕 |
| **4-B** | **價值/定存 ≥ 70/60 + 短線<50且破5MA** | **⭐ 飛刀濾網：觀望（附歷史低估價位）** 🆕 |
| 5 | 50~**70/60** | **觀望（附觀察價位區間）** 🆕 |

> **v4.3 新增**：P1/P4-B/P5 現在會輸出具體建議買價區間（entry_price_low ~ entry_price_high），不再只有制式文字。支援 risk_mode 參數（保守=70/50，積極=60/40）。

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
| 3票 | — | 持有（附 MA_20 補槍參考價 + 區間） 🆕 |
| 2票 | + 法人連3轉負 | 減碼 |
| 2票 | 法人未轉負 | 持有觀望（附 MA_20 參考價 + 區間） 🆕 |
| 1/0票 | **⭐ 鐵盾啟動** | **持有觀望（基本面鐵盾覆蓋 + 區間）** 🆕 |
| 1票 | 鐵盾未啟動 | 減碼 |
| 0票 | 鐵盾未啟動 | 賣出 |

**鐵盾條件：** 價值>70 或 定存>70，且虧損 ≤ 5%

---

## 回測功能

### 預設參數

| 參數 | 預設值 | 說明 |
|:---|:---:|:---|
| 輸出頻率 | **每日 (D)** | 每交易日評分一次，可改每週(W)或每月(M) |
| 買入門檻 | **60** | 分數 ≥ 60 觸發買入訊號（v1.0 調降提高交易敏感度） |
| 賣出門檻 | **40** | 分數 < 40 觸發賣出訊號（配合買入門檻同步調降） |

### 操作流程

1. 完成分析後點擊側邊欄「📊 回測分析」按鈕
2. 切換到圖表區第 3 個 Tab「📊 回測分析」
3. 展開「⚙️ 回測參數設定」調整參數 → 按「▶️ 執行回測」
4. 查看結果：分數走勢圖、價格訊號圖、五種策略績效總覽、交易明細表
5. 修改任一參數後可再次按「▶️ 執行回測」重新運算（無需鎖定）
6. 切換「保守/積極」按鈕快速切換雙策略顯示（各自綁定對應 threshold）

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
- CSV 除錯：回測完成後點擊「📥 下載 積極(60/40) CSV / 保守(70/50) CSV」手動下載
- Debug CSV：除錯面板「匯出 CSV」分頁改為手動按鈕，不再每次渲染自動寫入

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

> 等 SQLite + 儀表板穩定後再搞模擬盤，基礎設施到位了做起來才順。

---

## Render 中文部署教學（GitHub → Render）

> 以下完整教學，照著做就能讓朋友透過網址直接使用本系統。

### 📦 第一步：上傳程式碼到 GitHub

#### 1.1 註冊 GitHub（如果還沒有帳號）

1. 打開 https://github.com/signup → 註冊帳號
2. 登入後，點右上角 **+** → **New repository**
3. 填入倉庫名稱（例如 `tw-stock-analyzer`）
4. 選 **Private**（私人倉庫，避免 API Token 外洩）或 **Public**（公開）
5. 點 **Create repository**

#### 1.2 上傳程式碼

在本機終端機（在專案資料夾裡）依序輸入：

```bash
# 初始化 git
git init
git add .
git commit -m "v1.6 初始上傳"

# 連到 GitHub — 如果出現 remote origin already exists，改用 set-url
git remote add origin https://github.com/YOUR_USER/tw-stock-analyzer.git
# 如果上面那行報錯，改執行這行：
git remote set-url origin https://github.com/YOUR_USER/tw-stock-analyzer.git

# 上傳
git push -u origin main
```

> 💡 如果 GitHub 要求登入，可以改用 **Personal Access Token**（Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token，勾 `repo`）

### 🚀 第二步：部署到 Render

#### 2.1 註冊 Render

1. 打開 https://dashboard.render.com/register
2. 用 GitHub 帳號登入（最方便）

#### 2.2 建立 Web Service

1. 點 **New +** → **Web Service**
2. 選 **Build and deploy from a Git repository**
3. 點 **Connect** → 選擇 `tw-stock-analyzer` 倉庫
4. 填寫設定：

| 欄位 | 填法 |
|:---|:---|
| **Name** | `tw-stock-analyzer`（自訂，網址會是這個） |
| **Region** | 選 **Singapore**（新加坡，離台灣近） |
| **Branch** | `main` |
| **Runtime** | **Docker**（用我們寫好的 Dockerfile） |
| **Instance Type** | **Free**（免費方案） |

#### 2.3 設定環境變數（Environment Variables）

在 Render 的 **Environment** 區塊，點 **Add Environment Variable**，填入：

| Key | Value |
|:---|:---|
| `FINMIND_TOKEN` | 你的 FinMind API Token（必填） |
| `DEEPSEEK_API_KEY` | 你的 DeepSeek API Key（選填，不填就沒 AI 解說） |

> 🔐 這兩個值只有你能看到，Render 會加密儲存，不會外洩。

#### 2.4 啟動

1. 頁面最下方點 **Create Web Service**
2. Render 會自動開始 build（約 3~5 分鐘）
3. 看到 **Your service is live 🎉** 就完成了
4. 網址是：`https://tw-stock-analyzer.onrender.com`

### 🌐 第三步：開始使用

1. 把網址 `https://tw-stock-analyzer.onrender.com` 傳給朋友
2. 朋友打開瀏覽器 → 輸入股票代號 → 按「開始分析」就能用了
3. **不需要安裝任何東西，也不用註冊 API Token**（因為 Token 已經設在 Render 的環境變數裡了）

> ⚠️ **Render 免費方案注意事項：**
> - 閒置 15 分鐘會自動休眠
> - 有人訪問時約 30~60 秒才會啟動（會看到 Loading）
> - 每月 750 小時（足夠 24 小時連續開 31 天）
> - 休眠後自動重新啟動，不影響使用

### ❓ 常見問題

#### Q：如何更新程式碼？
在本機修改完程式後：
```bash
git add .
git commit -m "修改了 xxx"
git push
```
Render 會自動偵測到更新並重新部署。

#### Q：如何看 Log 除錯？
在 Render Dashboard → 點你的 Web Service → **Logs** 分頁。

#### Q：要如何設定自己的網域名稱？
Render Dashboard → **Settings** → **Custom Domain** → 輸入你的網址。

#### Q：佈署失敗怎麼辦？
1. 到 Render Logs 看錯誤訊息
2. 最常見原因：`requirements.txt` 遺漏套件 → 補上後重新 push 即可
3. 設了 `FINMIND_TOKEN` 但忘記加到 Environment → 補上後在 Render 點 **Manual Deploy → Deploy latest commit**

---

## Docker 自行架設（進階選項）

如果不用 Render，也可以在自己的 VPS 用 Docker 跑：

```bash
# 建立 image
docker build -t tw-stock-analyzer .

# 執行容器
docker run -p 8501:8501 \
  -e FINMIND_TOKEN=你的Token \
  -e DEEPSEEK_API_KEY=你的Key(選填) \
  tw-stock-analyzer
```

開啟 http://localhost:8501

---

## 變更記錄（修改歷程）

### v1.6 (2026-07-14) — 圖表增強 + 檔案整理

| 檔案 | 變更 |
|:---|:---|
| `app.py` | **短線面圖表新增股價疊加**：法人買賣超圖 + 融資券變化圖均疊加黑色股價線（右軸） |
| `app.py` | **波段圖表縮減至評分時間跨度**：中期趨勢圖從全年→近60日，籌碼趨勢圖全年→近20日 |
| `app.py` | **修復回測策略切換按鈕 bug**：積極/保守切換改用 `on_click` callback，解決第一次點無反應問題 |
| `README.md` | 加入 **網路佈署教學**（Docker / Streamlit Cloud / HuggingFace） |
| `.gitignore` | 新增 `archive/` 規則 |
| — | 整理專案：開發測試檔案搬至 `archive/`，清理 bug/ 與 data/debug/ 暫存 CSV |

### v1.5 (2026-07-14) — 回測增強版（threshold 修復 + 綜合策略修正 + 建議價位記錄）

| 檔案 | 變更 |
|:---|:---|
| `app.py` | **修復積極/保守 threshold 錯置** — 積極=買≥60/賣<40，保守=買≥70/賣<50（原相反），共修正 12 處 |
| `app.py` | 回測預設起始日從 `2026/1/1` 改為 **1 年前**（`datetime.now() - timedelta(days=365)`） |
| `app.py` | 除錯面板 CSV 匯出取消自動寫入，改為 **手動按鈕觸發** |
| `app.py` | 「📊 四維度分析」加入 **實盤操作 SOP**（四大策略操作指引） |
| `core/backtest.py` | **signal_history 新增 8 欄位**：high, low, agg_low, agg_high, cons_low, cons_high, price_in_range, composite_signal |
| `core/backtest.py` | **綜合策略買入條件修復**：原 `any(≥threshold)` 改為 **≥2 種風格** 同時通過才買 |
| `README.md` | 更新 v1.5 變更記錄 |

### v1.4 (2026-07-13) — 人類風格折扣法 + 建議買價區間

| 檔案 | 變更 |
|:---|:---|
| `core/trade_manager.py` | **v4.3** — TradeAdvice 新增 entry_price_low/entry_price_high 建議買價區間 |
| `core/trade_manager.py` | **v4.3** — 新增 _calc_aggressive_entry()/_calc_conservative_entry() 人類風格折扣法 |
| `core/trade_manager.py` | **v4.3** — P1/P4-B/P5 分支補上具體建議購買價位區間，不再只有制式文字 |
| `core/trade_manager.py` | **v4.3** — generate_trade_advice() 新增 risk_mode 參數（保守/積極雙風險規範） |
| `core/trade_manager.py` | **v4.3** — 所有建議價含 max() 邊界檢查，防止極限低價 |
| | 基於 2330/2454/6770 回測資料驗證，聯發科 1/5 案例成功避開追高套牢 |

### v1.0 (2026-07-13) — 初始穩定版

| 檔案 | 變更 |
|:---|:---|
| `app.py` | 回測輸出頻率預設改為「每日」(D)；買入門檻預設改為 60、賣出門檻預設改為 40 |
| `app.py` | 修復修改邊界後無法重新執行回測的問題（移除 _bt_trigger 鎖定機制） |
| `core/backtest.py` | 總報酬率改為已出清交易平均，持有中策略顯示未實現損益 |
| `app.py` | 新增頁面頂部與底部免責聲明、評分解讀提示、修復價格圖空白問題 |
| `README.md` | 統一版本號、更新預設參數說明與操作流程、新增新電腦安裝教學 |

### 0.4 (2026-07-11) — 回測增強版

| 檔案 | 變更 |
|:---|:---|
| `core/scorer.py` | 回測引擎(get_historical_scores)、金融業防錯(is_finance)、權重調整(v5.1)、動態RSI門檻 |
| `core/backtest.py` | **新檔案** - 五種策略回測(TradeRecord/BacktestResult/run_backtest) |
| `core/scoring_config.py` | VALUE_WEIGHTS 估值25%→15%, 成長20%→30% |
| `app.py` | 回測Tab + waterfall_6摘要 + Industry欄位merge + 快取邏輯修復 |

### 0.3 (2026-07-12) — 資料撈取調整

| # | 項目 | 說明 |
|:---|:---|:---|
| 1 | 股價撈取範圍改為 **3 年** | 確保 Debt_Ratio_Trend/EPS_YoY 等趨勢計算有足夠歷史 |
| 2 | 前端串接真實資料 + 圖表完成 | 瀑布流 5 階段全部實作完成 |
| 3 | AI 解說（DeepSeek Explain Engine）完成 | 輸出 explanation 格式，含 evidence JSON |
| 4 | 除錯面板（5 分頁）完成 | 撈取資訊/計算欄位/最新數據/母表欄位/匯出 CSV |
| 5 | 快取機制實作 | 同一支股票重複分析時跳過撈取 |

### 0.2 (2026-07-11) — Bug 修復

| # | 問題 | 解決方式 |
|:---|:---|:---|
| 1 | 股利 year 欄位髒資料 | 支援民國年/西元年/髒資料清洗 |
| 2 | Data_Years_Available 計算錯誤 | 改從原始財報日期計算 |
| 3 | 營收 YoY 計算不準 | 改用 revenue_year/month 精準對齊 |
| 4 | 股利 merge 錯誤 | 改用原始每筆資料直接 merge_asof |
| 5 | 財報 pivot 後 stock_id 重複 | merge 前移除重複欄位 |

### 0.1 — 初始版本

系統初始建置完成，包含：
- 12 種 FinMind API 資料抓取
- 母表對齊邏輯（merge_asof 公告日對齊）
- 技術指標 + 財務指標計算
- 四風格打分（短線/波段/價值/定存）
- 基本建議規則
- DeepSeek AI 解說整合
- Streamlit 前端瀑布流顯示

---

> ⚠️ **免責聲明**：本系統為個人研究專案，僅供學習與參考用途。所有分析結果與建議均不構成投資要約或建議。投資人應獨立判斷，審慎評估風險，並對自己的投資決策負責。股市投資可能導致本金損失，過去績效不代表未來表現。**本程式不保證獲利，使用前請詳閱相關風險說明。**