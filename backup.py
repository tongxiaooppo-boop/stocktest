"""
備份腳本 — 將專案原始碼壓縮為 backup\YYYY-MM-DD_HHMMSS.zip
排除：__pycache__、.git、venv、data\cache、backup 等
"""
import os
import shutil
import zipfile
from datetime import datetime

# 專案根目錄
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(SRC_DIR, "backup")

# 排除目錄（名稱比對，不區分大小寫）
EXCLUDE_DIRS = {
    "__pycache__", ".git", "venv", ".venv", "data\\cache",
    "backup", ".mypy_cache", ".pytest_cache", "node_modules"
}

# 排除副檔名
EXCLUDE_EXT = {".zip", ".pyc", ".pyo", ".parquet", ".db"}

# 排除特定檔案
EXCLUDE_FILES = {".gitignore"}


def should_include(root: str, name: str) -> bool:
    """判斷檔案/目錄是否應納入備份"""
    # 檢查目錄排除
    parts = root.replace(SRC_DIR, "").strip(os.sep).split(os.sep)
    for part in parts:
        if part.lower() in {d.lower() for d in EXCLUDE_DIRS}:
            return False

    full_path = os.path.join(root, name)
    if os.path.isdir(full_path):
        # 目錄本身也要檢查
        if name.lower() in {d.lower() for d in EXCLUDE_DIRS}:
            return False
        return True
    else:
        # 檔案檢查
        if name in EXCLUDE_FILES:
            return False
        _, ext = os.path.splitext(name)
        if ext.lower() in EXCLUDE_EXT:
            return False
        return True


def backup():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    zip_path = os.path.join(BACKUP_DIR, f"{timestamp}.zip")

    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(SRC_DIR):
            # 過濾目錄（直接從 dirs 移除，避免 os.walk 進入）
            dirs[:] = [d for d in dirs if should_include(root, d)]

            for file in files:
                if should_include(root, file):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, SRC_DIR)
                    zf.write(full_path, rel_path)
                    count += 1

    file_size = os.path.getsize(zip_path)
    print(f"  ✅ 備份完成：{timestamp}.zip （{count} 個檔案，{file_size:,} 位元組）")


if __name__ == "__main__":
    backup()