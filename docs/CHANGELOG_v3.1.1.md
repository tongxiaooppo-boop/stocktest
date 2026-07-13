# 台股 AI 個人化決策系統 v3.1.1 變更記錄

> **版本**: v3.1.1  
> **日期**: 2026-07-11 19:51  
> **模組**: `data/processor.py`  
> **類型**: Bug 修復 + 資料清洗強化

---

## 修復項目總覽

| # | 問題 | 狀態 | 說明 |
|---|------|------|------|
| 1 | 股利 year 欄位資料清洗 | ✅ 已修復 | 支援民國年/西元年/髒資料 |
| 2 | Data_Years_Available 計算錯誤 | ✅ 已修復 | 改從原始財報日期計算 |
| 3 | 營收 YoY 計算不準 | ✅ 已修復 | 改用 revenue_year/month 精準對齊 |
| 4 | 股利 groupby 後 merge 問題 | ✅ 已修復 | 改用原始每筆資料直接 merge |
| 5 | 財報 pivot 後 stock_id 重複 | ✅ 已修復 | merge 前移除重複欄位 |

---

## 詳細變更內容

### Bug 1: 股利 year 欄位資料清洗

**問題**: FinMind 回傳的 `year` 欄位格式多樣：
- `"105年"`（民國年）
- `"108年第1季"`（民國年+季度）
- `"2015"`（西元年）
- `"無資料"`、`"nono"`（髒資料）

原本用 `str.extract(r"(\d+)")` 直接轉 int，遇到髒資料會報錯。

**修復**: 新增 `_parse_year()` 函數：
1. 用 `re.findall(r"\d+")` 提取第一個連續數字區塊
2. 若數字 ≤ 150 → 視為民國年，自動 +1911 轉西元
3. 若數字 ≥ 1900 → 視為西元年，直接使用
4. 若無數字 → 回傳 None，後續 `dropna` 自動過濾

**測試結果**（2330 台積電）：
```
105年 → 2016
108年第1季 → 2019
114年第4季 → 2025
```

---

### Bug 2: Data_Years_Available 計算錯誤

**問題**: 原本在 `calculate_derived_columns()` 中用母表的 EPS 日期範圍計算可用年數。但母表的日期範圍受股價資料限制（只抓近 1 年），導致最多只算出 1 年，無法反映真實的財報歷史長度。

**修復**: 
1. 在 `build_universal_base_table()` 中，從**原始財報資料**（`df_financial`, `df_balance`, `df_cash_flow`）的日期預先計算 `data_years_available`
2. 寫入母表的 `Data_Years_Available` 欄位
3. 在 `calculate_derived_columns()` 中保留該欄位不做覆蓋（若不存在則補計算）

**流程**:
```
原始財報日期 → 取 min/max → 計算年數 → 寫入母表 → 保留至最終輸出
```

---

### Bug 3: 營收 YoY 計算

**問題**: 原本用 `pct_change(periods=12)` 計算營收年增率，但母表經過 merge_asof 後，月營收資料在每筆股價日期上都有值（重複），導致 rolling 計算不準確。

**修復**: 改用 `revenue_year` / `revenue_month` 精準對齊去年同月：
1. 過濾出有營收資料的列
2. 建立 `"year_month"` key（如 `"2025_06"`）
3. 建立 lookup dict：`this_year_key → month_revenue`
4. 用 `last_year_key = (year-1)_month` 查找去年同月營收
5. 計算 `(當月 - 去年同月) / 去年同月`

---

### Bug 4: 股利 groupby 後 merge 問題

**問題**: 原本先 groupby 每年加總股利，再 merge_asof 到母表。但 groupby 後只剩每年一筆資料，merge_asof 時對齊不精準。

**修復**: 改用原始每筆股利資料的 `announce_date` 直接 merge_asof：
- 保留每筆股利公告記錄
- 每筆股利公告後，母表就能對應到最新的股利資訊
- 欄位名稱改為 `cash_dividend` / `cash_statutory`（單筆）

---

### Bug 5: 財報 pivot 後 stock_id 重複

