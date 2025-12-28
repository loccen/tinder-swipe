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
from collections import defaultdict
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, Dict, Union

from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
import httpx

from app.core.config import get_settings

logger = logging.getLogger("backend.telegram")


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
    PIKPAK_PATTERN = re.compile(r'https?://mypikpak\.com/s/[A-Za-z0-9_-]+', re.IGNORECASE)
    
    # 时间窗口 (秒)
    ASSOCIATION_WINDOW = 30
    
    def __init__(self):
        settings = get_settings()
        
        self.api_id = settings.telegram_api_id
        self.api_hash = settings.telegram_api_hash
        self.phone = settings.telegram_phone
        self.channels = set(settings.telegram_channels)
        self.session_path = settings.session_path
        self.previews_path = Path(settings.previews_path)
        
        self._client: Optional[TelegramClient] = None
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
        
        # 不保持运行，让 FastAPI 控制生命周期
        logger.info("Telegram 采集器后台任务已启动")
    
    async def stop(self):
        """停止采集器"""
        self._running = False
        if self._reload_task:
            self._reload_task.cancel()
        if self._flush_task:
            self._flush_task.cancel()
        if self._client:
            await self._client.disconnect()
        logger.info("Telegram 采集器已停止运行")
    
    async def _reload_channels_loop(self):
        """定期从配置获取频道配置"""
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
        """从数据库或配置获取最新的频道配置"""
        try:
            # 这里可以从数据库读取配置
            # 现在暂时保持频道列表不变
            settings = get_settings()
            new_channels = set(settings.telegram_channels)
            
            if new_channels != self.channels:
                added = new_channels - self.channels
                removed = self.channels - new_channels
                if added:
                    logger.info(f"配置更新: 新增监听频道 {list(added)}")
                if removed:
                    logger.info(f"配置更新: 移除监听频道 {list(removed)}")
                self.channels = new_channels
            else:
                logger.debug("频道配置未发生变化")
        except Exception as e:
            logger.error(f"重载频道配置过程发生异常: {str(e)}", exc_info=True)
    
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
                    logger.debug(f"跳过非监听频道消息: chat_id={chat_id}, username={username}")
                    return
            except Exception as chat_err:
                if not self._is_monitored_channel(chat_id):
                    logger.debug(f"获取聊天信息失败且不在直接监听列表，跳过消息: chat_id={chat_id}, error={chat_err}")
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
            if urls:
                logger.info(f"发现资源消息: chat_id={chat_id}, msg_id={msg_id}, 包含链接数={len(urls)}")
                logger.debug(f"提取到的链接: {urls}")
            
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
                    logger.info(f"已下载预览图: {image_path}, 准备尝试关联资源...")
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
                    logger.info(f"任务已加入待处理队列 (等待关联更多分片): {title[:30]}..., 当前预览图: {len(preview_images)}张, key={resource_key}")
                    
        except Exception as e:
            logger.error(f"处理消息异常: {e}", exc_info=True)
    
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
        """提交资源到内部 API（直接调用服务层）"""
        try:
            # 导入服务层，避免循环导入
            from app.api.internal import create_task_internal
            
            payload = {
                "telegram_chat_id": resource.chat_id,
                "telegram_msg_id": resource.msg_id,
                "source_url": resource.source_url,
                "title": resource.title,
                "description": resource.description,
                "preview_image": resource.preview_images[0] if resource.preview_images else None,
                "preview_images": resource.preview_images
            }
            
            # 直接调用内部函数而非 HTTP 请求
            await create_task_internal(payload)
            logger.info(f"任务创建成功: {resource.title[:30]}... (预览图: {len(resource.preview_images)}张)")
            
        except Exception as e:
            logger.error(f"创建任务失败: {e}", exc_info=True)
    
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


# 全局单例
_collector: Optional[TelegramCollector] = None


def get_telegram_collector() -> TelegramCollector:
    """获取 Telegram 采集器单例"""
    global _collector
    if _collector is None:
        _collector = TelegramCollector()
    return _collector
