"""
核心配置模块
"""
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True  # 同时支持别名和字段名
    )
    
    # 数据库
    database_path: str = Field(default="/data/swipe.db", alias="DATABASE_PATH")
    
    # Telegram
    telegram_api_id: Optional[int] = Field(default=None, alias="TELEGRAM_API_ID")
    telegram_api_hash: Optional[str] = Field(default=None, alias="TELEGRAM_API_HASH")
    telegram_phone: Optional[str] = Field(default=None, alias="TELEGRAM_PHONE")
    telegram_channels_raw: str = Field(default="[]", alias="TELEGRAM_CHANNELS")
    session_path: str = Field(default="/sessions/collector", alias="SESSION_PATH")
    
    @property
    def telegram_channels(self) -> List[Union[str, int]]:
        """解析 Telegram 频道列表"""
        import json
        try:
            channels = json.loads(self.telegram_channels_raw)
            # 转换数字字符串为整数
            result = []
            for ch in channels:
                if isinstance(ch, str) and ch.lstrip('-').isdigit():
                    result.append(int(ch))
                else:
                    result.append(ch)
            return result
        except json.JSONDecodeError:
            return []

    
    # PikPak
    pikpak_username: Optional[str] = Field(default=None, alias="PIKPAK_USERNAME")
    pikpak_password: Optional[str] = Field(default=None, alias="PIKPAK_PASSWORD")
    
    # Linode
    linode_token: Optional[str] = Field(default=None, alias="LINODE_TOKEN")
    linode_region: str = Field(default="ap-northeast", alias="LINODE_REGION")
    linode_type: str = Field(default="g6-nanode-1", alias="LINODE_TYPE")
    
    # SOCKS5 代理配置 (固定配置，所有实例使用相同的凭据)
    socks5_port: int = Field(default=1080, alias="SOCKS5_PORT")
    socks5_username: str = Field(default="proxy", alias="SOCKS5_USERNAME")
    socks5_password: str = Field(default="swipe2024", alias="SOCKS5_PASSWORD")
    
    # Aria2
    aria2_rpc_url: str = Field(default="http://localhost:6800/jsonrpc", alias="ARIA2_RPC_URL")
    aria2_rpc_secret: Optional[str] = Field(default=None, alias="ARIA2_RPC_SECRET")
    
    # 系统配置
    aggregation_window_minutes: int = Field(default=5, alias="AGGREGATION_WINDOW_MINUTES")
    batch_task_threshold: int = Field(default=10, alias="BATCH_TASK_THRESHOLD")
    idle_destroy_minutes: int = Field(default=15, alias="IDLE_DESTROY_MINUTES")
    download_base_path: str = Field(default="/downloads", alias="DOWNLOAD_BASE_PATH")
    
    # 预览图路径
    previews_path: str = Field(default="/data/previews", alias="PREVIEWS_PATH")
    
    @property
    def database_url(self) -> str:
        """SQLite 数据库 URL"""
        return f"sqlite+aiosqlite:///{self.database_path}"



@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
