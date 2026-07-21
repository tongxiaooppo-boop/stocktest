"""
ui/components.py — 共用元件
FIELD_CN_MAP 中英欄位對照、cn() 翻譯函數、_radar_chart() 雷達圖繪製
"""
import matplotlib.pyplot as plt


# ===== 中英欄位對照表（用於細目中文顯示 + 除錯面板） =====
FIELD_CN_MAP = {
    # 技術面
    "close": "收盤價",
    "volume": "成交量",
    "MA_5": "5日均線",
    "MA_10": "10日均線",
    "MA_20": "20日均線",
    "MA_60": "60日均線",
    "High_5D": "5日最高價",
    "High_10D": "10日最高價",
    "High_20D": "20日最高價",
    "Vol_MA_5": "5日均量",
    "RSI_6": "6日RSI",
    "MA_Alignment": "均線排列",
    "Volume_Ratio": "量比",
    "MA60_Bias": "60日乖離率",
    "ATR": "平均真實波幅",
    "Above_MA_5": "站上5日線",
    "Above_MA_10": "站上10日線",
    "Above_MA_20": "站上20日線",
    "Above_MA_60": "站上60日線",
    "Bullish_MA": "多頭排列",
    "Volume_Above_MA5": "量站上5日均量",
    "Low_10D": "10日最低價",
    "Consec_Up_Days": "連續上漲天數",
    "Consec_Down_Days": "連續下跌天數",
    # 籌碼面
    "Foreign_Net": "外資買賣超",
    "Trust_Net": "投信買賣超",
    "Dealer_Net": "自營商買賣超",
    "Inst_Net": "三大法人合計",
    "Inst_5D_Net": "法人5日累計",
    "Inst_20D_Net": "法人20日累計",
    "Chip_Divergence": "籌碼背離",
    "Margin_5D_Change": "融資5日變化",
    "Short_5D_Change": "融券5日變化",
    "SBL_5D_Change": "借券5日變化",
    "Inst_Consecutive_Days": "法人連續天數",
    # 基本面
    "month_revenue": "月營收",
    "revenue_year": "營收年度",
    "revenue_month": "營收月份",
    "Revenue_YoY": "營收年增率",
    "Revenue_MoM": "營收月增率",
    "Revenue_Accelerating": "營收加速",
    "Revenue_Momentum": "營收動能",
    "Revenue_12M_High": "營收創12月新高",
    "Revenue_6M_High": "營收創6月新高",
    "Price_Revenue_Divergence": "價量背離",
    "TTM_EPS": "近四季EPS",
    "TTM_EPS_Valid": "EPS有效性",
    "TTM_FCF": "近四季自由現金流",
    "TTM_OCF": "近四季營業現金流",
    "TTM_OperatingCF": "近四季營業現金流",
    "TTM_CAPEX": "近四季資本支出",
    "TTM_NetIncome": "近四季稅後淨利",
    "ROE_TTM": "近四季ROE",
    "ROE_Stability": "ROE穩定度",
    "ROA_TTM": "近四季ROA",
    "Gross_Margin": "毛利率",
    "Gross_Margin_Stability": "毛利率穩定度",
    "Operating_Margin": "營業利益率",
    "Current_Ratio": "流動比率",
    "Interest_Coverage": "利息保障倍數",
    "EPS_Stability": "EPS穩定度",
    "EPS_YoY": "EPS年成長率",
    "EPS_YoY_Reason": "EPS成長率原因",
    "Debt_Ratio": "負債比",
    "Debt_Ratio_Trend": "負債比趨勢",
    "PE_Percentile": "本益比百分位",
    "PB_Percentile": "股價淨值比百分位",
    "pe_ratio": "本益比",
    "pb_ratio": "股價淨值比",
    "dividend_yield": "殖利率",
    "cash_dividend_total": "現金股利總額",
    "cash_dividend": "現金股利",
    "cash_statutory": "法定盈餘公積",
    "Payout_Ratio": "配息率",
    "Payout_Ratio_Stability": "配息率穩定度",
    "FCF_Coverage": "FCF覆蓋率",
    "FCF_vs_Dividend": "FCF/股利比",
    "Dividend_Continuity_Years": "連續配息年數",
    "Data_Years_Available": "資料可用年數",
    # 評分相關
    "trend_score": "趨勢評分",
    "momentum_score": "動能評分",
    "volume_score": "量能評分",
    "inst_score": "法人評分",
    "chip_score": "籌碼評分",
    "risk_score": "風險評分",
    "revenue_score": "營收評分",
    "mid_trend_score": "中期趨勢評分",
    "inst_trend_score": "籌碼趨勢評分",
    "earnings_score": "獲利評分",
    "valuation_score": "估值評分",
    "catalyst_score": "催化評分",
    "valuation_safety_score": "估值安全評分",
    "profit_quality_score": "獲利品質評分",
    "growth_score": "成長評分",
    "financial_safety_score": "財務安全評分",
    "cash_flow_quality_score": "現金流品質評分",
    "shareholder_return_score": "股東報酬評分",
    "dividend_record_score": "配息紀錄評分",
    "dividend_quality_score": "配息品質評分",
    "cash_flow_score": "現金流評分",
    "profit_stability_score": "獲利穩定評分",
    "long_term_growth_score": "長期成長評分",
    # 短線細項原始資料（sub_details）
    "ma_alignment": "均線排列",
    "ma_alignment_score": "均線排列評分",
    "above_ma_count": "站上均線數",
    "above_ma_score": "站上均線評分",
    "rsi": "RSI(6)",
    "dist_high_5d": "距高點比例",
    "break_low_5d": "破底(5日)",
    "macd_positive": "MACD柱正",
    "volume_ratio": "量比",
    "volume_ratio_score": "量比評分",
    "surge_score": "爆量評分",
    "inst_5d_net": "法人5日淨額",
    "inst_5d_score": "法人5日評分",
    "inst_20d_score": "法人20日評分",
    "inst_20d_is_proxy": "20日為代理",
    "foreign_score": "外資評分",
    "trust_score": "投信評分",
    "margin_5d_change": "融資5日變化",
    "margin_score": "融資評分",
    "short_5d_change": "融券5日變化",
    "short_score": "融券評分",
    "sbl_score": "借券評分",
    "bias_5d": "5日乖離率",
    # note 類
    "note": "備註",
    # 波段細項原始資料（revenue_momentum）
    "revenue_yoy": "營收年增率",
    "yoy_score": "年增率評分",
    "mom_score": "月增率評分",
    "accel_score": "加速度評分",
    "cagr_1_5y": "1.5年CAGR",
    "cagr_score": "CAGR評分",
    # 波段細項（mid_trend）
    "above_ma20": "站上20MA",
    "above_ma60": "站上60MA",
    "ma20_slope": "20MA斜率",
    # 波段細項（institutional_trend）
    "inst_slope_20d": "法人20日斜率",
    "inst_20d_net": "法人20日淨額",
    # 波段細項（earnings_growth）
    "ttm_eps": "近四季EPS",
    "eps_score": "EPS評分",
    "eps_yoy": "EPS年成長率",
    "eps_yoy_score": "EPS年增評分",
    "eps_yoy_available": "EPS年增可用",
    "eps_yoy_note": "EPS年增備註",
    # 波段細項（valuation）
    "pe_percentile": "本益比百分位",
    "pe_score": "本益比評分",
    "pb_percentile": "淨值比百分位",
    "pb_score": "淨值比評分",
    # 波段細項（catalyst）
    "revenue_momentum": "營收動能",
    "catalyst_score": "催化評分",
    # 價值細項（valuation_safety）
    "pe_ttm": "本益比(TTM)",
    # 價值細項（profit_quality）
    "roe": "ROE",
    "gross_margin": "毛利率",
    # 價值細項（growth_ability）
    "rev_score": "營收評分",
    # 價值細項（financial_safety）
    "debt_ratio": "負債比",
    "debt_score": "負債比評分",
    "current_ratio": "流動比率",
    "cr_score": "流動比率評分",
    # 價值細項（cash_flow_quality）
    "ttm_fcf": "近四季FCF",
    "fcf_score": "FCF評分",
    "ocf_score": "營運現金流評分",
    # 價值細項（shareholder_return）
    "dividend_yield": "殖利率",
    "yield_score": "殖利率評分",
    "dividend": "現金股利",
    "div_score": "股利評分",
    # 定存細項（dividend_record）
    "dividend_continuity_years": "連續配息年數",
    # 定存細項（dividend_quality）
    "payout_ratio": "配息率",
    "eps_cover": "EPS覆蓋率",
    # 定存細項（cash_flow）
    "cash_conv_ratio": "現金轉換率",
    "fcf_positive": "FCF正數",
    # 定存細項（financial_safety）
    "interest_coverage": "利息保障倍數",
    "ic_score": "利息保障評分",
    # 定存細項（profit_stability）
    "roe_std": "ROE標準差",
    "eps_std": "EPS標準差",
    # 定存細項（long_term_growth）
    "rev_cagr": "營收CAGR",
    # modifier 相關
    "data_quality": "資料品質",
    "data_years": "資料年數",
    "modifier": "調整係數",
    "adjusted_score": "調整後分數",
    "finance_redistribution": "金融業權重再分配",
}

