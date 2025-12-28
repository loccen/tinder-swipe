"""
任务模型
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List
import json

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "PENDING"                       # 待筛选
    CONFIRMED = "CONFIRMED"                   # 已确认，等待转存
    PIKPAK_TRANSFERRING = "PIKPAK_TRANSFERRING"  # PikPak 转存中
    DOWNLOADING = "DOWNLOADING"               # Aria2 下载中
    COMPLETE = "COMPLETE"                     # 下载完成
    IGNORED = "IGNORED"                       # 已忽略
    ERROR = "ERROR"                           # 下载失败


class Task(Base, TimestampMixin):
    """资源任务模型"""
    
    __tablename__ = "tasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 来源信息
    telegram_msg_id: Mapped[int] = mapped_column(Integer, nullable=False)
    telegram_chat_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 资源元数据
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 资源描述文本
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    preview_image: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # 兼容旧数据
    preview_images: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 数组存储多张图片
    
    # 状态管理
    status: Mapped[str] = mapped_column(
        String(32), 
        nullable=False, 
        default=TaskStatus.PENDING.value
    )
    
    # 批次关联
    batch_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("batches.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # 下载详情
    pikpak_file_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    pikpak_file_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # 用于按名查找
    aria2_gids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 数组存储多个 GID
    download_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # 时间戳
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # 关系
    batch: Mapped[Optional["Batch"]] = relationship("Batch", back_populates="tasks")
    
    __table_args__ = (
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_batch_id", "batch_id"),
        Index("idx_tasks_telegram", "telegram_chat_id", "telegram_msg_id", unique=True),
    )
    
    def get_preview_images_list(self) -> List[str]:
        """获取预览图列表"""
        images = []
        # 优先使用新字段
        if self.preview_images:
            try:
                images = json.loads(self.preview_images)
            except json.JSONDecodeError:
                pass
        # 兼容旧数据
        if not images and self.preview_image:
            images = [self.preview_image]
        return images
    
    def set_preview_images_list(self, images: List[str]):
        """设置预览图列表"""
        self.preview_images = json.dumps(images) if images else None
        # 同时设置第一张图到旧字段，保持兼容
        self.preview_image = images[0] if images else None
    
    def get_aria2_gids(self) -> List[str]:
        """获取 Aria2 GID 列表"""
        if self.aria2_gids:
            try:
                return json.loads(self.aria2_gids)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_aria2_gids(self, gids: List[str]):
        """设置 Aria2 GID 列表"""
        self.aria2_gids = json.dumps(gids) if gids else None


# 延迟导入，避免循环引用
from app.models.batch import Batch

