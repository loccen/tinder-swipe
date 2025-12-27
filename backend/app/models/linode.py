"""
Linode 实例模型
"""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.batch import Batch


class LinodeStatus(str, Enum):
    """Linode 状态枚举"""
    PROVISIONING = "PROVISIONING"   # 创建中
    RUNNING = "RUNNING"             # 运行中
    DESTROYING = "DESTROYING"       # 销毁中
    DESTROYED = "DESTROYED"         # 已销毁
    ZOMBIE = "ZOMBIE"               # 僵尸实例 (需要人工处理)


class Linode(Base, TimestampMixin):
    """Linode 实例模型"""
    
    __tablename__ = "linodes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Linode 信息
    linode_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    region: Mapped[str] = mapped_column(String(32), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    
    # 代理配置
    hysteria_port: Mapped[int] = mapped_column(Integer, default=443)
    hysteria_password: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # 状态管理
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=LinodeStatus.PROVISIONING.value
    )
    
    # 成本追踪
    hourly_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_minutes: Mapped[int] = mapped_column(Integer, default=0)
    
    # 时间戳
    ready_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    destroyed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # 关系
    batches: Mapped[List["Batch"]] = relationship("Batch", back_populates="linode")
    
    __table_args__ = (
        Index("idx_linodes_linode_id", "linode_id", unique=True),
        Index("idx_linodes_status", "status"),
    )
