# 台股AI個人化決策系統 v1.6
# Render Web Service 專用 Dockerfile
# Render 會自動代入 $PORT 環境變數

FROM python:3.11-slim

WORKDIR /app

# 複製依賴檔案並安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有程式碼
COPY . .

# Render Web Service 啟動指令
CMD ["sh", "-c", "streamlit run app.py --server.port $PORT --server.address 0.0.0.0"]
