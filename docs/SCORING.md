# 四種投資風格評分細則

## 評分架構

- **版本**：v3.1
- **評分方式**：每個子項採 **五級評分**（Excellent=100, Good=85, Normal=70, Weak=50, Poor=0）
- **短線評分**：v3.0 起從 6 子項升級為 **8 子項**，新增慣性突破與籌碼密集區，並支援雙分析師人格（追熱門股 / 穩重型）
- **波段評分**：v3.1 修正 catalyst 子項，真正實作「營收創12個月新高」判斷，與 revenue_momentum 解耦
- **權重集中管理**：`core/scoring_config.py`

## Modifier 疊加順序（v2.1）

```
最終分數 = (base_score × DQ_Modifier) - Risk_Penalty + Risk_Bonus
最後用 np.clip(0, 100) 確保範圍
```

- **Data Quality Modifier**：≥8年×1.00, ≥5年×0.95, ≥3年×0.85, <3年×0.70
- **Risk Penalty**：負債過高 -10、EPS 為負 -15、盈餘品質不佳 -15
- **Risk Bonus**：RSI 超賣 +5、低負債 +5
- **Industry Debt Bias**（價值/定存）：負債比 > 同業中位數×1.2 打 85 折

> v2.1 變更：RSI 過熱扣分已移至 `score_volatility_risk` 子項，`apply_all_modifiers` 中不再重複扣分。

---

## 短線評分（v3.0 — 雙分析師 · 8 子項）

### 系統架構

短線評分從 v3.0 起支援兩種分析師人格，側邊欄可切換：
- **🔥 主動型（追熱門股 / chaser）**：重動能強度與慣性突破，適合強勢股追價
- **🛡️ 穩重型（stable）**：重趨勢結構與法人籌碼，適合盤整或保守進場

兩種人格共用相同的 8 個子項評分函式，但使用**獨立的買入/賣出權重表**計算總分。

### 8 子項說明

| 子項 | 函式 | 評分方式 |
|:---|:---|:---|
| trend_structure（趨勢結構） | `score_trend_structure()` | 均線排列（60%）+ 站上均線數量（40%） |
| momentum（動能強度） | `score_momentum()` | RSI(6) + Dist_High_5D 雙條件 |
| volume（成交量結構） | `score_volume_structure()` | Volume Ratio（60%）+ 爆量程度（40%） |
| institutional（法人籌碼） | `score_institutional()` | 5日法人（35%）+ 20日代理（25%）+ 外資（25%）+ 投信（15%） |
| chip（籌碼健康） | `score_chip_health()` | 融資變化（反）+ 融券變化 + 借券變化（反） |
| risk（波動風險） | `score_volatility_risk()` | Bias_5D + RSI 過熱判定 |
| **🆕 inertia_break（慣性突破）** | `score_inertia_break()` | 日K近10日高低點 + 連續漲跌天數判斷 |
| **🆕 chip_concentration（籌碼密集區）** | `score_chip_concentration()` | 60日收盤價×成交量加權分箱（POC 代理） |

### 追熱門股分析師權重表（chaser）

| 子項 | 買入 | 賣出 | 設計理念 |
|:---|:---:|:---:|:---|
| momentum（動能強度） | **30%** | 10% | 主軸不變：買看爆發、賣看是否真的失速 |
| inertia_break（慣性突破） | **25%** | **35%** | 短線核心，賣出權重最高（慣性反轉＝出場訊號） |
| volume（成交量結構） | 15% | 15% | 攻擊量 vs 爆量出貨 |
| trend_structure（趨勢結構） | 15% | 20% | 賣出更重視均線失守 |
| risk（波動風險） | 5% | 10% | 賣出時放大過熱權重，作停利觸發 |
| chip_concentration（籌碼密集區） | 5% | 5% | 短線參考，不作主要依據 |
| institutional（法人籌碼） | 5% | 5% | 大額籌碼監控 |
| chip（籌碼健康） | 0% | 0% | 追熱門股不看散戶 |
| **合計** | **100%** | **100%** | |

### 穩重型分析師權重表（stable）

