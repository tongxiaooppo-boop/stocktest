"""
測試斷點 5-8（依 SCORING_STANDARDS_v1.0 規格）
只測 2330（台積電）
EPS（財報三表）及配股配息改為 10 年，其他不變
加上詳細評分過程說明
"""
import sys, time
sys.path.insert(0, 'd:/AI股票程式參考/TW Stock AI/taiwan-stock-analyzer-v3')
from data.fetcher import *
from data.processor import build_universal_base_table, calculate_derived_columns
from stock.metrics import calculate_technical_indicators, calculate_financial_indicators
from core.scorer import get_all_scores, get_style_label
from core.advisor import get_advice
from datetime import datetime, timedelta

TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidG9uZ3hpYW8ub3Bwb0BnbWFpbC5jb20iLCJlbWFpbCI6InRvbmd4aWFvLm9wcG9AZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.Ie0ysfHneXOaClcxG96Gi0c0cV1AxAZzuwchBbwi0fs'
END = datetime.now().strftime('%Y-%m-%d')
START_1Y = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
START_3Y = (datetime.now() - timedelta(days=3*365)).strftime('%Y-%m-%d')
START_10Y = (datetime.now() - timedelta(days=10*365)).strftime('%Y-%m-%d')

stock_id = "2330"
label = "台積電"
t0 = time.time()

print(f"{'='*60}")
print(f"=== {label} ({stock_id}) 評分過程分析 ===")
print(f"{'='*60}")

# ===== 1. 股價資料（近1年） =====
df_price = fetch_stock_price(stock_id, START_1Y, END, TOKEN)
print(f"\n【1. 股價資料撈取】近1年 ({START_1Y} ~ {END})")
print(f"   取得 {len(df_price)} 筆日資料")

# ===== 2. 籌碼資料（近1年） =====
df_inst = fetch_institutional_investors(stock_id, START_1Y, END, TOKEN)
df_margin = fetch_margin_purchase(stock_id, START_1Y, END, TOKEN)
df_ss = fetch_short_sale_balances(stock_id, START_1Y, END, TOKEN)
print(f"\n【2. 籌碼資料撈取】近1年")
print(f"   法人 {len(df_inst)} 筆 + 融資券 {len(df_margin)} 筆 + 借券 {len(df_ss)} 筆")

# ===== 3. 基本面（EPS/股利改為10年，營收維持3年） =====
df_rev = fetch_month_revenue(stock_id, START_3Y, END, TOKEN)
df_fin = fetch_financial_statements(stock_id, START_10Y, END, TOKEN)  # 10年
df_bal = fetch_balance_sheet(stock_id, START_10Y, END, TOKEN)         # 10年
df_cf = fetch_cash_flows(stock_id, START_10Y, END, TOKEN)             # 10年
df_div = fetch_dividend(stock_id, START_10Y, END, TOKEN)              # 10年
df_per = fetch_per_history(stock_id, START_1Y, END, TOKEN)
print(f"\n【3. 基本面撈取】")
print(f"   營收(3年): {len(df_rev)} 筆")
print(f"   損益表(10年): {len(df_fin)} 筆")
print(f"   資產負債表(10年): {len(df_bal)} 筆")
print(f"   現金流量表(10年): {len(df_cf)} 筆")
print(f"   股利(10年): {len(df_div)} 筆")
print(f"   PER(1年): {len(df_per)} 筆")

# ===== 4. 母表建構 =====
print(f"\n【4. 母表建構】")
base = build_universal_base_table(df_price, df_rev, df_fin, df_bal, df_cf, df_div, df_per, df_inst, df_margin, df_ss)
print(f"   原始母表: {len(base)} 筆 x {len(base.columns)} 欄位")

result = calculate_derived_columns(base)
print(f"   計算衍生欄位後: {len(result)} 筆 x {len(result.columns)} 欄位")
print(f"   包含: MA_5/10/20/60, Vol_MA_5, Revenue_YoY, TTM_EPS, TTM_FCF, PE/PB_Percentile")

# ===== 5. 技術指標 =====
tech = calculate_technical_indicators(result)
print(f"\n【5. 技術指標計算】")
print(f"   新增: RSI_6, MA_Alignment, Volume_Ratio, Inst_5D/20D_Net, Chip_Divergence, MA60_Bias, Revenue_Momentum")

# ===== 6. 財務指標 =====
fin = calculate_financial_indicators(tech)
print(f"\n【6. 財務指標計算】")
print(f"   新增: ROE_TTM, Gross_Margin, Debt_Ratio, Payout_Ratio, FCF_Coverage, Dividend_Continuity_Years")

# ===== 7. 評分過程 =====
latest = fin.iloc[-1]
print(f"\n{'='*60}")
print(f"【7. 評分過程（最新交易日: {latest.get('date', 'N/A')}）】")
print(f"{'='*60}")

# --- 短線評分 ---
print(f"\n--- 短線評分 ---")
ma_al = latest.get("MA_Alignment", 0)
print(f"  ① 均線多頭排列 (權重30)")
print(f"     MA_Alignment = {ma_al} (close>MA5>MA10>MA20 滿足 {ma_al}/3 項)")
s_ma = 30 if ma_al >= 3 else (18 if ma_al >= 2 else (8 if ma_al >= 1 else 0))
print(f"     → 得分: {s_ma}")

