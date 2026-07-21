# 波段評分 `score_catalyst()` 修正計畫書

> 結論：波段（swing）6 個子項與買賣雙軌權重（`SWING_BUY_WEIGHTS` / `SWING_SELL_WEIGHTS`）
> 架構已完整，**權重表不需調整**，也不需要比照短線做雙分析師改造。
> 本計畫僅修正 `score_catalyst()` 這一個函式的實作 bug，屬小範圍修正。

---

## 1. 問題描述

`core/scorer.py` 中 `score_catalyst()` 的 docstring 承諾：

> 若「最新單月營收創近 12 個月新高」→ 100 分

但**實際程式碼從未實作這個判斷**。目前邏輯只檢查 `Revenue_Momentum >= 1 或 3` 與
`Revenue_YoY > 30`，而這兩個欄位跟同一個檔案裡的 `score_revenue_momentum()` 子項用的
是**同一份原始資料**。

造成兩個問題：
1. **文件承諾的功能是空的**——「創12個月新高」這個判斷實際上不存在。
2. **重複計分**：`revenue_momentum`（買入權重25%）與 `catalyst`（買入權重15%）本質上
   都在吃 `Revenue_Momentum`/`Revenue_YoY` 同一份訊號，等於「營收動能」這一個因子的
   買入端話語權被放大到 40%，擠壓了估值、法人趨勢等其他子項該有的鑑別度。

---

## 2. 修正方案

把 `catalyst` 從「重複判斷營收動能」改為「真正獨立的離散突破事件」——
用**近 12 個月 / 6 個月營收是否創新高**做核心判斷，這是跟 `revenue_momentum`
（判斷連續性趨勢）不同維度的訊號，兩者不再重疊。

### 2.1 評分邏輯（新版）

| 分數 | 條件 |
|---|---|
| 100 | 最新單月營收創近 12 個月新高（真正的突破事件） |
| 85 | 最新單月營收創近 6 個月新高（次一級突破） |
| 75 | 未創高，但 Revenue_YoY > 30%（強勁成長，非突破） |
| 70 | 無明顯突破性催化因子（中性，維持原設計不扣分） |

### 2.2 資料來源

`Revenue_12M_High`、`Revenue_6M_High` 皆可由 **TaiwanStockMonthRevenue（Free）**
的歷史月營收序列計算：

```
Revenue_12M_High = (本月營收 == 近12個月營收的最大值)
Revenue_6M_High  = (本月營收 == 近6個月營收的最大值)
```

不需要新增 FinMind API 呼叫，只是把既有月營收欄位多做一次 rolling max 比較。

---

## 3. 前置作業：processor 需新增欄位

在資料前處理階段（月營收處理模組）新增：

```python
# 假設 monthly_revenue 為依日期排序的月營收序列
df["Revenue_12M_High"] = df["revenue"] >= df["revenue"].rolling(12, min_periods=1).max()
df["Revenue_6M_High"]  = df["revenue"] >= df["revenue"].rolling(6, min_periods=1).max()
```

> 注意：用 `>=` 而非 `==`，避免浮點數比較誤差；`min_periods=1` 讓資料不足 12/6 個月時
> 仍可運算（此時等同於「至今最高」，不會因為資料不足而整批判 False）。

---

## 4. `core/scorer.py` 程式碼異動

