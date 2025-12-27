"""
下载批次模型
"""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.linode import Linode


class BatchStatus(str, Enum):
    """批次状态枚举"""
    AGGREGATING = "AGGREGATING"       # 聚合中 (等待更多任务)
    PROVISIONING = "PROVISIONING"     # 正在创建 Linode 实例
    ACTIVE = "ACTIVE"                 # 下载中
    COMPLETED = "COMPLETED"           # 全部完成
    FAILED = "FAILED"                 # 失败


class Batch(Base, TimestampMixin):
    """下载批次模型"""
    
    __tablename__ = "batches"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # 状态管理
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=BatchStatus.AGGREGATING.value
    )
    
    # Linode 关联
    linode_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("linodes.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # 统计信息
    task_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # 时间控制
    window_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    window_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # 时间戳
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # 关系
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="batch")
    linode: Mapped[Optional["Linode"]] = relationship("Linode", back_populates="batches")
    
    __table_args__ = (
        Index("idx_batches_status", "status"),
    )
