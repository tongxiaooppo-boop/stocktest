"""
utils/helpers.py
金鑰驗證、錯誤處理、日期格式化

注意：API Key 由前端網頁輸入，此模組不從 .env 讀取金鑰
"""

from datetime import datetime, timedelta


def validate_api_keys(finmind_token: str = "", deepseek_key: str = "") -> dict:
    """
    驗證使用者輸入的 API Key 是否為空
    
    Parameters:
        finmind_token: 使用者輸入的 FinMind Token
        deepseek_key: 使用者輸入的 DeepSeek API Key
    
    Returns:
        dict: {"finmind_ok": bool, "deepseek_ok": bool}
    """
    return {
        "finmind_ok": bool(finmind_token),
        "deepseek_ok": bool(deepseek_key),
    }


def get_default_date_range(years: int = 3) -> tuple:
    """
    取得預設日期範圍
    
    Parameters:
        years: 往回幾年
    
    Returns:
        (start_date, end_date) 字串格式 YYYY-MM-DD
    """
    end = datetime.now()
    start = end - timedelta(days=years * 365)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def format_number(num: float, decimals: int = 2) -> str:
    """
    格式化數字為台灣常用顯示方式
    
    Parameters:
        num: 數字
        decimals: 小數位數
    
    Returns:
        格式化字串
    """
    if num is None or (isinstance(num, float) and num != num):  # NaN check
        return "N/A"
    
    if abs(num) >= 100000000:  # 億
        return f"{num / 100000000:.{decimals}f} 億"
    elif abs(num) >= 10000:  # 萬
        return f"{num / 10000:.{decimals}f} 萬"
    else:
        return f"{num:.{decimals}f}"


if __name__ == "__main__":
    print("Default range:", get_default_date_range())
    print("Format test:", format_number(123456789))
