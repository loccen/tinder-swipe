"""
Telegram 采集引擎

监听指定频道，提取磁力/PikPak 链接，保存预览图
支持动态热重载频道配置
支持关联临近时间窗口内的图片和文本
"""
import asyncio
import logging
import os
import re
import sys
import json
from collections import defaultdict
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, Dict, Union

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


@dataclass
class PendingResource:
    """待处理的资源 (等待关联预览图)"""
    chat_id: int
    msg_id: int
    source_url: str
    title: str
    description: str = ""
    preview_images: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class RecentMedia:
    """最近的媒体消息 (用于关联到资源)"""
    chat_id: int
    msg_id: int
    image_path: Optional[str] = None
    text: str = ""
    created_at: datetime = field(default_factory=datetime.now)


class TelegramCollector:
    """Telegram 消息采集器 (支持热重载 + 时间窗口关联)"""
    
    # 链接匹配正则
    MAGNET_PATTERN = re.compile(r'magnet:\?xt=urn:[a-z0-9]+:[a-zA-Z0-9]{32,}[^\s]*', re.IGNORECASE)
    PIKPAK_PATTERN = re.compile(r'https?://mypikpak\.com/s/[A-Za-z0-9]+', re.IGNORECASE)
    
    # 时间窗口 (秒)
    ASSOCIATION_WINDOW = 30
    
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
        self.channels = set(channels)
        self.session_path = session_path
        self.previews_path = Path(previews_path)
        self.backend_url = backend_url
        
        self._client: Optional[TelegramClient] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._processed_ids: Set[str] = set()
        self._running = False
        self._reload_task: Optional[asyncio.Task] = None
        self._flush_task: Optional[asyncio.Task] = None
        
        # 按频道存储最近的媒体消息 (用于关联)
        self._recent_media: Dict[int, List[RecentMedia]] = defaultdict(list)
        # 等待关联的资源
        self._pending_resources: Dict[str, PendingResource] = {}
        
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
        
        await self._client.start(phone=self.phone)
        self._running = True
        
        # 注册消息处理器
        @self._client.on(events.NewMessage())
        async def handler(event):
            await self._handle_message(event)
        
        logger.info(f"采集器已启动，监听频道: {list(self.channels)}")
        
        # 启动后台任务
        self._reload_task = asyncio.create_task(self._reload_channels_loop())
        self._flush_task = asyncio.create_task(self._flush_pending_resources_loop())
        
        # 保持运行
        await self._client.run_until_disconnected()
    
    async def stop(self):
        """停止采集器"""
        self._running = False
        if self._reload_task:
            self._reload_task.cancel()
        if self._flush_task:
            self._flush_task.cancel()
        if self._client:
            await self._client.disconnect()
        if self._http_client:
            await self._http_client.aclose()
        logger.info("采集器已停止")
    
    async def _reload_channels_loop(self):
        """定期从后端 API 获取频道配置"""
        while self._running:
            try:
                await asyncio.sleep(30)
                await self._reload_channels()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"重载频道配置失败: {e}")
    
    async def _flush_pending_resources_loop(self):
        """定期提交等待关联的资源"""
        while self._running:
            try:
                await asyncio.sleep(5)  # 每5秒检查一次
                await self._flush_pending_resources()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"提交待处理资源失败: {e}")
    
    async def _flush_pending_resources(self):
        """提交已超过时间窗口的资源"""
        now = datetime.now()
        to_submit = []
        
        for key, resource in list(self._pending_resources.items()):
            # 超过30秒后提交
            if (now - resource.created_at).total_seconds() > self.ASSOCIATION_WINDOW:
                to_submit.append(resource)
                del self._pending_resources[key]
        
        for resource in to_submit:
            await self._submit_resource(resource)
        
        # 清理过期的媒体缓存
        for chat_id in list(self._recent_media.keys()):
            self._recent_media[chat_id] = [
                m for m in self._recent_media[chat_id]
                if (now - m.created_at).total_seconds() < 60  # 保留1分钟内的
            ]
    
    async def _reload_channels(self):
        """从后端 API 获取最新的频道配置"""
        try:
            response = await self._http_client.get("/api/settings/channels")
            if response.status_code == 200:
                data = response.json()
                new_channels = set()
                for ch in data.get("channels", []):
                    ch_id = ch.get("id") if isinstance(ch, dict) else ch
                    try:
                        ch_id = int(ch_id)
                    except (ValueError, TypeError):
                        pass
                    new_channels.add(ch_id)
                
                if new_channels != self.channels:
                    added = new_channels - self.channels
                    removed = self.channels - new_channels
                    if added:
                        logger.info(f"新增监听频道: {list(added)}")
                    if removed:
                        logger.info(f"移除监听频道: {list(removed)}")
                    self.channels = new_channels
        except Exception as e:
            logger.debug(f"获取频道配置失败: {e}")
    
    def _is_monitored_channel(self, chat_id: int, username: Optional[str] = None) -> bool:
        """检查是否是监听的频道"""
        if chat_id in self.channels or str(chat_id) in self.channels:
            return True
        if username and username in self.channels:
            return True
        return False
    
    async def _handle_message(self, event):
        """处理新消息"""
        try:
            chat_id = event.chat_id
            
            # 检查是否在监听列表中
            try:
                chat = await event.get_chat()
                username = getattr(chat, 'username', None)
                if not self._is_monitored_channel(chat_id, username):
                    return
            except:
                if not self._is_monitored_channel(chat_id):
                    return
            
            message = event.message
            msg_id = message.id
            text = message.raw_text or ""
            
            # 防重复处理
            unique_key = f"{chat_id}_{msg_id}"
            if unique_key in self._processed_ids:
                return
            self._processed_ids.add(unique_key)
            
            # 限制缓存大小
            if len(self._processed_ids) > 10000:
                self._processed_ids = set(list(self._processed_ids)[-5000:])
            
            # 查找链接
            urls = self._extract_urls(text)
            
            # 处理媒体消息 (可能是预览图)
            if message.media:
                image_path = await self._download_preview(message, chat_id, msg_id)
                if image_path:
                    media = RecentMedia(
                        chat_id=chat_id,
                        msg_id=msg_id,
                        image_path=image_path,
                        text=text if not urls else "",  # 如果没有链接，保存文本作为描述
                        created_at=datetime.now()
                    )
                    self._recent_media[chat_id].append(media)
                    
                    # 尝试关联到已有的待处理资源
                    await self._try_associate_media(chat_id, media)
            
            # 如果有链接，创建资源
            if urls:
                title = self._extract_title(text)
                description = self._extract_description(text)
                
                for url in urls:
                    resource_key = f"{chat_id}_{url}"
                    
                    # 获取30秒内的图片
                    preview_images = self._get_recent_images(chat_id)
                    # 获取30秒内的描述文本
                    if not description:
                        description = self._get_recent_description(chat_id)
                    
                    resource = PendingResource(
                        chat_id=chat_id,
                        msg_id=msg_id,
                        source_url=url,
                        title=title,
                        description=description,
                        preview_images=preview_images,
                        created_at=datetime.now()
                    )
                    
                    # 存入待处理队列，等待更多关联
                    self._pending_resources[resource_key] = resource
                    logger.info(f"发现资源: {title[:30]}..., 当前预览图: {len(preview_images)}张")
                    
        except Exception as e:
            logger.error(f"处理消息异常: {e}")
    
    def _get_recent_images(self, chat_id: int) -> List[str]:
        """获取30秒内的图片"""
        now = datetime.now()
        images = []
        for media in self._recent_media.get(chat_id, []):
            if media.image_path and (now - media.created_at).total_seconds() < self.ASSOCIATION_WINDOW:
                images.append(media.image_path)
        return images
    
    def _get_recent_description(self, chat_id: int) -> str:
        """获取30秒内的描述文本"""
        now = datetime.now()
        for media in reversed(self._recent_media.get(chat_id, [])):
            if media.text and (now - media.created_at).total_seconds() < self.ASSOCIATION_WINDOW:
                return media.text
        return ""
    
    async def _try_associate_media(self, chat_id: int, media: RecentMedia):
        """尝试将媒体关联到待处理的资源"""
        for key, resource in self._pending_resources.items():
            if resource.chat_id == chat_id:
                # 检查时间窗口
                if abs((media.created_at - resource.created_at).total_seconds()) < self.ASSOCIATION_WINDOW:
                    if media.image_path and media.image_path not in resource.preview_images:
                        resource.preview_images.append(media.image_path)
                        logger.debug(f"关联预览图到资源: {resource.title[:20]}...")
                    if media.text and not resource.description:
                        resource.description = media.text
    
    async def _submit_resource(self, resource: PendingResource):
        """提交资源到后端"""
        try:
            payload = {
                "telegram_chat_id": resource.chat_id,
                "telegram_msg_id": resource.msg_id,
                "source_url": resource.source_url,
                "title": resource.title,
                "description": resource.description,
                "preview_image": resource.preview_images[0] if resource.preview_images else None,
                "preview_images": resource.preview_images
            }
            
            response = await self._http_client.post(
                "/api/tasks/internal/create",
                json=payload
            )
            
            if response.status_code == 200:
                logger.info(f"任务创建成功: {resource.title[:30]}... (预览图: {len(resource.preview_images)}张)")
                
        except Exception as e:
            logger.error(f"创建任务失败: {e}")
    
    def _extract_urls(self, text: str) -> List[str]:
        """从文本中提取资源链接"""
        urls = []
        magnets = self.MAGNET_PATTERN.findall(text)
        urls.extend(magnets)
        pikpaks = self.PIKPAK_PATTERN.findall(text)
        urls.extend(pikpaks)
        return list(set(urls))
    
    def _extract_title(self, text: str) -> str:
        """提取资源标题"""
        if not text:
            return ""
        
        first_line = text.split("\n")[0].strip()
        
        # 移除常见的前缀标记
        prefixes = ["#", "【", "「", "《", "🎬", "📺", "🔥", "📽️", "🎞️"]
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
        
        if len(first_line) > 100:
            first_line = first_line[:100] + "..."
        
        return first_line
    
    def _extract_description(self, text: str) -> str:
        """提取资源描述 (除标题和链接外的文本)"""
        if not text:
            return ""
        
        lines = text.split("\n")
        if len(lines) <= 1:
            return ""
        
        # 跳过第一行(标题)，过滤掉链接行
        desc_lines = []
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            # 跳过链接行
            if self.MAGNET_PATTERN.search(line) or self.PIKPAK_PATTERN.search(line):
                continue
            desc_lines.append(line)
        
        description = "\n".join(desc_lines[:5])  # 最多5行
        if len(description) > 500:
            description = description[:500] + "..."
        
        return description
    
    async def _download_preview(
        self,
        message,
        chat_id: int,
        msg_id: int
    ) -> Optional[str]:
        """下载消息中的预览图"""
        try:
            media = message.media
            filename = f"{chat_id}_{msg_id}"
            
            if isinstance(media, MessageMediaPhoto):
                filename += ".jpg"
            elif isinstance(media, MessageMediaDocument):
                if hasattr(media.document, 'thumbs') and media.document.thumbs:
                    filename += ".jpg"
                else:
                    return None
            else:
                return None
            
            filepath = self.previews_path / filename
            
            await self._client.download_media(
                message,
                file=str(filepath),
                thumb=-1
            )
            
            logger.debug(f"预览图已保存: {filename}")
            return filename
            
        except Exception as e:
            logger.warning(f"下载预览图失败: {e}")
            return None


async def main():
    """主入口"""
    api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    phone = os.getenv("TELEGRAM_PHONE", "")
    channels_str = os.getenv("TELEGRAM_CHANNELS", "[]")
    
    if not api_id or not api_hash or not phone:
        logger.error("缺少 Telegram 配置，请设置环境变量")
        sys.exit(1)
    
    try:
        channels = json.loads(channels_str)
    except json.JSONDecodeError:
        channels = []
    
    if not channels:
        logger.warning("未配置初始监听频道，将从后端 API 获取")
    
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
