@echo off
chcp 65001 >nul
title 台股AI決策系統 - 清除快取 + 重啟

echo ==================================
echo  🧹 清除快取 + 重新啟動 App
echo ==================================
echo.

:: 跳至專案目錄
cd /d "%~dp0"

:: ===== [步驟 0] 程式開發備份 =====
echo [0/5] 備份原始碼（附日期時間）...

:: 使用 Python 備份腳本（專案內建，最穩定）
python backup.py

echo.

echo [1/5] 清除 Python 位元碼快取...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
echo   ✅ 已刪除所有 __pycache__ 目錄

echo.
echo [2/5] 清除 Parquet 快取...
if exist data\cache\*.parquet (
    del /q data\cache\*.parquet 2>nul
    echo   ✅ 已刪除 Parquet 快取
) else (
    echo   ℹ️  無 Parquet 快取
)

echo.
echo [3/5] 清除 SQLite 分析快取...
python -c "import sys; sys.path.insert(0,'.'); from news.database import delete_analysis_cache; delete_analysis_cache('all'); print('  ✅ SQLite 快取已清除')" 2>nul
if %errorlevel% neq 0 echo   ⚠️  SQLite 清除失敗（可跳過）

echo.
echo [4/5] 啟動 Streamlit App...
echo.
echo ==================================
echo  ⏳ 啟動中，請稍候...
echo  🌐 瀏覽器將自動開啟 http://localhost:8501
echo  ❌ 關閉視窗 = 停止 App
echo ==================================
echo.

streamlit run app.py

pause