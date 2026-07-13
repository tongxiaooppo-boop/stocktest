# 台股AI個人化決策系統 v3.1

本文件為系統設計文件，請參考 `台股AI個人化決策系統_開發規格書_v3.1_claude0711.md` 原始文件。

## 目錄結構

```
taiwan-stock-analyzer-v3/
├── app.py                      # Streamlit 前端（主入口）
├── requirements.txt            # Python 依賴（不含 gunicorn）
├── Dockerfile                  # 容器化部署（可選）
├── .env.example                # 環境變數範例
├── .gitignore
│
├── data/                       # 資料抓取與清洗
│   ├── __init__.py
│   ├── fetcher.py              # FinMind API 呼叫（全撈取）
│   └── processor.py            # 母表建構：頻率對齊、公告日對齊、長轉寬
│
├── stock/                      # 指標計算
│   ├── __init__.py
│   ├── metrics.py              # 財務指標（ROE、FCF、PE、PB、YoY...）
│   └── screener.py             # 選股篩選（未來擴充用）
│
├── core/                       # 純 Python 規則引擎
│   ├── __init__.py
│   ├── scorer.py               # 四種風格打分（0-100）
│   └── advisor.py              # 基本建議規則（買/持有/賣）
│
├── ai/                         # AI 邏輯
│   ├── __init__.py
│   ├── analyzer.py             # DeepSeek API 呼叫
│   └── prompts.py              # 四種風格的 System Prompt
│
├── utils/                      # 共用工具
│   ├── __init__.py
│   └── helpers.py              # 金鑰驗證、錯誤處理、日期格式化
│
├── tests/                      # 單元測試（未來）
│   └── test_core.py
│
└── docs/                       # 文件
    └── DESIGN_v3.1.md          # 本文件
```
