# Linode API v4 使用指南

Linode API 可用于自动化执行 Cloud Manager 中的任何任务，包括管理 Linode 实例、配置防火墙、管理账户及处理工单等。

## 1. 使用流程与身份验证

在使用 Linode API 之前，必须完成以下准备步骤：

*   **获取访问令牌 (Access Token)**：所有对非公共资源的 API 请求都必须通过个人访问令牌进行身份验证。
*   **身份验证方式**：在 API 请求的头部（Header）中包含该令牌。格式为：`Authorization: Bearer <token-string>`。
*   **获取配置参数**：在创建实例前，通常需要查询并存储以下信息的 ID：
    *   **方案类型 (Type)**：例如 `g5-standard-2`（标准 2GB 计算实例）。
    *   **镜像 (Image)**：例如 `linode/debian11`。
    *   **区域 (Region)**：例如 `us-east`（纽瓦克数据中心）。

---

## 2. Linode 实例管理 API 细节

### 2.1 创建 Linode (Create a Linode)
**接口地址**：`POST https://api.linode.com/v4/linode/instances`

**核心参数说明**：
*   **type** (String): 必需。方案 ID（如 `g5-standard-2`）。
*   **region** (String): 必需。数据中心 ID（如 `us-east`）。
*   **image** (String): 可选。操作系统镜像 ID（如 `linode/debian12`）。
*   **root_pass** (String): 必需（使用镜像时）。root 用户的登录密码。
*   **label** (String): 可选。Linode 实例的显示名称。
*   **authorized_keys** (List): 可选。为 root 用户提供的 SSH 公钥列表。
*   **swap_size** (Integer): 可选。自定义交换分区大小（默认为 512MB）。

**注意事项**：
*   用户必须拥有 `add_linodes` 权限才能成功创建。
*   创建操作会产生费用。
*   可以通过 **StackScript**、**备份 (Backup)** 或 **私有镜像** 进行创建。

---

### 2.2 查询特定 Linode (Get a Linode)
**接口地址**：`GET https://api.linode.com/v4/linode/instances/{linodeId}`

**回显说明**：
*   返回特定 Linode 实例的详细信息，包括其状态、IP 地址、配置规格等。
*   如果使用 `GET https://api.linode.com/v4/linode/instances` 则会列出账户下的所有 Linode。

---

### 2.3 删除 Linode (Delete a Linode)
**接口地址**：`DELETE https://api.linode.com/v4/linode/instances/{linodeId}`

**执行后果与回显说明**：
*   **破坏性操作**：该操作不可逆。
*   **资源释放**：会删除所有关联的磁盘、备份和配置，并释放分配给该实例的 IP 地址。
*   **计费停止**：停止对该实例及其关联服务的计费（已产生的使用时长仍会计入账单）。
*   **限制**：正在进行克隆或备份恢复的 Linode 无法删除。

---

## 3. Python 使用示例

你可以使用 Python 的 `requests` 库来调用 API。

```python
import requests

# 你的个人访问令牌
TOKEN = 'your_personal_access_token'
HEADERS = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json'
}

# 1. 创建 Linode 示例
def create_linode():
    url = "https://api.linode.com/v4/linode/instances"
    data = {
        "type": "g5-standard-2",
        "region": "us-east",
        "image": "linode/debian12",
        "root_pass": "your_secure_password",
        "label": "my-python-linode"
    }
    response = requests.post(url, headers=HEADERS, json=data)
    return response.json()

# 2. 查询 Linode 示例 (根据 ID)
def get_linode(linode_id):
    url = f"https://api.linode.com/v4/linode/instances/{linode_id}"
    response = requests.get(url, headers=HEADERS)
    return response.json()

# 3. 删除 Linode 示例
def delete_linode(linode_id):
    url = f"https://api.linode.com/v4/linode/instances/{linode_id}"
    response = requests.delete(url, headers=HEADERS)
    if response.status_code == 200:
        print("删除成功")
    else:
        print(f"删除失败: {response.json()}")

# 使用逻辑示范
# new_linode = create_linode()
# linode_id = new_linode.get('id')
# print(get_linode(linode_id))
```

---

**比喻说明**：
如果把 Linode 云端资源比作一个**酒店**，那么 **API 访问令牌** 就是酒店发给你的**万能房卡**。你通过这个房卡（API）向前台（Linode 服务器）下达指令：**创建请求**就像是预订并入住房间；**查询请求**则是查看房间当前的清洁或占用状态；而**删除请求**则相当于彻底退房并清空房间内的所有个人物品。