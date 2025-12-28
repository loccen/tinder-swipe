"""
仪表盘 API 路由
"""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Task, TaskStatus, Linode, LinodeStatus as LinodeStatusEnum
from app.schemas import (
    DashboardResponse,
    DashboardStats,
    LinodeStatus,
    Aria2Stats,
    EmergencyDestroyResponse,
    ProxyCheckResponse
)
from app.services import get_aria2_client, get_orchestrator, get_proxy_tester

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """获取仪表盘数据"""
    
    # 1. 统计各状态的任务数
    stats = DashboardStats(
        pending_count=0,
        confirmed_count=0,
        downloading_count=0,
        completed_count=0,
        error_count=0
    )
    
    status_counts = await db.execute(
        select(Task.status, func.count())
        .group_by(Task.status)
    )
    for status, count in status_counts:
        if status == TaskStatus.PENDING.value:
            stats.pending_count = count
        elif status == TaskStatus.CONFIRMED.value:
            stats.confirmed_count = count
        elif status == TaskStatus.DOWNLOADING.value:
            stats.downloading_count = count
        elif status == TaskStatus.COMPLETE.value:
            stats.completed_count = count
        elif status == TaskStatus.ERROR.value:
            stats.error_count = count
    
    # 2. 获取运行中的 Linode 状态
    linode_status = LinodeStatus(
        is_running=False,
        estimated_cost=0.0
    )
    
    running_linode_stmt = select(Linode).where(
        Linode.status == LinodeStatusEnum.RUNNING.value
    ).limit(1)
    result = await db.execute(running_linode_stmt)
    running_linode = result.scalar_one_or_none()
    
    if running_linode:
        uptime = 0
        if running_linode.ready_at:
            uptime = int(
                (datetime.now() - running_linode.ready_at).total_seconds() / 60
            )
        
        linode_status = LinodeStatus(
            is_running=True,
            linode_id=running_linode.linode_id,
            ip_address=running_linode.ip_address,
            root_password=running_linode.root_password,
            uptime_minutes=uptime,
            estimated_cost=running_linode.hourly_cost * (uptime / 60)
        )
    
    # 3. 获取 Aria2 统计
    aria2_stats = Aria2Stats(
        download_speed=0,
        upload_speed=0,
        active_count=0,
        waiting_count=0,
        stopped_count=0
    )
    
    try:
        aria2_client = get_aria2_client()
        global_stat = await aria2_client.get_global_stat()
        aria2_stats = Aria2Stats(
            download_speed=int(global_stat.get("downloadSpeed", 0)),
            upload_speed=int(global_stat.get("uploadSpeed", 0)),
            active_count=int(global_stat.get("numActive", 0)),
            waiting_count=int(global_stat.get("numWaiting", 0)),
            stopped_count=int(global_stat.get("numStopped", 0))
        )
    except Exception:
        pass  # Aria2 不可用时保持默认值
    
    # 4. 计算本月累计费用
    monthly_cost_stmt = select(func.sum(Linode.total_minutes * Linode.hourly_cost / 60)).where(
        Linode.created_at >= datetime.now().replace(day=1, hour=0, minute=0, second=0)
    )
    cost_result = await db.execute(monthly_cost_stmt)
    monthly_cost = cost_result.scalar() or 0.0
    
    return DashboardResponse(
        stats=stats,
        linode=linode_status,
        aria2=aria2_stats,
        monthly_cost=round(monthly_cost, 4)
    )


@router.post("/emergency-destroy", response_model=EmergencyDestroyResponse)
async def emergency_destroy():
    """
    紧急销毁所有 Linode 实例
    
    ⚠️ 此操作不可逆，所有正在运行的实例将被立即销毁
    """
    orchestrator = get_orchestrator()
    destroyed_count = await orchestrator.emergency_destroy_all()
    
    return EmergencyDestroyResponse(
        message=f"已销毁 {destroyed_count} 个实例",
        destroyed_count=destroyed_count
    )


@router.post("/proxy-check", response_model=ProxyCheckResponse)
async def check_proxy_ip(db: AsyncSession = Depends(get_db)):
    """检查当前代理的出口 IP"""
    # 获取运行中的实例
    stmt = select(Linode).where(
        Linode.status == LinodeStatusEnum.RUNNING.value
    ).limit(1)
    result = await db.execute(stmt)
    linode = result.scalar_one_or_none()
    
    if not linode:
        return ProxyCheckResponse(success=False, error="当前没有运行中的代理实例")
    
    proxy_tester = get_proxy_tester()
    try:
        ip = await proxy_tester.check_proxy_ip(
            linode.ip_address,
            linode.socks5_port,
            linode.socks5_password
        )
        if ip:
            return ProxyCheckResponse(ip=ip, success=True)
        else:
            return ProxyCheckResponse(success=False, error="代理连接超时或不可达")
    except Exception as e:
        return ProxyCheckResponse(success=False, error=str(e))
