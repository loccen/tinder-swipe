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

---

## 快速开始 (Docker 部署)

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

# 4. 首次 Telegram 登录
docker-compose stop collector
docker-compose run -it collector
# 输入验证码后 Ctrl+C 退出
docker-compose up -d collector

# 5. 访问前端
open http://localhost:3000
```

---

## 本地开发

### 环境要求

| 依赖 | 版本要求 | 说明 |
|------|---------|------|
| Python | **3.11+** | pikpakapi 库需要 Python 3.10+ |
| Node.js | 18+ | 前端构建 |
| npm | 9+ | 依赖管理 |

### 1. 安装 Python 3.11

#### macOS (使用 pyenv)

```bash
# 安装 pyenv
brew install pyenv

# 添加到 shell 配置 (~/.zshrc 或 ~/.bashrc)
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
source ~/.zshrc

# 安装 Python 3.11
pyenv install 3.11.7

# 在项目目录中设置 Python 版本
cd /path/to/tinder-swipe
pyenv local 3.11.7

# 验证
python --version  # 应显示 Python 3.11.7
```

#### macOS (使用 Homebrew)

```bash
brew install python@3.11
# 使用 /usr/local/opt/python@3.11/bin/python3.11 创建虚拟环境
```

### 2. 创建虚拟环境

```bash
cd /path/to/tinder-swipe

# 创建虚拟环境
python3.11 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 验证 Python 版本
python --version  # 应显示 Python 3.11.x
```

### 3. 安装依赖

```bash
# 确保虚拟环境已激活
source .venv/bin/activate

# 安装后端依赖
pip install -r backend/requirements.txt

# 安装采集器依赖
pip install -r collector/requirements.txt

# 安装前端依赖
cd frontend && npm install && cd ..
```

### 4. 准备数据目录

```bash
mkdir -p data/previews sessions
```

### 5. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 API 凭证
```

### 6. 启动开发服务

#### 方式一：使用 VSCode 调试 (推荐)

1. 用 VSCode 打开项目
2. 按 `F5` 或点击「运行和调试」
3. 选择配置：
   - **Backend: FastAPI** - 仅后端
   - **Frontend: Vite Dev** - 仅前端
   - **Full Stack** - 后端 + 前端
   - **All Services** - 全部服务

#### 方式二：命令行启动

```bash
# 终端 1: 启动后端
source .venv/bin/activate
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 终端 2: 启动前端
cd frontend
npm run dev

# 终端 3: 启动采集器 (可选)
source .venv/bin/activate
python collector/collector.py
```

### 7. 访问应用

- **前端**: http://localhost:3000
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

---

## 项目结构

```
tinder-swipe/
├── backend/                   # FastAPI 后端
│   ├── app/
│   │   ├── api/               # API 路由
│   │   ├── core/              # 配置、数据库
│   │   ├── models/            # SQLAlchemy 模型
│   │   ├── schemas/           # Pydantic 模型
│   │   └── services/          # 业务逻辑
│   ├── Dockerfile
│   └── requirements.txt
├── collector/                 # Telegram 采集引擎
│   ├── collector.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                  # Vue 3 PWA
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── aria2/                     # NAS 节点 Aria2 配置
│   └── docker-compose.yml
├── data/                      # 运行时数据 (被 .gitignore 忽略)
│   ├── swipe.db               # SQLite 数据库
│   └── previews/              # 预览图缓存
├── sessions/                  # Telegram session (被 .gitignore 忽略)
├── .vscode/                   # VSCode 调试配置
├── docker-compose.yml
├── .env.example               # 环境变量模板
└── README.md
```

---

## 常见问题

### Q: 本地运行报错 `ImportError: cannot import name 'NoneType' from 'types'`

**原因**：Python 版本过低，pikpakapi 库需要 Python 3.10+

**解决**：升级 Python 到 3.11，参考上方「本地开发」章节

### Q: Telegram 采集器如何登录？

1. 首次运行时会提示输入验证码
2. Docker 环境需要使用交互模式：`docker-compose run -it collector`
3. 本地开发直接运行即可在终端输入

### Q: 如何添加/删除监听频道？

在前端「设置」页面可以动态管理频道，修改后需重启采集器生效。

---

## 许可证

MIT
