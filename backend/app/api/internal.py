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


async def create_task_internal(task_data: dict, db: AsyncSession = None):
    """
    内部任务创建函数 (供 Telegram collector 直接调用)
    
    Args:
        task_data: 任务数据字典
        db: 数据库会话，如果为 None 则创建新会话
    """
    from app.core.database import async_session_maker
    
    # 如果没有传入 db，创建新会话
    should_close = False
    if db is None:
        db = async_session_maker()
        should_close = True
    
    try:
        # 检查是否已存在
        existing = await db.execute(
            select(Task).where(
                Task.telegram_chat_id == task_data.get("telegram_chat_id"),
                Task.telegram_msg_id == task_data.get("telegram_msg_id"),
                Task.source_url == task_data.get("source_url")
            )
        )
        if existing.scalar_one_or_none():
            return None  # 任务已存在，跳过
        
        # 创建任务
        task = Task(
            telegram_msg_id=task_data.get("telegram_msg_id"),
            telegram_chat_id=task_data.get("telegram_chat_id"),
            source_url=task_data.get("source_url"),
            title=task_data.get("title"),
            description=task_data.get("description"),
            file_size=task_data.get("file_size"),
            preview_image=task_data.get("preview_image"),
            status=TaskStatus.PENDING.value
        )
        
        # 设置多张预览图
        preview_images = task_data.get("preview_images")
        preview_image = task_data.get("preview_image")
        if preview_images:
            task.set_preview_images_list(preview_images)
        elif preview_image:
            task.set_preview_images_list([preview_image])
        
        db.add(task)
        await db.commit()
        await db.refresh(task)
        
        return task
        
    except IntegrityError:
        await db.rollback()
        return None  # 任务已存在
    finally:
        if should_close:
            await db.close()


@router.post("/create", response_model=TaskResponse)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    创建新任务 (内部 API，供采集器调用)
    """
    # 转换为字典并调用内部函数
    data_dict = task_data.model_dump()
    task = await create_task_internal(data_dict, db)
    
    if task is None:
        raise HTTPException(status_code=409, detail="任务已存在")
    
    return TaskResponse.from_task(task)
