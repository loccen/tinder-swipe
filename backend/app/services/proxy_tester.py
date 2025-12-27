"""
代理测试服务
"""
import asyncio
import json
import logging
import os
import tempfile
from typing import Optional

import httpx
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class ProxyTester:
    """代理连通性测试器"""
    
    def __init__(self):
        self.settings = get_settings()
        # 探测路径优先级：/usr/local/bin -> backend/bin -> bin -> system PATH
        possible_paths = [
            "/usr/local/bin/hysteria",
            os.path.join(os.getcwd(), "bin", "hysteria"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "bin", "hysteria"),
            "hysteria"
        ]
        
        self.hysteria_path = "hysteria"
        for path in possible_paths:
            if "/" in path and os.path.exists(path):
                self.hysteria_path = path
                break
        
        logger.info(f"ProxyTester 初始化，使用 Hysteria 路径: {self.hysteria_path}")
            
    async def check_proxy_ip(self, ip: str, port: int, password: str) -> Optional[str]:
        """
        通过 Hysteria2 代理查询出口 IP
        
        Returns:
            出口 IP 或 None (失败)
        """
        # 1. 创建临时配置文件
        socks5_port = 10800 + (hash(ip) % 1000) # 简单端口分配逻辑
        
        config = {
            "server": f"{ip}:{port}",
            "auth": password,
            "tls": {
                "insecure": True # 自签名证书需允许不安全连接
            },
            "socks5": {
                "listen": f"127.0.0.1:{socks5_port}"
            },
            "transport": {
                "type": "udp"
            }
        }
        
        config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        try:
            json.dump(config, config_file)
            config_file.close()
            
            # 2. 启动 Hysteria 客户端
            process = await asyncio.create_subprocess_exec(
                self.hysteria_path, "client", "-c", config_file.name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # 等待客户端建立连接 (5秒)
            await asyncio.sleep(5)
            
            try:
                # 3. 使用 httpx 通过 SOCKS5 代理请求 IP 查询服务
                # 注意：需要安装 httpx[socks]
                async with httpx.AsyncClient(
                    proxy=f"socks5://127.0.0.1:{socks5_port}",
                    verify=False,
                    timeout=10.0
                ) as client:
                    response = await client.get("https://ifconfig.me/ip")
                    if response.status_code == 200:
                        return response.text.strip()
            except Exception as e:
                logger.error(f"代理请求失败: {e}")
            finally:
                # 4. 关闭进程
                if process.returncode is None:
                    process.terminate()
                    await process.wait()
                    
        finally:
            if os.path.exists(config_file.name):
                os.unlink(config_file.name)
                
        return None

_proxy_tester = ProxyTester()

def get_proxy_tester() -> ProxyTester:
    return _proxy_tester