**問題**: `_pivot_financial_statements()` 回傳的 DataFrame 包含 `stock_id` 欄位，merge_asof 時會帶入母表，造成多個 `stock_id` 欄位。

**修復**: 在 merge 前對財報三表（損益表/資產負債表/現金流量表）各執行：
```python
df_pivot = df_pivot.drop(columns=["stock_id"], errors="ignore")
```

---

## 函數流程圖

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

## 測試方式

```bash
# 測試股利 year 解析
python "d:\AI股票程式參考\TW Stock AI\taiwan-stock-analyzer-v3\test_parse_year.py"

# 測試完整管線
python "d:\AI股票程式參考\TW Stock AI\taiwan-stock-analyzer-v3\test_full_pipeline.py"
```

---

## 附錄：v2.0 備份專案分析摘要

> 分析日期：2026-07-11  
> 分析對象：`taiwan-stock-analyzer-master_max_backup_phase1_ok`（v2.0 備份）

### 資料抓取涵蓋度

| 資料集 | v2.0 | v3.1 |
|:---|:---:|:---:|
| 股價（TaiwanStockPrice） | ✅ | ✅ |
| 股票資訊（TaiwanStockInfo） | ✅ | ✅ |
| 損益表（FinancialStatements） | ✅ | ✅ |
| 資產負債表（BalanceSheet） | ✅ | ✅ |
| 現金流量表（CashFlowsStatement） | ✅ | ✅ |
| 股利（Dividend） | ✅ | ✅ |
| 月營收（MonthRevenue） | ❌ | ✅ |
| 本益比歷史（PER） | ❌ | ✅ |
| 三大法人買賣超 | ❌ | ✅ |
| 融資券 | ❌ | ✅ |
| 借券 | ❌ | ✅ |
| 大盤指數 TAIEX | ❌ | ✅ |

**結論：v3.1 完整涵蓋 v2.0 所有資料集，且多出 6 種籌碼面/營收/大盤資料。**

### 評分與 AI 分析比較

| 項目 | v2.0 | v3.1 |
|:---|:---|:---|
| **評分方式** | AI 評分（GPT 五維度） | 純 Python 規則打分（四風格） |
| **速度** | 慢（需等 API） | 極快（毫秒級） |
| **成本** | 每次付費 | 免費 |
| **可解釋性** | 低（黑箱） | 高（權重明確） |
| **穩定性** | 低（API/JSON 可能失敗） | 高（純本地計算） |
| **投資風格** | 單一評分 | 短線/波段/價值/定存四種 |
| **防呆機制** | 無 | RSI過熱打折、資料不足打折 |

### v2.0 值得參考的設計（已記錄，暫不實作）

1. **串流輸出（打字機效果）**：`st.write_stream()` 讓 AI 分析有即時感
2. **優勢/風險標籤**：AI 產出 strengths/risks 清單，以彩色 Badge 顯示
3. **按鈕觸發 AI**（非自動）：使用者主動點擊才呼叫，節省 API 費用
4. **五維度雷達圖**：視覺化呈現 AI 評分面向
5. **錯誤訊息友善化**：`format_openai_error()` 把金鑰錯誤轉成中文指引
6. **批次容錯**：單檔 AI 失敗不影響其他股票，用 fallback 保留該股
7. **session_state 保存**：AI 結果存 session_state，切換 Tab 不消失
8. **建議顏色對應**：強烈買入(深綠)→買入(淺綠)→持有(橙黃)→賣出(淺紅)→強烈賣出(深紅)

---

## 附錄二：my-stock-app 參考專案分析摘要

> 分析日期：2026-07-11  
> 分析對象：`my-stock-app-main_python_max_backup_phase1_ok`  
> 來源：GitHub RitaWu425/my-stock-app  
> 類型：單一 app.py（707行），無模組化

### 專案結構

```
my-stock-app/
├── app.py              ← 單一檔案（707行）
├── font.ttf            ← 中文字型
├── README.md           ← 簡短說明
├── requirements.txt    ← 依賴
├── LICENSE
├── .gitignore
└── 註解.txt
```

