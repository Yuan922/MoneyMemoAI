FROM python:3.9-slim

# 更新套件列表並安裝編譯工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    portaudio19-dev \
    libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

# 設定環境變數
ENV PYTHONUNBUFFERED=1

# 建立工作目錄
WORKDIR /app

# 複製專案檔案
COPY finance_app.py /app/
COPY .streamlit /app/.streamlit
COPY .env /app/.env

# 安裝 Python 依賴
RUN pip install --no-cache-dir \
    streamlit \
    plotly \
    speechrecognition \
    google-generativeai \
    pandas \
    pyaudio

# 啟動 Streamlit 應用程式
EXPOSE 8501
CMD streamlit run finance_app.py --server.address=0.0.0.0 --server.port=8501
