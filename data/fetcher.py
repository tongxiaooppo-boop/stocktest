"""
data/fetcher.py
FinMind API 呼叫（全撈取）
所有資料抓取集中在此模組，後續模組不得重複呼叫 API

注意：API Token 由前端傳入，不從 .env 讀取

FinMind 實際回傳欄位對照（2026年實測）：
  TaiwanStockPrice: date, stock_id, Trading_Volume, Trading_money, open, max, min, close, spread, Trading_turnover
  TaiwanStockInfo: industry_category, stock_id, stock_name, type, date
  財報三表（長格式）: date, stock_id, type, value, origin_name
  TaiwanStockDividend: date, stock_id, year, CashEarningsDistribution, ..., AnnouncementDate
"""

import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

FINMIND_BASE_URL = "https://api.finmindtrade.com/api/v4/data"
EVENT_THRESHOLD_PCT = 20.0


def _fetch_finmind(dataset: str, stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    """通用 FinMind API 呼叫"""
    time.sleep(1.5)
    params = {"dataset": dataset, "data_id": stock_id, "start_date": start_date, "end_date": end_date, "token": token}
    try:
        resp = requests.get(FINMIND_BASE_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == 200 and data.get("data"):
            return pd.DataFrame(data["data"])
        else:
            print(f"[FETCH_ERROR] {dataset}/{stock_id}: status={data.get('status')}, msg={data.get('msg','')}")
            return pd.DataFrame()
    except Exception as e:
        print(f"[FETCH_ERROR] {dataset}/{stock_id}: {e}")
        return pd.DataFrame()


def _normalize_price_columns(df: pd.DataFrame) -> pd.DataFrame:
    """標準化股價欄位名稱（max→high, min→low, Trading_Volume→volume）"""
    if df.empty: return df
    rename_map = {"max": "high", "min": "low", "Trading_Volume": "volume", "Trading_money": "trading_money"}
    return df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})


# 全域 PriceAdjuster 實例（延遲初始化，由 fetch_stock_price 傳入 token 後建立）
_price_adjuster = None

def _get_price_adjuster(token: str):
    """取得或建立 PriceAdjuster 實例"""
    global _price_adjuster
    from data.price_adjuster import PriceAdjuster
    if _price_adjuster is None:
        _price_adjuster = PriceAdjuster(token)
    return _price_adjuster


def _calc_adjusted_prices(token: str, stock_id: str, df: pd.DataFrame) -> pd.DataFrame:
    """
    使用 PriceAdjuster 計算還原股價（adj_close）
    
    基於 FinMind 官方事件資料（TaiwanStockSplitPrice、
    TaiwanStockCapitalReductionReferencePrice、TaiwanStockParValueChange）
    精確計算還原因子。
    
    保留原始 close 欄位不動。
    """
    if df.empty:
        return df
    
    adjuster = _get_price_adjuster(token)
    return adjuster.adjust(stock_id, df)


def fetch_stock_info(stock_id: str, token: str = "") -> pd.DataFrame:
    params = {"dataset": "TaiwanStockInfo", "data_id": stock_id, "token": token}
    try:
        resp = requests.get(FINMIND_BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == 200 and data.get("data"):
            return pd.DataFrame(data["data"])
    except Exception as e:
        print(f"[ERROR] fetch_stock_info: {e}")
    return pd.DataFrame()


def fetch_stock_price(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    """TaiwanStockPrice + adj_close 還原股價（基於 FinMind 官方事件資料）"""
    df = _fetch_finmind("TaiwanStockPrice", stock_id, start_date, end_date, token)
    df = _normalize_price_columns(df)
    df = _calc_adjusted_prices(token, stock_id, df)
    return df


def fetch_taiex_price(start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    df = _fetch_finmind("TaiwanStockPrice", "TAIEX", start_date, end_date, token)
    return _normalize_price_columns(df)


def fetch_institutional_investors(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    return _fetch_finmind("TaiwanStockInstitutionalInvestorsBuySell", stock_id, start_date, end_date, token)


def fetch_margin_purchase(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    return _fetch_finmind("TaiwanStockMarginPurchaseShortSale", stock_id, start_date, end_date, token)


def fetch_short_sale_balances(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    return _fetch_finmind("TaiwanDailyShortSaleBalances", stock_id, start_date, end_date, token)


def fetch_month_revenue(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    return _fetch_finmind("TaiwanStockMonthRevenue", stock_id, start_date, end_date, token)


def fetch_financial_statements(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    return _fetch_finmind("TaiwanStockFinancialStatements", stock_id, start_date, end_date, token)


def fetch_balance_sheet(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    return _fetch_finmind("TaiwanStockBalanceSheet", stock_id, start_date, end_date, token)


def fetch_cash_flows(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    return _fetch_finmind("TaiwanStockCashFlowsStatement", stock_id, start_date, end_date, token)


def fetch_dividend(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    return _fetch_finmind("TaiwanStockDividend", stock_id, start_date, end_date, token)


def fetch_per_history(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    return _fetch_finmind("TaiwanStockPER", stock_id, start_date, end_date, token)