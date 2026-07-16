# 安裝與設定指南

## 系統需求

- **Python** 3.10+
- 網路連線（用於呼叫 FinMind API）

---

## 1. 申請 API 金鑰

### FinMind API Token（必填）

1. 前往 [FinMind](https://finmindtrade.com) 官網
2. 點右上角 **Login / Register** → 用 Email 註冊
3. 登入後進 **Dashboard** → 左邊 **API Token**
4. 複製 Token（`eyJ0eXAiOiJKV1Qi...` 開頭的字串）

### DeepSeek API Key（選填）

1. 前往 [DeepSeek Platform](https://platform.deepseek.com) 註冊
2. 登入後點左邊 **API Keys**
3. 點 **Create API key** → 取名（如 `stock-analyzer`）
4. 複製 Key

---

## 2. 本地安裝

```bash
# 下載專案
git clone https://github.com/your-username/taiwan-stock-analyzer-v3.git
cd taiwan-stock-analyzer-v3

# 安裝依賴
pip install -r requirements.txt

# 啟動
streamlit run app.py
```

啟動後瀏覽器自動開啟 `http://localhost:8501`，在側邊欄貼上 FinMind Token 即可使用。

---

## 3. Render 雲端部署

| 項目 | 設定值 |
|:---|:---|
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `streamlit run app.py --server.port $PORT --server.address 0.0.0.0` |
| **環境變數** | `FINMIND_TOKEN`, `DEEPSEEK_API_KEY`（選填） |

> **注意**：Streamlit 應用程式不是 WSGI callable，**不可使用** `gunicorn app:app` 啟動。

---

## 4. 大改版後快取清理

改完程式碼後若發現結果沒變，通常是快取殘留：

```bash
# Windows：點兩下 refresh_and_restart.bat
# 或手動：
del data\cache\*.parquet
python -c "from news.database import delete_analysis_cache; delete_analysis_cache('all')"
streamlit run app.py
```

---

## 5. 測試

```bash
# 完整管線測試（需 FinMind Token）
python test_full_pipeline.py

# 啟動前端
streamlit run app.py