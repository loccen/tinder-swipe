# PikPak API 使用指南

根据提供的参考文档，PikPak 提供了一系列 API 接口供开发者进行二次开发，主要包括 Python 实现的 SDK 以及集成于第三方工具中的调用方式。以下是基于参考文档整理的 API 使用指南。

---

### 1. 快速开始 (Python SDK)

**Quan666/PikPakAPI** 是一个 PikPak API 的 Python 实现版本。

#### 安装
使用 pip 安装官方推荐的 Python 库：
```bash
pip3 install pikpakapi
```

#### 基础代码示例
以下是一个完成登录、刷新令牌及获取离线列表的基础异步操作示例：
```python
from pikpakapi import PikPakApi

async def main():
    # 初始化客户端
    client = PikPakApi(username="your_username", password="your_password")
    
    # 执行登录
    await client.login()
    
    # 刷新访问令牌 (Access Token)
    await client.refresh_access_token()
    
    # 获取离线下载列表
    tasks = await client.offline_list()
    print(tasks)
```

---

### 2. 核心功能支持
根据参考文档，该 API 支持以下核心操作：
*   **身份验证**：支持登录及令牌自动刷新。
*   **离线任务管理**：管理离线下载任务列表。
*   **文件操作**：包括文件重命名、收藏、分享等。
*   **路径管理**：支持指定离线下载至特定目录（如设置 `PIKPAK_OFFLINE_PATH`）。

---

### 3. 数据结构参考
在调用 API 获取文件信息时，返回的 **JSON 数据（html 变量）** 通常包含以下关键字段，开发者可根据这些字段实现自定义功能：

*   **id**: 文件唯一标识符。
*   **name**: 文件名称。
*   **size**: 文件大小（字节）。
*   **web_content_link**: **文件直链**，用于直接下载或投屏播放。
*   **links**: 包含不同协议（如 `application/octet-stream`）的下载链接及其对应的 Token。
*   **medias**: 包含视频的分辨率、原始链接等信息。
*   **params**: 包含原始磁力链接（`url`）等参数。

---

### 4. 进阶应用场景
利用 API 返回的 `web_content_link` 和文件信息，可以实现将任务推送至第三方工具。

#### 推送至下载器 (Aria2)
可以通过构造 JSON-RPC 请求，将 PikPak 的直链推送至 Aria2 进行高速下载：
*   **方法**：`aria2.addUri`。
*   **参数**：包含 `url`、下载路径 `dir` 以及文件名 `out`。
*   **镜像加速**：可以通过替换域名的方式添加多个镜像链接以提升下载速度。

#### 推送至播放器 (PotPlayer / MPV)
调用本地播放器 API 或通过进程调用，直接播放网盘内的视频：
*   **PotPlayer**: 传入 `file_url` 并附加参数 `/insert` 或 `/current`。
*   **MPV**: 传入 `file_url` 并通过 `--title` 设置显示的文件名。

---

### 5. 使用限制与注意事项
*   **账号配额**：本项目不涉及破解行为。普通用户仍受 **6G 空间限制** 以及 **每天三次离线机会** 的限制。
*   **离线特性**：部分资源在 PikPak 服务器上可能因没有缓存导致下载进度长时间卡在 0%，此时程序通常会停止处理该磁链。
*   **安全建议**：**不建议将存储重要文件的账号用于此类自动化项目**，因为部分强力删除命令（如 `/clean`）操作不慎可能导致数据误删。
*   **文件过滤**：PikPak 默认可能不离线某些广告文件，若返回 `not saved successfully` 可能是此原因。

---

**比喻说明**：
如果把 PikPak 网盘比作一个巨大的**远程仓库**，那么 API 就像是仓库的**遥控器**。你可以通过代码命令（按遥控器）让仓库自动接收外面的包裹（磁力离线），或者命令仓库把某个包裹直接送到你的电视机（播放器）或本地小仓库（Aria2）里，而不需要你亲自去搬运。