# ============================================================
# Stage 1: 构建前端
# ============================================================
FROM node:20-alpine as frontend-builder

WORKDIR /frontend

# 安装前端依赖
COPY frontend/package*.json ./
RUN npm install

# 构建前端
COPY frontend/ ./
RUN npm run build


# ============================================================
# Stage 2: 后端 + 前端静态文件
# ============================================================
FROM python:3.11-slim

WORKDIR /app

# 安装 curl 和 wget 用于健康检查和下载
RUN apt-get update && apt-get install -y curl wget && \
    wget -qO /usr/local/bin/hysteria https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64 && \
    chmod +x /usr/local/bin/hysteria && \
    rm -rf /var/lib/apt/lists/*

# 安装依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY backend/app/ ./app/

# 复制前端构建产物
COPY --from=frontend-builder /frontend/dist ./static

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
