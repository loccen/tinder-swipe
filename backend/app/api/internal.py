"""
内部 API (供采集器调用)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.models import Task, TaskStatus
from app.schemas import TaskCreate, TaskResponse, MessageResponse

router = APIRouter(prefix="/tasks/internal", tags=["internal"])


@router.post("/create", response_model=TaskResponse)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    创建新任务 (内部 API，供采集器调用)
    """
    # 检查是否已存在
    existing = await db.execute(
        select(Task).where(
            Task.telegram_chat_id == task_data.telegram_chat_id,
            Task.telegram_msg_id == task_data.telegram_msg_id,
            Task.source_url == task_data.source_url
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="任务已存在")
    
    # 创建任务
    task = Task(
        telegram_msg_id=task_data.telegram_msg_id,
        telegram_chat_id=task_data.telegram_chat_id,
        source_url=task_data.source_url,
        title=task_data.title,
        description=task_data.description,
        file_size=task_data.file_size,
        preview_image=task_data.preview_image,
        status=TaskStatus.PENDING.value
    )
    
    # 设置多张预览图
    if task_data.preview_images:
        task.set_preview_images_list(task_data.preview_images)
    elif task_data.preview_image:
        task.set_preview_images_list([task_data.preview_image])
    
    db.add(task)
    
    try:
        await db.commit()
        await db.refresh(task)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="任务已存在")
    
    return TaskResponse.from_task(task)

