@echo off
chcp 65001 >nul
title 台股AI決策系統 - 清除快取 + 佈署至 GitHub

echo ============================================
echo  🚀 台股AI個人化決策系統 — 佈署至 GitHub
echo ============================================
echo.

:: 跳至專案目錄
cd /d "%~dp0"

:: ===== [步驟 1] 清除所有快取 =====
echo [1/4] 清除 Python 位元碼快取...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
echo   ✅ 已刪除所有 __pycache__ 目錄

echo.
echo [1/4] 清除 Parquet 快取...
if exist data\cache\*.parquet (
    del /q data\cache\*.parquet 2>nul
    echo   ✅ 已刪除 Parquet 快取
) else (
    echo   ℹ️  無 Parquet 快取
)

echo.
echo [1/4] 清除 SQLite 分析快取...
python -c "import sys; sys.path.insert(0,'.'); from news.database import delete_analysis_cache; delete_analysis_cache('all'); print('  ✅ SQLite 快取已清除')" 2>nul

echo.
echo [1/4] 清除除錯暫存檔（bug/ 目錄下 .csv）...
if exist bug\*.csv (
    del /q bug\*.csv 2>nul
    echo   ✅ 已刪除 bug\*.csv
) else (
    echo   ℹ️  無除錯暫存檔
)
echo.

:: ===== [步驟 2] 顯示 Git 狀態 =====
echo [2/4] 顯示 Git 異動狀態...
echo.
git status
echo.

:: ===== [步驟 3] 加入所有檔案 + Commit + Push =====
echo [3/4] 加入所有檔案至 Git...
git add -A
echo   ✅ git add -A 完成
echo.

echo [3/4] Commit 至本地倉庫（附日期時間）...
set dt=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set dt=%dt: =0%
git commit -m "Auto deploy %dt%"
if %errorlevel% neq 0 (
    echo   ⚠️  Commit 失敗（可能無異動內容）
    echo   將跳過 Push 步驟
    goto :SKIP_PUSH
)
echo   ✅ Commit 完成
echo.

echo [3/4] Push 至 GitHub 遠端倉庫...
git push
if %errorlevel% neq 0 (
    echo   ⚠️  Push 失敗，請檢查 GitHub 連線與權限
    echo   本機 Commit 仍保留，可稍後手動 git push
) else (
    echo   ✅ Push 完成
)
:SKIP_PUSH
echo.

:: ===== [步驟 4] 備份本地程式碼（附日期時間） =====
echo [4/4] 備份當前版本（zip 至 backup/ 目錄）...
python backup.py
echo.

echo ============================================
echo  ✅ 佈署完成！
echo  📦 已清除所有快取
echo  📤 已推送至 GitHub
echo  📁 已備份至 backup/ 目錄
echo ============================================
echo.
pause