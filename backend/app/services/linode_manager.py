"""
Linode 实例管理服务
"""
import secrets
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LinodeManager:
    """Linode API 管理器"""
    
    BASE_URL = "https://api.linode.com/v4"
    
    # SOCKS5 代理 cloud-init 脚本模板 (使用 Dante)
    CLOUD_INIT_TEMPLATE = """#cloud-config
packages:
  - dante-server
  - ufw

runcmd:
  # 获取主网卡名称
  - |
    IFACE=$(ip route | grep default | awk '{{print $5}}' | head -1)
    
    # 写入 Dante 配置文件
    cat > /etc/danted.conf << EOF
    logoutput: syslog
    
    internal: 0.0.0.0 port = {port}
    external: $IFACE
    
    socksmethod: username
    clientmethod: none
    
    user.privileged: root
    user.unprivileged: nobody
    
    client pass {{
        from: 0.0.0.0/0 to: 0.0.0.0/0
        log: error
    }}
    
    socks pass {{
        from: 0.0.0.0/0 to: 0.0.0.0/0
        protocol: tcp udp
        command: bind connect udpassociate
        log: error
        socksmethod: username
    }}
    EOF
    
  # 创建代理认证用户
  - useradd -r -s /bin/false {username} || true
  - echo "{username}:{password}" | chpasswd
  
  # 启动服务
  - systemctl enable danted
  - systemctl start danted
  
  # 配置防火墙
  - ufw allow {port}/tcp
  - ufw --force enable
  
  # 标记就绪
  - touch /var/run/socks5_ready
"""
    
    def __init__(self, token: Optional[str] = None):
        settings = get_settings()
        self.token = token or settings.linode_token
        self.region = settings.linode_region
        self.instance_type = settings.linode_type
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            },
            timeout=60.0
        )
    
    async def create_instance(
        self,
        label: str,
        socks5_port: Optional[int] = None,
        socks5_username: Optional[str] = None,
        socks5_password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建 Linode 实例并自动部署 SOCKS5 代理
        
        Args:
            label: 实例标签
            socks5_port: SOCKS5 代理端口 (默认使用配置)
            socks5_username: SOCKS5 认证用户名 (默认使用配置)
            socks5_password: SOCKS5 认证密码 (默认使用配置)
            
        Returns:
            实例信息 (包含 id, ip_address, socks5_* 等)
        """
        settings = get_settings()
        
        # 使用配置中的固定值作为默认
        socks5_port = socks5_port or settings.socks5_port
        socks5_username = socks5_username or settings.socks5_username
        socks5_password = socks5_password or settings.socks5_password
        
        # 生成 cloud-init 脚本
        user_data = self.CLOUD_INIT_TEMPLATE.format(
            port=socks5_port,
            username=socks5_username,
            password=socks5_password
        )
        
        # 幂等性检查：先尝试查找同名标签的现有实例
        existing_instances = await self.list_instances(label_prefix=label)
        for inst in existing_instances:
            if inst.get("label") == label:
                logger.info(f"发现已存在的同名实例: {label} (ID: {inst['id']})，将复用该实例")
                inst["socks5_port"] = socks5_port
                inst["socks5_username"] = socks5_username
                inst["socks5_password"] = socks5_password
                return inst

        # 生成 root 密码
        root_pass = secrets.token_urlsafe(24)
        
        # Linode API 要求 user_data 必须是 base64 编码的
        import base64
        user_data_b64 = base64.b64encode(user_data.encode("utf-8")).decode("utf-8")
        
        payload = {
            "type": self.instance_type,
            "region": self.region,
            "image": "linode/debian12",
            "root_pass": root_pass,
            "label": label,
            "metadata": {
                "user_data": user_data_b64
            }
        }
        
        response = await self._client.post("/linode/instances", json=payload)
        if response.status_code != 200:
            error_details = response.json()
            logger.error(f"Linode API Error (400): {error_details}")
        response.raise_for_status()
        
        data = response.json()
        
        # 附加返回代理信息
        data["socks5_port"] = socks5_port
        data["socks5_username"] = socks5_username
        data["socks5_password"] = socks5_password
        
        return data
    
    async def get_instance(self, linode_id: int) -> Dict[str, Any]:
        """
        获取实例详情
        
        Args:
            linode_id: Linode 实例 ID
            
        Returns:
            实例信息
        """
        response = await self._client.get(f"/linode/instances/{linode_id}")
        response.raise_for_status()
        return response.json()
    
    async def list_instances(self, label_prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出所有实例
        
        Args:
            label_prefix: 按标签前缀过滤
            
        Returns:
            实例列表
        """
        response = await self._client.get("/linode/instances")
        response.raise_for_status()
        
        instances = response.json().get("data", [])
        
        if label_prefix:
            instances = [
                i for i in instances 
                if i.get("label", "").startswith(label_prefix)
            ]
        
        return instances
    
    async def get_instance_by_label(self, label: str) -> Optional[Dict[str, Any]]:
        """
        根据标签精确查找实例
        
        Args:
            label: 实例标签
            
        Returns:
            实例信息或 None
        """
        instances = await self.list_instances()
        for instance in instances:
            if instance.get("label") == label:
                return instance
        return None
    
    async def delete_instance(self, linode_id: int) -> bool:
        """
        删除实例
        
        Args:
            linode_id: Linode 实例 ID
            
        Returns:
            是否成功
        """
        response = await self._client.delete(f"/linode/instances/{linode_id}")
        return response.status_code == 200
    
    async def wait_for_running(
        self,
        linode_id: int,
        timeout_seconds: int = 300,
        poll_interval: int = 10
    ) -> Optional[str]:
        """
        等待实例进入 running 状态并返回 IP 地址
        
        Args:
            linode_id: Linode 实例 ID
            timeout_seconds: 超时时间 (秒)
            poll_interval: 轮询间隔 (秒)
            
        Returns:
            公网 IP 地址或 None (超时)
        """
        import asyncio
        
        start_time = datetime.now()
        while True:
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout_seconds:
                return None
            
            instance = await self.get_instance(linode_id)
            status = instance.get("status")
            
            if status == "running":
                # 获取公网 IPv4
                ipv4 = instance.get("ipv4", [])
                if ipv4:
                    return ipv4[0]
            
            await asyncio.sleep(poll_interval)
    
    async def delete_all_instances(self, label_prefix: str = "swipe-") -> int:
        """
        删除所有匹配标签前缀的实例 (紧急销毁功能)
        
        Args:
            label_prefix: 标签前缀
            
        Returns:
            删除的实例数量
        """
        instances = await self.list_instances(label_prefix)
        deleted_count = 0
        
        for instance in instances:
            linode_id = instance["id"]
            if await self.delete_instance(linode_id):
                deleted_count += 1
        
        return deleted_count
    
    async def get_monthly_cost(self) -> float:
        """
        获取本月预计费用
        
        Returns:
            费用 (USD)
        """
        # 使用账户接口获取账单信息
        response = await self._client.get("/account/invoices")
        if response.status_code != 200:
            return 0.0
        
        # 简化处理：累加所有活跃实例的小时费用
        instances = await self.list_instances()
        total_hourly = sum(
            i.get("type", {}).get("price", {}).get("hourly", 0)
            for i in instances
        )
        
        # 粗略估算本月费用 (假设运行至月底)
        now = datetime.now()
        days_in_month = 30
        hours_remaining = (days_in_month - now.day) * 24 + (24 - now.hour)
        
        return total_hourly * hours_remaining
    
    async def close(self):
        """关闭 HTTP 客户端"""
        await self._client.aclose()


class LinodeError(Exception):
    """Linode API 错误"""
    pass


# 单例管理器
_linode_manager: Optional[LinodeManager] = None


def get_linode_manager() -> LinodeManager:
    """获取 Linode 管理器单例"""
    global _linode_manager
    if _linode_manager is None:
        _linode_manager = LinodeManager()
    return _linode_manager