vol_r = latest.get("Volume_Ratio", 0)
print(f"  ② 量能配合 (權重25)")
print(f"     Volume_Ratio = {vol_r:.2f} (成交量/5日均量)")
if pd.notna(vol_r):
    if vol_r >= 1.5: s_vol = 25
    elif vol_r >= 1.2: s_vol = 15
    elif vol_r >= 1.0: s_vol = 8
    else: s_vol = 0
else:
    s_vol = 0
print(f"     → 得分: {s_vol}")

inst5 = latest.get("Inst_5D_Net", 0)
print(f"  ③ 法人籌碼方向 (權重25)")
print(f"     Inst_5D_Net = {inst5:.0f} (法人5日累計)")
s_inst = 25 if (pd.notna(inst5) and inst5 > 0) else 0
print(f"     → 得分: {s_inst}")

chip = latest.get("Chip_Divergence", 0)
margin5 = latest.get("Margin_5D_Change", 0)
short5 = latest.get("Short_5D_Change", 0)
print(f"  ④ 資券健康度 (權重20)")
print(f"     Chip_Divergence={chip}, Margin_5D_Change={margin5:.0f}, Short_5D_Change={short5:.0f}")
if pd.notna(chip) and chip > 0:
    s_margin = 0
elif pd.notna(margin5) and pd.notna(short5) and margin5 > 0 and short5 < 0:
    s_margin = 20
elif pd.notna(margin5) and pd.notna(short5) and (margin5 > 0 or short5 < 0):
    s_margin = 10
else:
    s_margin = 10
print(f"     → 得分: {s_margin}")

short_total = s_ma + s_vol + s_inst + s_margin
rsi6 = latest.get("RSI_6", 0)
print(f"  短線原始總分: {short_total}")
if pd.notna(rsi6) and rsi6 > 85:
    short_total = int(short_total * 0.7)
    print(f"  RSI_6={rsi6:.1f} > 85, 過熱折扣0.7 → 最終: {short_total}")
else:
    print(f"  RSI_6={rsi6:.1f}, 無過熱折扣 → 最終: {short_total}")

# --- 波段評分 ---
print(f"\n--- 波段評分 ---")
momentum = latest.get("Revenue_Momentum", 0)
rev_yoy = latest.get("Revenue_YoY", 0)
print(f"  ① 營收動能 (權重35)")
print(f"     Revenue_Momentum={momentum}, Revenue_YoY={rev_yoy:.2f}")
if pd.notna(momentum) and momentum > 0:
    s_rev = 35
elif pd.notna(rev_yoy) and rev_yoy > 0:
    s_rev = 20
else:
    s_rev = 0
print(f"     → 得分: {s_rev}")

close = latest.get("close", 0)
ma60 = latest.get("MA_60", 0)
bias = latest.get("MA60_Bias", 0)
print(f"  ② 均線位置 (權重25)")
print(f"     close={close:.1f}, MA_60={ma60:.1f}, MA60_Bias={bias:.4f}")
if pd.notna(close) and pd.notna(ma60) and pd.notna(bias) and close > ma60:
    if 0 <= bias <= 0.15:
        s_ma60 = 25
    elif bias > 0.15:
        s_ma60 = 10
    else:
        s_ma60 = 0
else:
    s_ma60 = 0
print(f"     → 得分: {s_ma60}")

inst20 = latest.get("Inst_20D_Net", 0)
print(f"  ③ 中期籌碼 (權重25)")
print(f"     Inst_20D_Net={inst20:.0f}")
s_inst20 = 25 if (pd.notna(inst20) and inst20 > 0) else 0
print(f"     → 得分: {s_inst20}")

diverg = latest.get("Price_Revenue_Divergence", 0)
print(f"  ④ 背離扣分 (權重15)")
print(f"     Price_Revenue_Divergence={diverg}")
s_div = 15 if (pd.isna(diverg) or diverg == 0) else 0
print(f"     → 得分: {s_div}")

swing_total = s_rev + s_ma60 + s_inst20 + s_div
print(f"  波段總分: {swing_total}")

# --- 價值評分 ---
print(f"\n--- 價值評分 ---")
pe_pct = latest.get("PE_Percentile", None)
pb_pct = latest.get("PB_Percentile", None)
ttm_eps_v = latest.get("TTM_EPS_Valid", True)
print(f"  ① 估值安全邊際 (權重30)")
print(f"     PE_Percentile={pe_pct}, PB_Percentile={pb_pct}, TTM_EPS_Valid={ttm_eps_v}")
if pd.notna(ttm_eps_v) and not ttm_eps_v:
    pct = pb_pct
else:
    pct = pe_pct
if pd.isna(pct):
    s_val = 0
elif pct < 20: s_val = 30
elif pct < 40: s_val = 20
elif pct < 60: s_val = 10
else: s_val = 0
print(f"     → 得分: {s_val}")

