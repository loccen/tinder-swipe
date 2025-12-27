"""
任务相关 API 路由
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Task, TaskStatus
from app.schemas import (
    TaskResponse, 
    TaskAction, 
    PendingTasksResponse,
    MessageResponse
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/pending", response_model=PendingTasksResponse)
async def get_pending_tasks(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """获取待筛选的任务列表"""
    # 查询总数
    count_stmt = select(func.count()).select_from(Task).where(
        Task.status == TaskStatus.PENDING.value
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar()
    
    # 查询任务列表
    stmt = (
        select(Task)
        .where(Task.status == TaskStatus.PENDING.value)
        .order_by(Task.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    
    return PendingTasksResponse(
        tasks=[TaskResponse.from_task(t) for t in tasks],
        total=total
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取任务详情"""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return TaskResponse.from_task(task)


@router.post("/{task_id}/action", response_model=TaskResponse)
async def task_action(
    task_id: int,
    action: TaskAction,
    db: AsyncSession = Depends(get_db)
):
    """
    执行任务操作
    
    - **confirm**: 确认下载 (左滑)
    - **ignore**: 忽略任务 (右滑)
    """
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status != TaskStatus.PENDING.value:
        raise HTTPException(
            status_code=400, 
            detail=f"任务状态为 {task.status}，无法执行此操作"
        )
    
    if action.action == "confirm":
        task.status = TaskStatus.CONFIRMED.value
        task.confirmed_at = datetime.now()
    elif action.action == "ignore":
        task.status = TaskStatus.IGNORED.value
    
    await db.commit()
    await db.refresh(task)
    
    return TaskResponse.from_task(task)


@router.get("", response_model=PendingTasksResponse)
async def list_tasks(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """获取任务列表 (可按状态过滤)"""
    # 构建查询条件
    conditions = []
    if status:
        conditions.append(Task.status == status)
    
    # 查询总数
    count_stmt = select(func.count()).select_from(Task)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar()
    
    # 查询列表
    stmt = select(Task).order_by(Task.created_at.desc()).offset(offset).limit(limit)
    if conditions:
        stmt = stmt.where(*conditions)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    
    return PendingTasksResponse(
        tasks=[TaskResponse.from_task(t) for t in tasks],
        total=total
    )