def cn(val: str) -> str:
    """將英文欄位名稱轉為中文，若無對照則保留原文"""
    return FIELD_CN_MAP.get(val, val)


def _radar_chart(labels: list, values: list, title: str, color: str,
                 label_weights: list = None) -> plt.Figure:
    """繪製六邊形雷達圖（支援 6 子項）"""
    import numpy as np
    N = len(labels)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]
    values_closed = values + values[:1]
    
    fig, ax = plt.subplots(figsize=(3.8, 3.8), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    
    for level in [20, 40, 60, 80, 100]:
        ax.plot(angles, [level] * len(angles), color='gray', linestyle='--', linewidth=0.5, alpha=0.3)
    ax.plot(angles, [0] * len(angles), color='gray', linewidth=0.5, alpha=0.5)
    
    ax.fill(angles, values_closed, alpha=0.15, color=color)
    ax.plot(angles, values_closed, color=color, linewidth=2)
    
    if label_weights:
        tick_labels = [f"{l}\n({w}%)" for l, w in zip(labels, label_weights)]
    else:
        tick_labels = labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(tick_labels, fontsize=8, fontweight='bold')
    
    ax.set_ylim(0, 105)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=7)
    
    ax.set_title(title, fontsize=12, fontweight='bold', pad=18, color=color)
    plt.tight_layout()
    return fig