roe = latest.get("ROE_TTM", 0)
roe_std = latest.get("ROE_Stability", 999)
print(f"  ② 獲利能力穩定性 (權重25)")
print(f"     ROE_TTM={roe:.2f}%, ROE_Stability={roe_std:.2f}")
if pd.notna(roe):
    if roe > 15 and pd.notna(roe_std) and roe_std < 5:
        s_roe = 25
    elif roe > 10:
        s_roe = 15
    else:
        s_roe = 5
else:
    s_roe = 5
print(f"     → 得分: {s_roe}")

gm_std = latest.get("Gross_Margin_Stability", 999)
print(f"  ③ 毛利穩定性 (權重20)")
print(f"     Gross_Margin_Stability={gm_std:.2f}")
if pd.isna(gm_std):
    s_gm = 0
elif gm_std < 3: s_gm = 20
elif gm_std < 6: s_gm = 10
else: s_gm = 0
print(f"     → 得分: {s_gm}")

debt = latest.get("Debt_Ratio", 100)
print(f"  ④ 財務結構 (權重15)")
print(f"     Debt_Ratio={debt:.2f}%")
if pd.isna(debt):
    s_debt = 0
elif debt < 40: s_debt = 15
elif debt < 60: s_debt = 8
else: s_debt = 0
print(f"     → 得分: {s_debt}")

fcf_div = latest.get("FCF_vs_Dividend", 0)
print(f"  ⑤ 現金流覆蓋 (權重10)")
print(f"     FCF_vs_Dividend={fcf_div:.2f}")
s_fcf = 10 if (pd.notna(fcf_div) and fcf_div > 0) else 0
print(f"     → 得分: {s_fcf}")

value_total = s_val + s_roe + s_gm + s_debt + s_fcf
data_years = latest.get("Data_Years_Available", 10)
if pd.isna(data_years): data_years = 10
print(f"  價值原始總分: {value_total}")
if data_years < 5:
    value_total = int(value_total * 0.8)
    print(f"  Data_Years_Available={data_years} < 5, 折扣0.8 → 最終: {value_total}")
else:
    print(f"  Data_Years_Available={data_years}, 無折扣 → 最終: {value_total}")

# --- 定存評分 ---
print(f"\n--- 定存評分 ---")
div_years = latest.get("Dividend_Continuity_Years", 0)
print(f"  ① 配息連續性 (權重35)")
print(f"     Dividend_Continuity_Years={div_years}, Data_Years_Available={data_years}")
if pd.notna(div_years) and pd.notna(data_years):
    if div_years >= data_years: s_divc = 35
    elif div_years >= data_years - 1: s_divc = 15
    else: s_divc = 0
else:
    s_divc = 0
print(f"     → 得分: {s_divc}")

payout = latest.get("Payout_Ratio", None)
payout_std = latest.get("Payout_Ratio_Stability", 999)
print(f"  ② 配息率健康度 (權重25)")
print(f"     Payout_Ratio={payout}, Payout_Ratio_Stability={payout_std:.2f}")
if pd.isna(payout):
    s_pay = 0
else:
    in_range = (50 <= payout <= 80) if pd.notna(payout) else False
    stable = pd.notna(payout_std) and payout_std < 10
    if in_range and stable: s_pay = 25
    elif in_range: s_pay = 15
    else: s_pay = 5
print(f"     → 得分: {s_pay}")

coverage = latest.get("FCF_Coverage", 0)
print(f"  ③ 現金流覆蓋 (權重25)")
print(f"     FCF_Coverage={coverage:.2f}")
if pd.isna(coverage):
    s_cov = 0
elif coverage > 1.5: s_cov = 25
elif coverage > 1.0: s_cov = 15
else: s_cov = 0
print(f"     → 得分: {s_cov}")

debt_trend = latest.get("Debt_Ratio_Trend", 0)
print(f"  ④ 財務結構趨勢 (權重15)")
print(f"     Debt_Ratio_Trend={debt_trend:.2f}")
if pd.isna(debt_trend):
    s_dt = 0
elif debt_trend < 0: s_dt = 15
elif debt_trend < 5: s_dt = 8
else: s_dt = 0
print(f"     → 得分: {s_dt}")

div_total = s_divc + s_pay + s_cov + s_dt
if data_years < 5:
    div_total = int(div_total * 0.8)
    print(f"  Data_Years_Available={data_years} < 5, 折扣0.8 → 最終: {div_total}")
else:
    print(f"  Data_Years_Available={data_years}, 無折扣 → 最終: {div_total}")

# ===== 8. 最終結果 =====
print(f"\n{'='*60}")
print(f"【8. 最終評分結果】")
print(f"{'='*60}")
print(f"  短線: {short_total}分")
print(f"  波段: {swing_total}分")
print(f"  價值: {value_total}分")
print(f"  定存: {div_total}分")

scores = get_all_scores(fin)
advice = get_advice(scores)
print(f"\n  基本建議: {advice['advice']}")
print(f"  最適合風格: {get_style_label(advice['best_style'])} ({advice['best_score']}分)")
print(f"\n  總耗時: {time.time()-t0:.1f}秒")
print(f"{'='*60}")
