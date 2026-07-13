# 台股AI個人化決策系統 v3.1 - Dockerfile（可選）
# Render 也支援直接從 requirements.txt 部署，此檔案為容器化選項

FROM python:3.11-slim

WORKDIR /app

# 複製依賴檔案
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案程式碼
COPY . .

# Render 會自動設定 PORT 環境變數
# 啟動指令：streamlit run app.py --server.port $PORT --server.address 0.0.0.0
CMD ["sh", "-c", "streamlit run app.py --server.port $PORT --server.address 0.0.0.0"]
