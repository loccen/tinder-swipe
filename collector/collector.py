"""
Telegram 采集引擎

监听指定频道，提取磁力/PikPak 链接，保存预览图
"""
import asyncio
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Union

from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
import httpx

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("collector")


class TelegramCollector:
    """Telegram 消息采集器"""
    
    # 链接匹配正则
    MAGNET_PATTERN = re.compile(r'magnet:\?xt=urn:[a-z0-9]+:[a-zA-Z0-9]{32,}[^\s]*', re.IGNORECASE)
    PIKPAK_PATTERN = re.compile(r'https?://mypikpak\.com/s/[A-Za-z0-9]+', re.IGNORECASE)
    
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        phone: str,
        channels: List[Union[str, int]],
        session_path: str = "/sessions/collector",
        previews_path: str = "/data/previews",
        backend_url: str = "http://backend:8000"
    ):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.channels = channels
        self.session_path = session_path
        self.previews_path = Path(previews_path)
        self.backend_url = backend_url
        
        self._client: Optional[TelegramClient] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._processed_ids: Set[str] = set()  # 防重复处理
        
        # 确保目录存在
        self.previews_path.mkdir(parents=True, exist_ok=True)
        Path(self.session_path).parent.mkdir(parents=True, exist_ok=True)
    
    async def start(self):
        """启动采集器"""
        logger.info("正在启动 Telegram 采集器...")
        
        self._http_client = httpx.AsyncClient(
            base_url=self.backend_url,
            timeout=30.0
        )
        
        self._client = TelegramClient(
            self.session_path,
            self.api_id,
            self.api_hash
        )
        
        # 注册消息处理器
        @self._client.on(events.NewMessage(chats=self.channels))
        async def handler(event):
            await self._handle_message(event)
        
        await self._client.start(phone=self.phone)
        logger.info(f"采集器已启动，监听频道: {self.channels}")
        
        # 保持运行
        await self._client.run_until_disconnected()
    
    async def stop(self):
        """停止采集器"""
        if self._client:
            await self._client.disconnect()
        if self._http_client:
            await self._http_client.aclose()
        logger.info("采集器已停止")
    
    async def _handle_message(self, event):
        """处理新消息"""
        try:
            message = event.message
            chat_id = event.chat_id
            msg_id = message.id
            
            # 防重复处理
            unique_key = f"{chat_id}_{msg_id}"
            if unique_key in self._processed_ids:
                return
            
            # 提取文本
            text = message.raw_text or ""
            
            # 查找链接
            urls = self._extract_urls(text)
            if not urls:
                return
            
            logger.info(f"发现资源: 频道={chat_id}, 消息={msg_id}, 链接数={len(urls)}")
            
            # 提取标题 (取文本第一行或前50字符)
            title = self._extract_title(text)
            
            # 下载预览图
            preview_path = None
            if message.media:
                preview_path = await self._download_preview(
                    message, chat_id, msg_id
                )
            
            # 为每个链接创建任务
            for url in urls:
                await self._create_task(
                    chat_id=chat_id,
                    msg_id=msg_id,
                    source_url=url,
                    title=title,
                    preview_image=preview_path
                )
            
            self._processed_ids.add(unique_key)
            
            # 限制缓存大小
            if len(self._processed_ids) > 10000:
                self._processed_ids = set(list(self._processed_ids)[-5000:])
                
        except Exception as e:
            logger.error(f"处理消息异常: {e}")
    
    def _extract_urls(self, text: str) -> List[str]:
        """从文本中提取资源链接"""
        urls = []
        
        # 磁力链接
        magnets = self.MAGNET_PATTERN.findall(text)
        urls.extend(magnets)
        
        # PikPak 分享链接
        pikpaks = self.PIKPAK_PATTERN.findall(text)
        urls.extend(pikpaks)
        
        return list(set(urls))  # 去重
    
    def _extract_title(self, text: str) -> str:
        """提取资源标题"""
        if not text:
            return ""
        
        # 取第一行
        first_line = text.split("\n")[0].strip()
        
        # 移除常见的前缀标记
        prefixes = ["#", "【", "「", "《", "🎬", "📺", "🔥"]
        for prefix in prefixes:
            if first_line.startswith(prefix):
                first_line = first_line[len(prefix):].strip()
                break
        
        # 移除后缀标记
        suffixes = ["】", "」", "》"]
        for suffix in suffixes:
            if suffix in first_line:
                idx = first_line.index(suffix)
                first_line = first_line[:idx].strip()
                break
        
        # 限制长度
        if len(first_line) > 100:
            first_line = first_line[:100] + "..."
        
        return first_line
    
    async def _download_preview(
        self,
        message,
        chat_id: int,
        msg_id: int
    ) -> Optional[str]:
        """下载消息中的预览图"""
        try:
            media = message.media
            
            # 确定保存路径
            filename = f"{chat_id}_{msg_id}"
            
            if isinstance(media, MessageMediaPhoto):
                filename += ".jpg"
            elif isinstance(media, MessageMediaDocument):
                # 视频则下载缩略图
                if hasattr(media.document, 'thumbs') and media.document.thumbs:
                    filename += ".jpg"
                else:
                    return None
            else:
                return None
            
            filepath = self.previews_path / filename
            
            # 下载文件 (仅下载缩略图，限制大小)
            await self._client.download_media(
                message,
                file=str(filepath),
                thumb=-1  # 下载最小的缩略图
            )
            
            logger.info(f"预览图已保存: {filename}")
            return filename
            
        except Exception as e:
            logger.warning(f"下载预览图失败: {e}")
            return None
    
    async def _create_task(
        self,
        chat_id: int,
        msg_id: int,
        source_url: str,
        title: str,
        preview_image: Optional[str]
    ):
        """调用后端 API 创建任务"""
        try:
            # 直接使用数据库 (共享 SQLite)
            # 这里简化为调用内部 API
            payload = {
                "telegram_chat_id": chat_id,
                "telegram_msg_id": msg_id,
                "source_url": source_url,
                "title": title,
                "preview_image": preview_image
            }
            
            # 由于采集器和后端共享数据库，这里直接写入
            # 使用 HTTP 调用以保持解耦
            response = await self._http_client.post(
                "/api/tasks/internal/create",
                json=payload
            )
            
            if response.status_code == 200:
                logger.info(f"任务创建成功: {title[:30]}...")
            else:
                # 可能是重复任务，忽略
                pass
                
        except Exception as e:
            logger.error(f"创建任务失败: {e}")


async def main():
    """主入口"""
    # 从环境变量读取配置
    api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    phone = os.getenv("TELEGRAM_PHONE", "")
    channels_str = os.getenv("TELEGRAM_CHANNELS", "[]")
    
    if not api_id or not api_hash or not phone:
        logger.error("缺少 Telegram 配置，请设置环境变量")
        sys.exit(1)
    
    # 解析频道列表
    import json
    try:
        channels = json.loads(channels_str)
    except json.JSONDecodeError:
        channels = []
    
    if not channels:
        logger.error("未配置监听频道")
        sys.exit(1)
    
    collector = TelegramCollector(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        channels=channels,
        session_path=os.getenv("SESSION_PATH", "/sessions/collector"),
        previews_path=os.getenv("PREVIEWS_PATH", "/data/previews"),
        backend_url=os.getenv("BACKEND_URL", "http://backend:8000")
    )
    
    try:
        await collector.start()
    except KeyboardInterrupt:
        await collector.stop()


if __name__ == "__main__":
    asyncio.run(main())
