"""
编排引擎 (Orchestrator)

核心职责：
1. 监控 CONFIRMED 状态的任务，执行聚合策略
2. 管理 Linode 实例生命周期
3. 协调 Aria2 代理配置
4. 监控下载进度，完成后销毁实例
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_context
from app.models import (
    Task, TaskStatus,
    Batch, BatchStatus,
    Linode, LinodeStatus
)
from app.services.aria2_client import get_aria2_client
from app.services.linode_manager import get_linode_manager
from app.services.pikpak_service import get_pikpak_service

logger = logging.getLogger(__name__)


class Orchestrator:
    """资源编排引擎"""
    
    def __init__(self):
        self.settings = get_settings()
        self._running = False
        self._current_batch_id: Optional[int] = None
        self._aggregation_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动编排引擎"""
        if self._running:
            logger.warning("编排引擎已在运行")
            return
        
        self._running = True
        logger.info("编排引擎启动")
        
        # 恢复僵尸实例
        await self._recover_zombie_instances()
        
        # 恢复由于重启中断的 PROVISIONING 批次
        await self._resume_provisioning_batches()
        
        # 启动后台任务
        self._aggregation_task = asyncio.create_task(self._aggregation_loop())
        self._monitor_task = asyncio.create_task(self._monitor_loop())
    
    async def stop(self):
        """停止编排引擎"""
        self._running = False
        
        if self._aggregation_task:
            self._aggregation_task.cancel()
        if self._monitor_task:
            self._monitor_task.cancel()
        
        logger.info("编排引擎已停止")
    
    async def _recover_zombie_instances(self):
        """系统启动时恢复对僵尸实例的管理"""
        logger.info("检查僵尸实例...")
        
        linode_manager = get_linode_manager()
        
        async with get_db_context() as db:
            # 查询未销毁的实例记录
            stmt = select(Linode).where(
                Linode.status.notin_([LinodeStatus.DESTROYED.value])
            )
            result = await db.execute(stmt)
            local_instances = result.scalars().all()
            
            if not local_instances:
                logger.info("无僵尸实例")
                return
            
            # 获取 Linode API 中的实际实例
            try:
                remote_instances = await linode_manager.list_instances(
                    label_prefix="swipe-"
                )
                remote_ids = {i["id"] for i in remote_instances}
            except Exception as e:
                logger.error(f"获取远程实例列表失败: {e}")
                return
            
            for local in local_instances:
                if local.linode_id in remote_ids:
                    # 实例仍存在，标记为僵尸待处理
                    if local.status != LinodeStatus.RUNNING.value:
                        local.status = LinodeStatus.ZOMBIE.value
                        logger.warning(
                            f"发现僵尸实例: {local.linode_id} ({local.ip_address})"
                        )
                else:
                    # 实例已不存在，更新状态
                    local.status = LinodeStatus.DESTROYED.value
                    local.destroyed_at = datetime.now()
                    logger.info(f"实例 {local.linode_id} 已不存在，更新状态")
            
            await db.commit()
            
    async def _resume_provisioning_batches(self):
        """恢复处于 PROVISIONING 状态的批次"""
        logger.info("检查并恢复处理中的批次...")
        async with get_db_context() as db:
            stmt = select(Batch).where(
                Batch.status == BatchStatus.PROVISIONING.value
            )
            result = await db.execute(stmt)
            batches = result.scalars().all()
            
            for batch in batches:
                if batch.linode_id:
                    logger.info(f"重新接管批次 #{batch.id} (Linode ID: {batch.linode_id})")
                    asyncio.create_task(
                        self._wait_and_activate_batch(batch.id, batch.linode_id)
                    )
            
            await db.commit()
    
    async def _aggregation_loop(self):
        """聚合策略主循环"""
        while self._running:
            try:
                await self._check_and_start_batch()
            except Exception as e:
                logger.error(f"聚合循环异常: {e}")
            
            await asyncio.sleep(5)  # 每 5 秒检查一次
    
    async def _check_and_start_batch(self):
        """检查是否需要启动新批次或触发下载"""
        async with get_db_context() as db:
            # 1. 获取当前聚合中的批次
            stmt = select(Batch).where(
                Batch.status == BatchStatus.AGGREGATING.value
            )
            result = await db.execute(stmt)
            current_batch = result.scalar_one_or_none()
            
            # 2. 检查系统是否由于已有活跃批次而处于“繁忙”状态
            busy_stmt = select(func.count()).select_from(Batch).where(
                Batch.status.in_([
                    BatchStatus.PROVISIONING.value,
                    BatchStatus.ACTIVE.value
                ])
            )
            busy_result = await db.execute(busy_stmt)
            if busy_result.scalar() > 0:
                # 系统繁忙，暂不启动新批次，但可以继续往当前 AGGREGATING 批次加任务
                if current_batch is None:
                    return

            # 3. 统计新生成的 CONFIRMED 任务数
            count_stmt = select(func.count()).select_from(Task).where(
                Task.status == TaskStatus.CONFIRMED.value,
                Task.batch_id.is_(None)
            )
            count_result = await db.execute(count_stmt)
            pending_count = count_result.scalar()
            
            # 3. 如果既无当前批次也无新任务，直接返回
            if current_batch is None and pending_count == 0:
                return
            
            now = datetime.now()
            
            # 4. 如果没批次但有新任务，创建新批次
            if current_batch is None:
                window_end = now + timedelta(
                    minutes=self.settings.aggregation_window_minutes
                )
                current_batch = Batch(
                    status=BatchStatus.AGGREGATING.value,
                    window_start=now,
                    window_end=window_end
                )
                db.add(current_batch)
                await db.flush()
                logger.info(
                    f"创建新批次 #{current_batch.id}，聚合窗口至 {window_end}"
                )
            
            # 5. 将新产生的任务关联到当前批次
            if pending_count > 0:
                await self._assign_tasks_to_batch(db, current_batch.id)
                # 刷新批次对象以获取最新的 task_count
                await db.refresh(current_batch)
            
            # 6. 检查触发条件
            should_trigger = False
            
            # 条件1: 达到任务阈值
            if current_batch.task_count >= self.settings.batch_task_threshold:
                logger.info(f"批次 #{current_batch.id} 达到任务阈值 ({current_batch.task_count})，触发下载")
                should_trigger = True
            
            # 条件2: 聚合窗口结束
            elif current_batch.window_end and now >= current_batch.window_end:
                logger.info(f"批次 #{current_batch.id} 聚合窗口结束，触发下载")
                should_trigger = True
            
            if should_trigger and current_batch.task_count > 0:
                await self._start_batch_download(db, current_batch)
            
            await db.commit()
    
    async def _assign_tasks_to_batch(self, db: AsyncSession, batch_id: int):
        """将未分配的 CONFIRMED 任务关联到批次"""
        stmt = (
            update(Task)
            .where(
                Task.status == TaskStatus.CONFIRMED.value,
                Task.batch_id.is_(None)
            )
            .values(batch_id=batch_id)
        )
        result = await db.execute(stmt)
        assigned_count = result.rowcount
        
        if assigned_count > 0:
            # 更新批次任务计数
            batch_stmt = (
                update(Batch)
                .where(Batch.id == batch_id)
                .values(task_count=Batch.task_count + assigned_count)
            )
            await db.execute(batch_stmt)
            logger.info(f"批次 #{batch_id} 新增 {assigned_count} 个任务")
    
    async def _start_batch_download(self, db: AsyncSession, batch: Batch):
        """启动批次下载 (创建 Linode + 配置代理)"""
        batch.status = BatchStatus.PROVISIONING.value
        await db.flush()
        
        try:
            linode_manager = get_linode_manager()
            
            # 创建实例
            label = f"swipe-batch-{batch.id}"
            instance_data = await linode_manager.create_instance(label=label)
            
            linode_id = instance_data["id"]
            hysteria_port = instance_data["hysteria_port"]
            hysteria_password = instance_data["hysteria_password"]
            region = instance_data["region"]
            
            # 保存实例记录
            linode = Linode(
                linode_id=linode_id,
                label=label,
                region=region,
                hysteria_port=hysteria_port,
                hysteria_password=hysteria_password,
                status=LinodeStatus.PROVISIONING.value
            )
            db.add(linode)
            await db.flush()
            
            batch.linode_id = linode.id
            
            logger.info(f"Linode 实例 {linode_id} 创建成功，等待就绪...")
            
            # 等待实例运行 (后台执行)
            asyncio.create_task(
                self._wait_and_activate_batch(batch.id, linode.id)
            )
            
        except Exception as e:
            logger.error(f"启动批次 #{batch.id} 下载流程失败: {e}")
            batch.status = BatchStatus.FAILED.value
            
            # 将关联任务打回 CONFIRMED 状态以待后续批次处理
            await db.execute(
                update(Task)
                .where(Task.batch_id == batch.id)
                .values(batch_id=None)
            )
            # 如果已有 Linode 记录但创建过程中断，尝试销毁（虽然此时可能并未成功创建）
            if batch.linode_id:
                linode = await db.get(Linode, batch.linode_id)
                if linode:
                    asyncio.create_task(self._destroy_linode_orphan(linode.linode_id))
    
    async def _wait_and_activate_batch(self, batch_id: int, linode_db_id: int):
        """等待 Linode 就绪并激活批次下载"""
        linode_manager = get_linode_manager()
        aria2_client = get_aria2_client()
        
        # 增加重试逻辑，应对数据库事务提交的竞态条件
        linode = None
        for _ in range(5):
            async with get_db_context() as db:
                linode = await db.get(Linode, linode_db_id)
                if linode:
                    break
                await asyncio.sleep(1)
        
        if not linode:
            logger.error(f"Linode 记录 {linode_db_id} 经过重试后仍不存在")
            return
            
        async with get_db_context() as db:
            # 重新获取对象以绑定到当前 session
            linode = await db.get(Linode, linode_db_id)
            
            # 等待实例运行
            ip_address = await linode_manager.wait_for_running(
                linode.linode_id, timeout_seconds=300
            )
            
            if not ip_address:
                logger.error(f"Linode {linode.linode_id} 启动超时")
                linode.status = LinodeStatus.ZOMBIE.value
                await db.commit()
                return
            
            # 更新实例信息
            linode.ip_address = ip_address
            linode.status = LinodeStatus.RUNNING.value
            linode.ready_at = datetime.now()
            
            logger.info(f"Linode {linode.linode_id} 已就绪: {ip_address}")
            
            # 等待 Hysteria2 服务启动 (额外等待 30 秒)
            await asyncio.sleep(30)
            
            # 配置 Aria2 代理
            proxy_url = f"hysteria2://{linode.hysteria_password}@{ip_address}:{linode.hysteria_port}"
            try:
                await aria2_client.set_proxy(proxy_url)
                logger.info(f"Aria2 代理已配置: {ip_address}")
            except Exception as e:
                logger.error(f"配置 Aria2 代理失败: {e}")
            
            # 更新批次状态
            batch = await db.get(Batch, batch_id)
            if batch:
                batch.status = BatchStatus.ACTIVE.value
                batch.activated_at = datetime.now()
            
            await db.commit()
            
            # 开始推送下载任务
            await self._push_download_tasks(batch_id)
    
    async def _push_download_tasks(self, batch_id: int):
        """将批次内的任务推送至 Aria2"""
        aria2_client = get_aria2_client()
        pikpak_service = get_pikpak_service()
        
        async with get_db_context() as db:
            # 获取批次内的任务
            stmt = select(Task).where(
                Task.batch_id == batch_id,
                Task.status == TaskStatus.CONFIRMED.value
            )
            result = await db.execute(stmt)
            tasks = result.scalars().all()
            
            for task in tasks:
                try:
                    await self._process_single_task(
                        db, task, pikpak_service, aria2_client
                    )
                except Exception as e:
                    logger.error(f"处理任务 {task.id} 失败: {e}")
                    task.status = TaskStatus.ERROR.value
                    task.error_message = str(e)
            
            await db.commit()
    
    async def _process_single_task(
        self,
        db: AsyncSession,
        task: Task,
        pikpak_service,
        aria2_client
    ):
        """处理单个下载任务"""
        source_url = task.source_url
        
        # 判断链接类型
        if pikpak_service.is_magnet_link(source_url):
            # 磁力链接：先离线下载到 PikPak
            logger.info(f"任务 {task.id}: 离线下载磁力链接...")
            result = await pikpak_service.offline_download(source_url)
            file_id = result.get("task", {}).get("file_id")
            if not file_id:
                raise Exception("PikPak 离线下载失败")
            task.pikpak_file_id = file_id
            
            # 等待离线完成 (简化处理，实际应轮询)
            await asyncio.sleep(10)
        else:
            # PikPak 分享链接：执行转存
            logger.info(f"任务 {task.id}: 转存分享链接内容...")
            file_ids = await pikpak_service.transfer_share_content(source_url)
            if not file_ids:
                raise Exception("PikPak 转存分享失败")
            
            # 记录其中一个文件 ID 以便后续递归提取 (通常分享里包含的主要内容)
            task.pikpak_file_id = file_ids[0]
            
            # 转存通常很快，但也稍微等一下确保网盘可见
            await asyncio.sleep(3)
        
        # 获取视频文件列表
        if task.pikpak_file_id:
            videos = await pikpak_service.get_video_files_recursive(
                task.pikpak_file_id
            )
            
            if not videos:
                logger.warning(f"任务 {task.id}: 未找到视频文件")
                return
            
            # 推送到 Aria2
            for file_id, filename, file_size, download_url in videos:
                gid = await aria2_client.add_uri(
                    [download_url],
                    options={
                        "dir": self.settings.download_base_path,
                        "out": filename
                    }
                )
                logger.info(f"任务 {task.id}: 已推送 {filename} -> GID: {gid}")
                
                # 只记录最后一个 GID (简化)
                task.aria2_gid = gid
        
        task.status = TaskStatus.DOWNLOADING.value
    
    async def _monitor_loop(self):
        """监控下载进度和实例销毁"""
        while self._running:
            try:
                await self._check_batch_completion()
                await self._check_batch_timeouts()
                await self._cleanup_orphan_instances()
                await self._check_and_push_active_tasks()
                await self._update_linode_cost()
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
            
            await asyncio.sleep(30)  # 每 30 秒检查一次
    
    async def _check_batch_completion(self):
        """检查批次是否完成"""
        aria2_client = get_aria2_client()
        
        async with get_db_context() as db:
            # 获取活跃批次
            stmt = select(Batch).where(
                Batch.status == BatchStatus.ACTIVE.value
            )
            result = await db.execute(stmt)
            active_batches = result.scalars().all()
            
            for batch in active_batches:
                # 获取批次内的下载中任务
                task_stmt = select(Task).where(
                    Task.batch_id == batch.id,
                    Task.status == TaskStatus.DOWNLOADING.value
                )
                task_result = await db.execute(task_stmt)
                downloading_tasks = task_result.scalars().all()
                
                all_complete = True
                
                for task in downloading_tasks:
                    if task.aria2_gid:
                        try:
                            status = await aria2_client.tell_status(
                                task.aria2_gid,
                                ["status"]
                            )
                            aria2_status = status.get("status")
                            
                            if aria2_status == "complete":
                                task.status = TaskStatus.COMPLETE.value
                                task.completed_at = datetime.now()
                                batch.completed_count += 1
                            elif aria2_status == "error":
                                task.status = TaskStatus.ERROR.value
                                task.error_message = "Aria2 下载失败"
                            else:
                                all_complete = False
                        except Exception as e:
                            logger.warning(f"查询任务 {task.id} 状态失败: {e}")
                            all_complete = False
                
                # 检查是否全部完成
                if all_complete and downloading_tasks:
                    await self._complete_batch(db, batch)
            
            await db.commit()
    
    async def _complete_batch(self, db: AsyncSession, batch: Batch):
        """完成批次并销毁 Linode"""
        logger.info(f"批次 #{batch.id} 全部任务完成")
        
        batch.status = BatchStatus.COMPLETED.value
        batch.completed_at = datetime.now()
        
        # 清除 Aria2 代理
        aria2_client = get_aria2_client()
        try:
            await aria2_client.set_proxy(None)
            logger.info("Aria2 代理已清除")
        except Exception as e:
            logger.warning(f"清除代理失败: {e}")
        
        # 销毁 Linode
        if batch.linode_id:
            linode = await db.get(Linode, batch.linode_id)
            if linode and linode.status == LinodeStatus.RUNNING.value:
                await self._destroy_linode(db, linode)
    
    async def _destroy_linode(self, db: AsyncSession, linode: Linode):
        """销毁 Linode 实例"""
        linode_manager = get_linode_manager()
        
        linode.status = LinodeStatus.DESTROYING.value
        await db.flush()
        
        try:
            success = await linode_manager.delete_instance(linode.linode_id)
            if success:
                linode.status = LinodeStatus.DESTROYED.value
                linode.destroyed_at = datetime.now()
                
                # 计算运行时长
                if linode.ready_at:
                    minutes = int(
                        (datetime.now() - linode.ready_at).total_seconds() / 60
                    )
                    linode.total_minutes = minutes
                
                logger.info(f"Linode {linode.linode_id} 已销毁")
            else:
                linode.status = LinodeStatus.ZOMBIE.value
                logger.error(f"Linode {linode.linode_id} 销毁失败")
        except Exception as e:
            linode.status = LinodeStatus.ZOMBIE.value
            logger.error(f"销毁 Linode 异常: {e}")
    
    async def _update_linode_cost(self):
        """更新 Linode 运行成本"""
        # 简化实现：每次循环更新运行中实例的分钟数
        async with get_db_context() as db:
            stmt = select(Linode).where(
                Linode.status == LinodeStatus.RUNNING.value
            )
            result = await db.execute(stmt)
            running_instances = result.scalars().all()
            
            for linode in running_instances:
                if linode.ready_at:
                    minutes = int(
                        (datetime.now() - linode.ready_at).total_seconds() / 60
                    )
                    linode.total_minutes = minutes
            
            await db.commit()
    
    async def emergency_destroy_all(self) -> int:
        """紧急销毁所有实例"""
        logger.warning("执行紧急销毁！")
        
        linode_manager = get_linode_manager()
        
        # 直接调用 API 销毁
        deleted_count = await linode_manager.delete_all_instances("swipe-")
        
        # 更新数据库记录
        async with get_db_context() as db:
            stmt = (
                update(Linode)
                .where(Linode.status != LinodeStatus.DESTROYED.value)
                .values(
                    status=LinodeStatus.DESTROYED.value,
                    destroyed_at=datetime.now()
                )
            )
            await db.execute(stmt)
            
            # 清除代理
            aria2_client = get_aria2_client()
            try:
                await aria2_client.set_proxy(None)
            except:
                pass
            
            await db.commit()
        
        logger.warning(f"已销毁 {deleted_count} 个实例")
        return deleted_count


    async def _check_batch_timeouts(self):
        """检查长时间卡住的批次并进行回收"""
        async with get_db_context() as db:
            # 查找卡在 PROVISIONING 超过 10 分钟的批次
            timeout_limit = datetime.now() - timedelta(minutes=10)
            stmt = select(Batch).where(
                Batch.status == BatchStatus.PROVISIONING.value,
                Batch.updated_at < timeout_limit
            )
            result = await db.execute(stmt)
            stuck_batches = result.scalars().all()
            
            for batch in stuck_batches:
                logger.warning(f"批次 #{batch.id} 启动超时，尝试回收...")
                batch.status = BatchStatus.FAILED.value
                
                # 重置任务
                await db.execute(
                    update(Task)
                    .where(Task.batch_id == batch.id)
                    .values(batch_id=None)
                )
                
                # 标记 Linode 为僵尸
                if batch.linode_id:
                    linode = await db.get(Linode, batch.linode_id)
                    if linode:
                        linode.status = LinodeStatus.ZOMBIE.value
            
            await db.commit()

    async def _cleanup_orphan_instances(self):
        """清理不属于任何活跃批次的 Linode 实例"""
        async with get_db_context() as db:
            # 获取所有非销毁状态的 Linode
            stmt = select(Linode).where(Linode.status != LinodeStatus.DESTROYED.value)
            result = await db.execute(stmt)
            linodes = result.scalars().all()
            
            for linode in linodes:
                # 检查是否有批次正在引用它
                batch_stmt = select(func.count()).select_from(Batch).where(
                    Batch.linode_id == linode.id,
                    Batch.status.in_([
                        BatchStatus.PROVISIONING.value,
                        BatchStatus.ACTIVE.value
                    ])
                )
                batch_result = await db.execute(batch_stmt)
                if batch_result.scalar() == 0:
                    # 如果没有活跃批次引用，且超过 5 分钟（给新实例一些宽限期），则销毁
                    grace_period = datetime.now() - timedelta(minutes=5)
                    if linode.created_at < grace_period:
                        logger.warning(f"发现孤儿 Linode {linode.linode_id}，正在清理...")
                        await self._destroy_linode(db, linode)
            
            await db.commit()

    async def _check_and_push_active_tasks(self):
        """检查活跃批次中是否有尚未推送的任务并进行补推"""
        async with get_db_context() as db:
            # 查找所有活跃状态的批次
            stmt = select(Batch).where(Batch.status == BatchStatus.ACTIVE.value)
            result = await db.execute(stmt)
            active_batches = result.scalars().all()
            
            for batch in active_batches:
                # 检查该批次下是否有处于 CONFIRMED 状态的任务
                task_stmt = select(func.count()).select_from(Task).where(
                    Task.batch_id == batch.id,
                    Task.status == TaskStatus.CONFIRMED.value
                )
                task_count_result = await db.execute(task_stmt)
                if task_count_result.scalar() > 0:
                    logger.info(f"发现活跃批次 #{batch.id} 存在待处理任务，尝试推送...")
                    # 重新触发推送逻辑
                    asyncio.create_task(self._push_download_tasks(batch.id))

    async def _destroy_linode_orphan(self, linode_id: int):
        """后台销毁孤儿实例"""
        try:
            linode_manager = get_linode_manager()
            await linode_manager.delete_instance(linode_id)
            logger.info(f"已清理孤儿 Linode 实例: {linode_id}")
        except Exception as e:
            logger.error(f"清理孤儿实例 {linode_id} 失败: {e}")


# 全局编排器实例
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """获取编排器单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
