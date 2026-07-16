# 四種投資風格評分細則

## 評分架構

- **版本**：v2.1
- **評分方式**：每個子項採 **五級評分**（Excellent=100, Good=85, Normal=70, Weak=50, Poor=0）
- **權重**：每個風格各有 **6 個子項**，權重總和 100%
- **門檻集中管理**：`core/scoring_config.py`

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

## 短線評分

| 子項 | 權重 | 評分方式 |
|:---|:---:|:---|
| trend_structure（趨勢結構） | 20% | 均線排列（60%）+ 站上均線數量（40%） |
| momentum（動能強度） | 20% | RSI(6) + Dist_High_5D 雙條件 |
| volume（成交量結構） | 20% | Volume Ratio（60%）+ 爆量程度（40%） |
| institutional（法人籌碼） | 15% | 5日法人（35%）+ 20日代理（25%）+ 外資（25%）+ 投信（15%） |
| chip（籌碼健康） | 15% | 融資變化（反）+ 融券變化 + 借券變化（反） |
| risk（波動風險） | 10% | Bias_5D + RSI 過熱判定 |

> v2.1：20 日法人代理使用獨立 `inst_20d_surrogate_*` 門檻，不與 10 日共用。

---

## 波段評分

| 子項 | 權重 | 評分方式 |
|:---|:---:|:---|
| revenue_momentum（營收動能） | 25% | YoY 50% + MoM 25% + CAGR 25% |
| mid_trend（中期趨勢） | 20% | MA20 斜率 + 站上均線 |
| institutional_trend（籌碼趨勢） | 20% | Inst_Slope_20D 優先，Inst_20D_Net 備援 |
| earnings_growth（獲利成長） | 15% | TTM EPS 60% + EPS YoY 40% |
| valuation（估值位置） | 10% | PE 百分位（反）+ PB 百分位（反） |
| catalyst（催化因子） | 10% | 突破性事件判定：營收連續成長→100 分，其餘→70 分 |

> v2.1：catalyst 改為「突破性事件」邏輯，與 revenue_momentum 的定量階梯區隔。

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

---

## 金融業特殊處理

| 風格 | 跳過子項 | 權重再分配 |
|:---|:---|:---|
| 價值 | financial_safety, cash_flow_quality | 其餘 4 子項等比例放大 |
| 定存 | cash_flow, financial_safety | 其餘 4 子項等比例放大 |