| 子項 | 買入 | 賣出 | 設計理念 |
|:---|:---:|:---:|:---|
| trend_structure（趨勢結構） | **37%** | **37%** | 穩重型進出場核心 |
| institutional（法人籌碼） | **18%** | **23%** | 主要籌碼依據 |
| chip_concentration（籌碼密集區） | **15%** | **15%** | 支撐/壓力參考 |
| volume（成交量結構） | 10% | 10% | 常態監控 |
| inertia_break（慣性突破） | 5% | 10% | 賣出時提高，防範慣性轉空 |
| momentum（動能強度） | 5% | 5% | 不做短線動能決策 |
| chip（籌碼健康） | 5% | 0% | 買入評估籌碼沉澱，賣出不看 |
| risk（波動風險） | 5% | 0% | 不因過熱賣出 |
| **合計** | **100%** | **100%** | |

### 短線雙軌計算流程

```
get_all_scores(base, profile="chaser"|"stable")
    │
    └── score_short_term_by_profile(row, profile, price_history)
          ├── score_trend_structure(row)
          ├── score_momentum(row, rsi_limit)
          ├── score_volume_structure(row)
          ├── score_institutional(row)
          ├── score_chip_health(row)
          ├── score_volatility_risk(row, rsi_limit)
          ├── score_inertia_break(row)          ← 🆕 v3.0
          └── score_chip_concentration(row)     ← 🆕 v3.0
                    ↓
          sub_scores (8 keys)
                    ↓
          buy_total  = Σ(sub_scores[k] × STYLE_PROFILES[profile]["buy"][k])
          sell_total = Σ(sub_scores[k] × STYLE_PROFILES[profile]["sell"][k])
```

### 新增資料欄位（processor 負責生產）

| 欄位 | 用於 | 來源 |
|:---|:---|:---|
| `Low_10D` | score_inertia_break 判斷破底 | close.rolling(10).min() |
| `Consec_Up_Days` | score_inertia_break 判斷連續上漲 | close.diff().gt(0) 分組累加 |
| `Consec_Down_Days` | score_inertia_break 判斷連續下跌 | close.diff().lt(0) 分組累加 |
| `High_10D` | score_inertia_break 判斷突破前高 | close.rolling(10).max()（已於 v2 存在） |

> v2.1：20 日法人代理使用獨立 `inst_20d_surrogate_*` 門檻，不與 10 日共用。

---

## 波段評分（v3.1 修正 catalyst）

| 子項 | 權重 | 評分方式 |
|:---|:---:|:---|
| revenue_momentum（營收動能） | 25% | YoY 50% + MoM 25% + CAGR 25%（v4.2：有 CAGR 時 YoY 35% + CAGR 35%） |
| mid_trend（中期趨勢） | 20% | MA20 斜率 + 站上均線 |
| institutional_trend（籌碼趨勢） | 20% | Inst_Slope_20D 優先，Inst_20D_Net 備援 |
| earnings_growth（獲利成長） | 15% | TTM EPS 60% + EPS YoY 40% |
| valuation（估值位置） | 10% | PE 百分位（反）+ PB 百分位（反） |
| catalyst（催化因子） | 10% | 🆕 v3.1 獨立突破事件：Revenue_12M_High=100分, Revenue_6M_High=85分, YoY>30%=75分, 其他=70分 |

> v3.1：catalyst 真正實作「創12個月新高」判斷，與 revenue_momentum 的營收連續趨勢訊號完全解耦，避免重複計分。

### catalyst 評分邏輯（v3.1）

| 分數 | 條件 |
|:---:|:---|
| 100 | 最新單月營收創近12個月新高（突破性催化） |
| 85 | 最新單月營收創近6個月新高 |
| 75 | Revenue_YoY > 30%（強勁成長，但非創高突破） |
| 70 | 無明顯突破性催化因子（中性，不扣分） |

> 資料來源：`Revenue_12M_High`、`Revenue_6M_High` 由 `processor.build_universal_base_table` 在月營收處理階段用 rolling max 比較計算。

---

## 價值評分

