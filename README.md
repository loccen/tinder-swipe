# PikPak Tinder-Swipe 自动化收集系统

一个高效的影视资源收集流水线，集成 Telegram 监听、Tinder 风格筛选界面、Linode 动态代理加速和 Aria2 高速下载。

## 功能特性

- 🤖 **Telegram 自动采集**：监听指定频道，自动提取磁力/PikPak 链接
- 📱 **Tinder 风格筛选**：PWA 应用，手势滑动确认或忽略资源
- ☁️ **动态代理加速**：按需创建 Linode VPS + Hysteria2 代理
- ⚡ **高速下载**：通过 Aria2 16 线程下载，速度可达 50MB/s+
- 💰 **成本优化**：任务完成后自动销毁 VPS，按分钟计费

## 技术栈

- **后端**：Python 3.11 + FastAPI + SQLite
- **前端**：Vue 3 + Vant UI + PWA
- **采集**：Telethon (Telegram UserBot)
- **下载**：PikPak API + Aria2 RPC
- **代理**：Linode API + Hysteria2
- **部署**：Docker Compose

## 快速开始

### 环境要求

- Docker & Docker Compose
- Telegram API 凭证 (从 my.telegram.org 获取)
- PikPak 账号
- Linode API Token
- 运行中的 Aria2 服务

### 部署步骤

```bash
# 1. 克隆项目
git clone <repo-url>
cd tinder-swipe

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API 凭证

# 3. 启动服务
docker-compose up -d

# 4. 访问前端
open http://localhost:3000
```

## 项目结构

```
tinder-swipe/
├── backend/          # FastAPI 后端 + 编排引擎
├── collector/        # Telegram 采集引擎
├── frontend/         # Vue 3 PWA 前端
├── docs/             # 项目文档
├── data/             # 运行时数据 (SQLite + 预览图)
└── docker-compose.yml
```

## 许可证

MIT
