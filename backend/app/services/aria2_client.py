"""
Aria2 RPC 客户端
"""
import json
import uuid
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings


class Aria2Client:
    """Aria2 JSON-RPC 客户端"""
    
    def __init__(self, rpc_url: Optional[str] = None, rpc_secret: Optional[str] = None):
        settings = get_settings()
        self.rpc_url = rpc_url or settings.aria2_rpc_url
        self.rpc_secret = rpc_secret or settings.aria2_rpc_secret
        self._client = httpx.AsyncClient(timeout=30.0)
    
    async def _call(self, method: str, params: Optional[List[Any]] = None) -> Any:
        """执行 RPC 调用"""
        # 构造参数列表，首位添加 token
        call_params = []
        if self.rpc_secret:
            call_params.append(f"token:{self.rpc_secret}")
        if params:
            call_params.extend(params)
        
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": call_params
        }
        
        response = await self._client.post(self.rpc_url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        if "error" in result:
            raise Aria2Error(result["error"]["message"], result["error"]["code"])
        
        return result.get("result")
    
    async def add_uri(
        self,
        uris: List[str],
        options: Optional[Dict[str, str]] = None,
        position: Optional[int] = None
    ) -> str:
        """
        添加下载任务
        
        Args:
            uris: URI 列表 (同一资源的多个镜像)
            options: 下载选项 (dir, out, header 等)
            position: 在队列中的位置
            
        Returns:
            任务 GID
        """
        params: List[Any] = [uris]
        
        # 添加默认选项
        default_options = {
            "user-agent": "Logos-Droid",
            "split": "16",
            "max-connection-per-server": "16",
        }
        if options:
            default_options.update(options)
        params.append(default_options)
        
        if position is not None:
            params.append(position)
        
        return await self._call("aria2.addUri", params)
    
    async def tell_status(
        self,
        gid: str,
        keys: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        查询任务状态
        
        Args:
            gid: 任务 GID
            keys: 要返回的字段列表 (不指定则返回全部)
            
        Returns:
            任务状态信息
        """
        params: List[Any] = [gid]
        if keys:
            params.append(keys)
        
        return await self._call("aria2.tellStatus", params)
    
    async def tell_active(self, keys: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """获取所有活跃的下载任务"""
        params: List[Any] = []
        if keys:
            params.append(keys)
        return await self._call("aria2.tellActive", params)
    
    async def change_global_option(self, options: Dict[str, str]) -> str:
        """
        修改全局选项
        
        Args:
            options: 要修改的选项字典
            
        Returns:
            "OK" 成功
        """
        return await self._call("aria2.changeGlobalOption", [options])
    
    async def set_proxy(self, proxy_url: Optional[str] = None) -> str:
        """
        设置全局代理
        
        Args:
            proxy_url: 代理 URL，如 "http://ip:port" 或 None 清除代理
            
        Returns:
            "OK" 成功
        """
        return await self.change_global_option({
            "all-proxy": proxy_url or ""
        })
    
    async def get_global_stat(self) -> Dict[str, Any]:
        """获取全局统计信息 (速度、任务数等)"""
        return await self._call("aria2.getGlobalStat")
    
    async def pause(self, gid: str) -> str:
        """暂停任务"""
        return await self._call("aria2.pause", [gid])
    
    async def unpause(self, gid: str) -> str:
        """恢复任务"""
        return await self._call("aria2.unpause", [gid])
    
    async def remove(self, gid: str) -> str:
        """移除任务"""
        return await self._call("aria2.remove", [gid])
    
    async def get_version(self) -> Dict[str, Any]:
        """获取 Aria2 版本信息"""
        return await self._call("aria2.getVersion")
    
    async def close(self):
        """关闭 HTTP 客户端"""
        await self._client.aclose()


class Aria2Error(Exception):
    """Aria2 RPC 错误"""
    
    def __init__(self, message: str, code: int):
        self.message = message
        self.code = code
        super().__init__(f"Aria2 Error [{code}]: {message}")


# 单例客户端
_aria2_client: Optional[Aria2Client] = None


def get_aria2_client() -> Aria2Client:
    """获取 Aria2 客户端单例"""
    global _aria2_client
    if _aria2_client is None:
        _aria2_client = Aria2Client()
    return _aria2_client
