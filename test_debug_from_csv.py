"""
test_debug_from_csv.py
從 data/debug/ 目錄讀取 CSV 進行離線評分測試

用法：
  python test_debug_from_csv.py                          # 自動找最新的 CSV
  python test_debug_from_csv.py --file 2330_debug.csv    # 指定檔案
  python test_debug_from_csv.py --list                   # 列出可用檔案
"""
import sys
import os
import glob
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from core.scorer import get_all_scores
from core.advisor import get_advice

DEBUG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "debug")


def list_debug_files():
    """列出 data/debug/ 下的所有 CSV"""
    files = sorted(glob.glob(os.path.join(DEBUG_DIR, "*.csv")))
    if not files:
        print("❌ data/debug/ 目錄下沒有 CSV 檔案")
        print("   請先從網頁除錯面板 → 匯出 CSV 下載檔案放到此目錄")
        return
    
    print(f"📂 data/debug/ 共有 {len(files)} 個 CSV 檔案：")
    for i, f in enumerate(files, 1):
        fname = os.path.basename(f)
        size = os.path.getsize(f)
        df = pd.read_csv(f, nrows=0)
        cols = len(df.columns)
        print(f"  {i}. {fname}  ({size/1024:.1f} KB, {cols} 欄)")


def load_csv(filepath: str) -> pd.DataFrame:
    """讀取 CSV，自動處理日期欄位"""
    df = pd.read_csv(filepath)
    
    # 嘗試轉換 date 欄位
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    
    print(f"📥 讀取 {os.path.basename(filepath)}: {len(df)} 行 x {len(df.columns)} 欄")
    return df


def run_scoring(df: pd.DataFrame):
    """對 DataFrame 執行評分"""
    print(f"\n{'='*60}")
    print("🎯 執行四風格評分")
    print(f"{'='*60}")
    
    scores = get_all_scores(df)
    
    for style_key in ["short_term", "swing", "value", "dividend"]:
        s = scores.get(style_key, {})
        total = s.get("total", 0)
        breakdown = s.get("breakdown", {})
        modifiers = s.get("modifiers", {})
        
        print(f"\n  {style_key}: {total}/100")
        for k, v in breakdown.items():
            print(f"      {k}: {v}")
        if modifiers:
            for mk, mv in modifiers.items():
                if isinstance(mv, dict):
                    print(f"      [{mk}]: {mv}")
                else:
                    print(f"      [{mk}]: {mv}")
    
    # Advisor 建議
    print(f"\n{'='*60}")
    print("💡 Advisor 建議")
    print(f"{'='*60}")
    advice = get_advice(scores)
    print(f"  建議: {advice.get('advice', 'N/A')}")
    print(f"  最佳風格: {advice.get('best_style', 'N/A')} ({advice.get('best_score', 0)}/100)")
    
    return scores


def main():
    parser = argparse.ArgumentParser(description="從 CSV 離線測試評分")
    parser.add_argument("--file", help="指定 CSV 檔名（放在 data/debug/ 下）")
    parser.add_argument("--list", action="store_true", help="列出可用檔案")
    args = parser.parse_args()
    
    if args.list:
        list_debug_files()
        return
    
    # 找要讀取的檔案
    if args.file:
        filepath = os.path.join(DEBUG_DIR, args.file)
        if not os.path.exists(filepath):
            print(f"❌ 找不到檔案: {filepath}")
            list_debug_files()
            return
    else:
        # 自動找最新的 CSV
        files = sorted(glob.glob(os.path.join(DEBUG_DIR, "*.csv")))
        if not files:
            print("❌ data/debug/ 目錄下沒有 CSV 檔案")
            print("   請先從網頁除錯面板 → 匯出 CSV 下載檔案放到此目錄")
            print("   或使用 --file 指定檔案路徑")
            return
        filepath = files[-1]  # 最新的
        print(f"📂 自動選取最新檔案: {os.path.basename(filepath)}")
    
    df = load_csv(filepath)
    run_scoring(df)
    
    print(f"\n{'='*60}")
    print("✅ 測試完成")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
