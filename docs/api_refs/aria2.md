### **aria2 RPC 接口使用指南**

aria2 通过 JSON-RPC 和 XML-RPC 接口提供远程控制功能。JSON-RPC 的默认请求路径为 `/jsonrpc`。

#### **1. RPC 授权机制**
为了安全，强烈建议使用 **--rpc-secret** 选项设置授权令牌。在调用方法时，必须将令牌作为第一个参数，并加上 `token:` 前缀。
*   例如，若令牌为 `secret`，则参数应为 `"token:secret"`。

---

#### **2. aria2.addUri**
此方法用于**添加新的下载任务**。

*   **方法签名**：`aria2.addUri([secret, ] uris[, options[, position]])`。
*   **参数说明**：
    *   **uris** (数组)：包含指向**同一资源**的 HTTP/FTP/SFTP/BitTorrent URI 字符串数组。
    *   **options** (结构体)：该任务特定的下载选项（如 `dir`、`out` 等）。
    *   **position** (整数)：可选，指定在等待队列中的插入位置（从 0 开始）。
*   **返回值**：返回新任务的 **GID**（16位十六进制字符串标识符）。
*   **JSON-RPC 示例**：
    ```json
    {
      "jsonrpc": "2.0",
      "id": "qwer",
      "method": "aria2.addUri",
      "params": ["token:secret", ["http://example.org/file"], {"dir": "/tmp"}]
    }
    ```

---

#### **3. aria2.tellStatus**
此方法返回由 **GID** 指定的**任务进度及详细状态**。

*   **方法签名**：`aria2.tellStatus([secret, ] gid[, keys])`。
*   **参数说明**：
    *   **gid** (字符串)：任务的唯一 ID。
    *   **keys** (数组)：可选，指定想要获取的响应键名。如果省略，则返回所有键。
*   **主要响应键值**：
    *   **status**：任务状态，包括 `active`（活动）、`waiting`（等待）、`paused`（暂停）、`error`（错误）、`complete`（完成）和 `removed`（已移除）。
    *   **totalLength**：下载总长度（字节）。
    *   **completedLength**：已完成下载长度（字节）。
    *   **downloadSpeed**：下载速度（字节/秒）。
    *   **errorCode**：错误代码（仅针对已停止/完成的任务）。
*   **JSON-RPC 示例**（仅请求 GID 和状态）：
    ```json
    {
      "method": "aria2.tellStatus",
      "params": ["token:secret", "2089b05ecca3d829", ["gid", "status"]]
    }
    ```

---

#### **4. aria2.changeGlobalOption**
此方法用于**动态更改 aria2 的全局下载选项**。

*   **方法签名**：`aria2.changeGlobalOption([secret, ] options)`。
*   **参数说明**：
    *   **options** (结构体)：包含要更改的全局选项对。
*   **可用选项限制**：
    *   以下选项**不可**通过此接口更改：`checksum`、`index-out`、`out`、`pause` 和 `select-file`。
    *   可以使用 `log` 选项动态开启或更改日志文件（传空字符串则停止记录）。
    *   其他常见可用选项包括：`max-concurrent-downloads`、`max-overall-download-limit`、`save-session` 等。
*   **返回值**：成功时返回字符串 `OK`。
*   **JSON-RPC 示例**（设置全局下载限速）：
    ```json
    {
      "method": "aria2.changeGlobalOption",
      "params": ["token:secret", {"max-overall-download-limit": "500K"}]
    }
    ```

---

### **概念理解：控制塔与飞机**
为了更好地理解这些接口，可以将 **aria2** 想象成一个**繁忙的机场控制塔**：

*   **`aria2.addUri`** 就像是**调度新飞机降落**。你告诉塔台飞机的编号（URI）和它应该停靠的机坪（options），塔台会给这架飞机分配一个唯一的呼号（GID）。
*   **`aria2.tellStatus`** 就像是**询问某架飞机的状态**。你可以问塔台：“呼号为 X 的飞机现在在哪？”塔台会回复它是在排队（waiting）、正在着陆（active）还是已经进站（complete）。
*   **`aria2.changeGlobalOption`** 就像是**调整机场的整体规则**。比如你可以下令：“从现在起，机场跑道同时只能起降 5 架飞机（max-concurrent-downloads）”，或者“所有飞机的滑行速度不得超过特定限制”。这种调整会影响整个机场的所有飞行任务。