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
from datetime import datetime, timedelta

FINMIND_BASE_URL = "https://api.finmindtrade.com/api/v4/data"


def _fetch_finmind(dataset: str, stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    """
    通用 FinMind API 呼叫
    
    Parameters:
        dataset: FinMind 資料集名稱
        stock_id: 股票代號
        start_date: 開始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)
        token: FinMind API Token（由前端傳入）
    
    Returns:
        DataFrame 或空的 DataFrame（若無資料或發生錯誤）
    """
    params = {
        "dataset": dataset,
        "data_id": stock_id,
        "start_date": start_date,
        "end_date": end_date,
        "token": token,
    }
    
    try:
        resp = requests.get(FINMIND_BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") == 200 and data.get("data"):
            return pd.DataFrame(data["data"])
        else:
            return pd.DataFrame()
    
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] FinMind API 呼叫失敗: {dataset} / {stock_id}: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"[ERROR] 未知錯誤: {dataset} / {stock_id}: {e}")
        return pd.DataFrame()


def _normalize_price_columns(df: pd.DataFrame) -> pd.DataFrame:
    """標準化股價欄位名稱（FinMind 用 max/min，統一為 high/low）"""
    if df.empty:
        return df
    rename_map = {
        "max": "high",
        "min": "low",
        "Trading_Volume": "volume",
        "Trading_money": "trading_money",
        "Trading_turnover": "trading_turnover",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    return df


def fetch_stock_info(stock_id: str, token: str = "") -> pd.DataFrame:
    """TaiwanStockInfo - 股票基本資料（名稱、產業別）"""
    params = {
        "dataset": "TaiwanStockInfo",
        "data_id": stock_id,
        "token": token,
    }
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
    """TaiwanStockPrice - 股價資料（開高低收量）"""
    df = _fetch_finmind("TaiwanStockPrice", stock_id, start_date, end_date, token)
    return _normalize_price_columns(df)


def fetch_taiex_price(start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    """TaiwanStockPrice - 大盤指數（TAIEX）"""
    df = _fetch_finmind("TaiwanStockPrice", "TAIEX", start_date, end_date, token)
    return _normalize_price_columns(df)


def fetch_institutional_investors(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    """TaiwanStockInstitutionalInvestorsBuySell - 三大法人買賣超"""
    return _fetch_finmind("TaiwanStockInstitutionalInvestorsBuySell", stock_id, start_date, end_date, token)


def fetch_margin_purchase(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    """TaiwanStockMarginPurchaseShortSale - 融資券"""
    return _fetch_finmind("TaiwanStockMarginPurchaseShortSale", stock_id, start_date, end_date, token)


def fetch_short_sale_balances(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    """TaiwanDailyShortSaleBalances - 借券"""
    return _fetch_finmind("TaiwanDailyShortSaleBalances", stock_id, start_date, end_date, token)


def fetch_month_revenue(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    """TaiwanStockMonthRevenue - 月營收"""
    return _fetch_finmind("TaiwanStockMonthRevenue", stock_id, start_date, end_date, token)


def fetch_financial_statements(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    """TaiwanStockFinancialStatements - 損益表（長格式：type/value/origin_name）"""
    return _fetch_finmind("TaiwanStockFinancialStatements", stock_id, start_date, end_date, token)


def fetch_balance_sheet(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    """TaiwanStockBalanceSheet - 資產負債表（長格式：type/value/origin_name）"""
    return _fetch_finmind("TaiwanStockBalanceSheet", stock_id, start_date, end_date, token)


def fetch_cash_flows(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    """TaiwanStockCashFlowsStatement - 現金流量表（長格式：type/value/origin_name）"""
    return _fetch_finmind("TaiwanStockCashFlowsStatement", stock_id, start_date, end_date, token)


def fetch_dividend(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    """TaiwanStockDividend - 股利"""
    return _fetch_finmind("TaiwanStockDividend", stock_id, start_date, end_date, token)


def fetch_per_history(stock_id: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    """TaiwanStockPER - 本益比歷史"""
    return _fetch_finmind("TaiwanStockPER", stock_id, start_date, end_date, token)


if __name__ == "__main__":
    # 測試區塊（需手動輸入 token）
    test_token = input("請輸入 FinMind Token: ").strip()
    if not test_token:
        print("請提供 FinMind Token 才能測試")
        exit(1)
    
    test_stock = "2330"
    test_end = datetime.now().strftime("%Y-%m-%d")
    test_start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    print(f"=== 測試抓取 {test_stock} 資料 ===")
    
    # 測試股價
    df_price = fetch_stock_price(test_stock, test_start, test_end, test_token)
    print(f"\n1. 股價資料: {len(df_price)} 筆")
    if not df_price.empty:
        print(df_price[["date", "open", "high", "low", "close", "volume"]].tail(5))
    
    # 測試大盤
    df_taiex = fetch_taiex_price(test_start, test_end, test_token)
    print(f"\n2. 大盤資料: {len(df_taiex)} 筆")
    if not df_taiex.empty:
        print(df_taiex[["date", "close", "spread", "trading_money"]].tail(3))
    
    # 測試股票資訊
    df_info = fetch_stock_info(test_stock, test_token)
    print(f"\n3. 股票資訊: {len(df_info)} 筆")
    if not df_info.empty:
        print(df_info[["stock_id", "stock_name", "industry_category"]].head())
    
    # 測試錯誤處理
    df_bad = fetch_stock_price("999999", test_start, test_end, test_token)
    print(f"\n4. 錯誤測試（不存在的股票）: {len(df_bad)} 筆（應為 0）")