### 使用的資料集

| 資料集 | 這個專案 | v3.1 |
|:---|:---:|:---:|
| TaiwanStockPrice（股價） | ✅ | ✅ |
| TaiwanStockInfo（股票資訊） | ✅ | ✅ |
| TaiwanStockFinancialStatements（損益表） | ✅ | ✅ |
| TaiwanStockInstitutionalInvestors（三大法人） | ✅ | ✅ |
| TaiwanStockMarginPurchaseShortSale（融資券） | ✅ | ✅ |
| TaiwanDailyShortSaleBalances（借券） | ✅ | ✅ |
| 大盤 TAIEX 股價 | ✅ | ✅ |
| 融資券總表（MarginPurchaseShortSaleTotal） | ✅ | ❌ **v3.1 沒有** |
| TaiwanStockBalanceSheet（資產負債表） | ❌ | ✅ |
| TaiwanStockCashFlowsStatement（現金流量表） | ❌ | ✅ |
| TaiwanStockDividend（股利） | ❌ | ✅ |
| TaiwanStockMonthRevenue（月營收） | ❌ | ✅ |
| TaiwanStockPER（本益比歷史） | ❌ | ✅ |

### 這個專案的特色（v3.1 可以參考的）

1. **籌碼面分析很強**：
   - 三大法人買賣超（外資/投信/自營/權證）
   - 融資券變動 + 大盤融資券總表
   - 借券回補天數計算（連續回補天數）
   - 籌碼集中度計算

2. **技術面指標**：
   - 5MA 均線 + 5MA 均量
   - RSI 指標（6日）
   - 量價關係判斷（帶量攻擊 vs 量能不足）

3. **大盤資訊**：
   - 加權指數、漲跌幅、總成交量
   - 大盤融資餘額、融券餘額

4. **圖表**：
   - Matplotlib 靜態圖表（非 Plotly）
   - 雙 Y 軸圖表（股價 + 借券）
   - 法人進出長條圖
   - 營收/毛利率趨勢圖

5. **AI 分析**：
   - DeepSeek（與 v3.1 相同）
   - 按鈕觸發（非自動）
   - 提示詞包含技術面 + 籌碼面數據

6. **操作建議邏輯**：
   - 多條件判斷（股價/5MA/法人/RSI/量能）
   - 輸出明確的「買進/加碼/續抱/觀望/停損」建議

### v3.1 已經涵蓋的部分

| 功能 | 這個專案 | v3.1 |
|:---|:---:|:---:|
| 股價 + 技術指標（MA/RSI） | ✅ | ✅ |
| 三大法人買賣超 | ✅ | ✅ |
| 融資券 | ✅ | ✅ |
| 借券 | ✅ | ✅ |
| 大盤指數 | ✅ | ✅ |
| DeepSeek AI 分析 | ✅ | ✅ |
| 財報三表（損益/資產負債/現金流） | 僅損益表 | ✅ **完整三表** |
| 月營收 | ❌ | ✅ |
| 本益比歷史 | ❌ | ✅ |
| 股利 | ❌ | ✅ |
| 母表對齊機制 | ❌ | ✅ |
| 四風格評分 | ❌ | ✅ |

### 這個專案有但 v3.1 沒有的（可參考）

1. **大盤融資券總表**（MarginPurchaseShortSaleTotal）：v3.1 目前沒抓這個 dataset
2. **借券連續回補天數計算**：v3.1 有借券資料但沒算這個指標
3. **籌碼集中度**：（外資+投信+自營+權證）/ 總成交量
4. **操作建議邏輯**：多條件判斷輸出明確的買/賣/觀望建議
5. **Matplotlib 圖表**：靜態圖表，v3.1 目前用 Plotly

### 總結

> **v3.1 的資料涵蓋度遠大於這個專案**（多了資產負債表、現金流量表、月營收、本益比歷史、股利），但這個專案在**籌碼面分析**（大盤融資券總表、借券回補天數、籌碼集中度）和**操作建議邏輯**上有值得參考的地方。