| 子項 | 權重 | 評分方式 |
|:---|:---:|:---|
| valuation_safety（估值安全） | 15% | PE_TTM + PB 百分位雙條件 |
| profit_quality（獲利品質） | 20% | ROE_TTM + Gross_Margin 雙條件 |
| growth_ability（成長能力） | 30% | TTM EPS 60% + Revenue YoY 40% |
| financial_safety（財務安全） | 15% | 負債比（反）+ 流動比率 |
| cash_flow_quality（現金流品質） | 10% | TTM FCF + OCF |
| shareholder_return（股東報酬） | 10% | 殖利率 + 配息與否 |

> 金融業跳過 financial_safety + cash_flow_quality，權重等比例再分配。

---

## 定存評分

| 子項 | 權重 | 評分方式 |
|:---|:---:|:---|
| dividend_record（配息紀錄） | 25% | 連續配息年數 + 殖利率雙條件 |
| dividend_quality（配息品質） | 20% | 配息率區間 + EPS Cover |
| cash_flow（現金流） | 20% | Cash_Conv_Ratio + FCF 正數 |
| financial_safety（財務安全） | 15% | 負債比（反）+ 利息保障倍數 |
| profit_stability（獲利穩定） | 10% | ROE 波動（反）+ EPS 波動（反） |
| long_term_growth（長期成長） | 10% | 營收 CAGR + EPS YoY |

> 金融業跳過 cash_flow + financial_safety，權重等比例再分配。

---

## 相關文件

| 文件 | 說明 |
|:---|:---|
| `core/scoring_config.py` | 權重與門檻設定（單一事實來源） |
| `core/scorer.py` | 評分主程式 |
| `docs/短線評分程式實說.md` | 短線評分函式詳細實作說明（含 v3.0 雙分析師） |
| `docs/波段評分程式實說.md` | 波段評分函式詳細實作說明（含 v3.1 catalyst） |
| `docs/CHANGELOG.md` | 改版歷程 |

## 短線雙分析師 8 子項權重表（v3.0+）

### 追熱門股分析師（chaser）

| 子項 | 買入權重 | 賣出權重 |
|:---|:---:|:---:|
| 動能強度 (momentum) | 30% | 10% |
| 慣性突破 (inertia_break) | 25% | 35% |
| 成交量結構 (volume) | 15% | 15% |
| 趨勢結構 (trend_structure) | 15% | 20% |
| 波動風險 (risk) | 5% | 10% |
| 籌碼密集區 (chip_concentration) | 5% | 5% |
| 法人籌碼 (institutional) | 5% | 5% |
| 籌碼健康 (chip) | 0% | 0% |

### 穩重型分析師（stable）

| 子項 | 買入權重 | 賣出權重 |
|:---|:---:|:---:|
| 趨勢結構 (trend_structure) | 37% | 37% |
| 法人籌碼 (institutional) | 18% | 23% |
| 籌碼密集區 (chip_concentration) | 15% | 15% |
| 成交量結構 (volume) | 10% | 10% |
| 慣性突破 (inertia_break) | 5% | 10% |
| 動能強度 (momentum) | 5% | 5% |
| 籌碼健康 (chip) | 5% | 0% |
| 波動風險 (risk) | 5% | 0% |

### 新增子項說明

| 子項 | 特徵欄位 | 評分邏輯 |
|:---|:---|:---|
| **慣性突破** (inertia_break) | High_10D, Low_10D, Consec_Up_Days, Consec_Down_Days | 近 10 日高低點 + 連續漲跌天數，連漲 3 天且創 10 日新高 = 100 分 |
| **籌碼密集區** (chip_concentration) | close, volume（60 日） | 多日量價分布 POC 代理，當前價距密集區 5% 內 = 100 分 |

### 新增特徵欄位（processor 端）

| 欄位 | 來源 | 用途 |
|:---|:---|:---|
| Low_10D | calculate_derived_columns | 慣性突破：判斷是否跌破前 10 日低點 |
| Consec_Up_Days | calculate_derived_columns | 慣性突破：連續上漲天數 |
| Consec_Down_Days | calculate_derived_columns | 慣性突破：連續下跌天數 |
| Revenue_12M_High | build_universal_base_table + metrics | 波段 catalyst：營收創近 12 月新高 |
| Revenue_6M_High | build_universal_base_table + metrics | 波段 catalyst：營收創近 6 月新高 |

