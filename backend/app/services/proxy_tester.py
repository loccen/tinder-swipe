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
            
            logger.info(f"Hysteria 客户端已启动 (PID: {process.pid})，等待握手...")
            
            # 等待客户端建立连接 (延长至 10 秒)
            await asyncio.sleep(10)
            
            # 检查进程是否还在运行
            if process.returncode is not None:
                _, stderr = await process.communicate()
                logger.error(f"Hysteria 客户端意外退出 (Code: {process.returncode}): {stderr.decode()}")
                return None

            try:
                # 3. 使用 httpx 通过 SOCKS5 代理请求 IP 查询服务
                # 注意：需要安装 httpx[socks]
                async with httpx.AsyncClient(
                    proxy=f"socks5://127.0.0.1:{socks5_port}",
                    verify=False,
                    timeout=15.0
                ) as client:
                    logger.info(f"正在通过 SOCKS5:{socks5_port} 发起测试请求...")
                    response = await client.get("https://ifconfig.me/ip")
                    if response.status_code == 200:
                        return response.text.strip()
            except Exception as e:
                # 请求失败时，尝试获取一些 Hysteria 的输出以便排查
                logger.error(f"代理请求失败: {e}")
                # 注意：这里不能用 wait() 否则会阻塞。稍微读取一下 stderr
                try:
                    # 尝试非阻塞读取一部分 stderr
                    # 由于 asyncio 限制，这里简单 terminate 后获取全部比较稳妥
                    pass
                except:
                    pass
            finally:
                # 4. 关闭进程
                if process.returncode is None:
                    process.terminate()
                    stdout, stderr = await process.communicate()
                    if stderr:
                        logger.info(f"Hysteria 客户端输出: {stderr.decode()[:500]}")
                    
        finally:
            if os.path.exists(config_file.name):
                os.unlink(config_file.name)
                
        return None

_proxy_tester = ProxyTester()

def get_proxy_tester() -> ProxyTester:
    return _proxy_tester