```python
def score_catalyst(row) -> dict:
    """
    催化因子評分（權重：買15% / 賣10%，權重表不變）

    v3.1 修正：
    - 真正實作「近12個月新高」判斷（原 docstring 承諾但程式碼未實作的部分）
    - 與 revenue_momentum 解耦：不再重複讀取 Revenue_Momentum/Revenue_YoY 的
      連續趨勢訊號，改以「創新高」這種離散突破事件為核心判斷依據，
      避免和 revenue_momentum 子項重複計分同一份原始資料
    """
    revenue_12m_high = row.get("Revenue_12M_High", None)  # bool，由 processor 提供
    revenue_6m_high = row.get("Revenue_6M_High", None)    # bool，由 processor 提供
    rev_yoy = row.get("Revenue_YoY", None)

    if revenue_12m_high is True:
        score = 100
        note = "最新單月營收創近12個月新高（突破性催化）"
    elif revenue_6m_high is True:
        score = 85
        note = "最新單月營收創近6個月新高"
    elif pd.notna(rev_yoy) and rev_yoy > 30:
        score = 75
        note = "營收YoY > 30%，強勁成長，但非創高突破"
    else:
        score = 70
        note = "無明顯突破性催化因子"

    return {
        "score": score,
        "details": {
            "revenue_12m_high": revenue_12m_high,
            "revenue_6m_high": revenue_6m_high,
            "rev_yoy": round(rev_yoy, 2) if pd.notna(rev_yoy) else None,
            "note": note,
        }
    }
```

**`score_swing()` 呼叫端與 `SWING_BUY_WEIGHTS` / `SWING_SELL_WEIGHTS` 完全不用改**，
`catalyst` 這個 key 的權重（買15% / 賣10%）維持原樣，只有子項內部運算邏輯改變。

---

## 5. 相容性與風險

- **不影響其他子項**：只改 `score_catalyst()` 內部，`score_revenue_momentum()`、
  `score_mid_trend()` 等其他 5 個子項完全不動。
- **權重表不變**：`SWING_WEIGHTS` / `SWING_BUY_WEIGHTS` / `SWING_SELL_WEIGHTS` 不需修改。
- **既有回測會有分數位移**：`get_historical_scores()` 走過的歷史資料，凡是原本靠
  `Revenue_Momentum >= 1` 就拿 100 分的個股，修正後如果沒有實際創新高，可能會掉到
  70~85 分，屬於**預期中的修正結果**（原本是虛胖分數），但若有下游系統依賴舊分數做比較，
  建議上線前先跑一次新舊版本對照，確認總分變化幅度在可接受範圍。
- **資料缺口防呆**：若 processor 因故未提供 `Revenue_12M_High`/`Revenue_6M_High`
  （例如新股上市不滿12個月），`row.get(..., None)` 會回傳 `None`，程式會自動 fallback
  到 `rev_yoy > 30` 或中性 70 分，不會噴錯。

---

## 6. 測試案例

| 情境 | 預期分數 |
|---|---|
| `Revenue_12M_High=True` | 100 |
| `Revenue_12M_High=False, Revenue_6M_High=True` | 85 |
| `Revenue_12M_High=False, Revenue_6M_High=False, Revenue_YoY=35` | 75 |
| 三者皆 False/None | 70 |
| `Revenue_12M_High=None`（資料不足），`Revenue_YoY=None` | 70（fallback 中性分） |
| 新股上市僅3個月，`Revenue_6M_High` 用 `min_periods=1` 算出 True | 85（不因資料不足被誤判為 False） |

---

## 7. Cline 實作步驟清單

1. 在月營收 processor 模組，新增 `Revenue_12M_High`、`Revenue_6M_High` 兩個布林欄位
   （第 3 節程式碼），確保這兩欄位會被送進 `score_swing()` 呼叫時用的 `row`/`row_dict`。
2. 用第 4 節的新版 `score_catalyst()` 覆蓋 `core/scorer.py` 中的舊版函式，其餘程式碼不動。
3. 執行第 6 節測試案例，確認各情境分數符合預期。
4. 對既有歷史資料跑一次 `get_historical_scores()`，比較修正前後 `swing_score` /
   `swing_score_buy` / `swing_score_sell` 的分數分布，確認變化幅度合理（預期普遍
   略降，因為移除了虛胖的重複計分）。
5. 若下游（前端/報表/選股清單）有寫死假設 catalyst 高分等於營收連續成長的邏輯，
   一併檢查是否需要同步調整說明文字。
