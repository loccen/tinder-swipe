"""
Pydantic 数据模型 (API 请求/响应)
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Task 相关
# =============================================================================

class TaskBase(BaseModel):
    """任务基础模型"""
    source_url: str
    title: Optional[str] = None
    description: Optional[str] = None  # 资源描述文本
    file_size: int = 0
    preview_image: Optional[str] = None  # 兼容旧数据
    preview_images: List[str] = []  # 多张预览图


class TaskCreate(TaskBase):
    """创建任务请求"""
    telegram_msg_id: int
    telegram_chat_id: int


class TaskResponse(TaskBase):
    """任务响应"""
    id: int
    telegram_msg_id: int
    telegram_chat_id: int
    status: str
    batch_id: Optional[int] = None
    aria2_gid: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
    
    @classmethod
    def from_task(cls, task) -> "TaskResponse":
        """从 Task 模型创建响应，处理 preview_images"""
        return cls(
            id=task.id,
            telegram_msg_id=task.telegram_msg_id,
            telegram_chat_id=task.telegram_chat_id,
            source_url=task.source_url,
            title=task.title,
            description=task.description,
            file_size=task.file_size,
            preview_image=task.preview_image,
            preview_images=task.get_preview_images_list(),
            status=task.status,
            batch_id=task.batch_id,
            aria2_gid=task.aria2_gid,
            error_message=task.error_message,
            created_at=task.created_at,
            confirmed_at=task.confirmed_at,
            completed_at=task.completed_at
        )


class TaskAction(BaseModel):
    """任务操作请求"""
    action: str = Field(..., pattern="^(confirm|ignore)$")


class PendingTasksResponse(BaseModel):
    """待处理任务列表响应"""
    tasks: List[TaskResponse]
    total: int


# =============================================================================
# Batch 相关
# =============================================================================

class BatchResponse(BaseModel):
    """批次响应"""
    id: int
    status: str
    linode_id: Optional[int] = None
    task_count: int
    completed_count: int
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    created_at: datetime
    activated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# =============================================================================
# Linode 相关
# =============================================================================

class LinodeResponse(BaseModel):
    """Linode 实例响应"""
    id: int
    linode_id: int
    label: Optional[str] = None
    region: str
    ip_address: Optional[str] = None
    status: str
    hysteria_port: int
    total_minutes: int
    hourly_cost: float
    created_at: datetime
    ready_at: Optional[datetime] = None
    destroyed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# =============================================================================
# Dashboard 相关
# =============================================================================

class DashboardStats(BaseModel):
    """仪表盘统计信息"""
    pending_count: int = Field(description="待筛选任务数")
    confirmed_count: int = Field(description="已确认任务数")
    downloading_count: int = Field(description="下载中任务数")
    completed_count: int = Field(description="已完成任务数")
    error_count: int = Field(description="失败任务数")


class LinodeStatus(BaseModel):
    """Linode 实例状态"""
    is_running: bool
    linode_id: Optional[int] = None
    ip_address: Optional[str] = None
    uptime_minutes: int = 0
    estimated_cost: float = Field(description="预计费用 (USD)")


class Aria2Stats(BaseModel):
    """Aria2 统计信息"""
    download_speed: int = Field(description="下载速度 (Bytes/s)")
    upload_speed: int = Field(description="上传速度 (Bytes/s)")
    active_count: int = Field(description="活跃任务数")
    waiting_count: int = Field(description="等待任务数")
    stopped_count: int = Field(description="停止任务数")


class DashboardResponse(BaseModel):
    """仪表盘响应"""
    stats: DashboardStats
    linode: LinodeStatus
    aria2: Aria2Stats
    monthly_cost: float = Field(description="本月累计费用 (USD)")


class ProxyCheckResponse(BaseModel):
    """代理检查响应"""
    ip: Optional[str] = None
    success: bool
    error: Optional[str] = None


# =============================================================================
# 通用响应
# =============================================================================

class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str
    success: bool = True


class EmergencyDestroyResponse(BaseModel):
    """紧急销毁响应"""
    message: str
    destroyed_count: int
