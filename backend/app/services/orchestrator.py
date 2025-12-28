"""
编排引擎 (Orchestrator) - 状态机驱动的定时任务模型

核心职责：
1. 确认转存任务: 处理 CONFIRMED 任务，创建实例，触发 PikPak 转存
2. Aria2 推送任务: 检查 PikPak 就绪状态，推送到 Aria2
3. 下载监控任务: 监控 Aria2 下载进度，更新完成状态
4. 自动清理任务: 系统空闲后销毁实例

使用固定标签 `swipe` 的单例 Linode 实例管理模式
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_context
from app.models import Task, TaskStatus, Linode, LinodeStatus
from app.services.aria2_client import get_aria2_client
from app.services.linode_manager import get_linode_manager
from app.services.pikpak_service import get_pikpak_service

logger = logging.getLogger(__name__)


class Orchestrator:
    """状态机驱动的编排引擎"""
    
    # 固定实例标签
    SWIPE_INSTANCE_LABEL = "swipe"
    
    def __init__(self):
        self.settings = get_settings()
        self._running = False
        self._instance_creating = False  # 内存锁，防止重复创建实例
        self._tasks: List[asyncio.Task] = []
    
    async def start(self):
        """启动编排引擎"""
        if self._running:
            logger.warning("编排引擎已在运行")
            return
        
        self._running = True
        logger.info("编排引擎启动")
        
        # 启动时同步实例状态
        await self._sync_instance_status()
        
        # 启动 4 个独立定时任务
        self._tasks = [
            asyncio.create_task(self._confirm_and_provision_loop()),  # 确认转存 (30s)
            asyncio.create_task(self._push_to_aria2_loop()),          # Aria2 推送 (30s)
            asyncio.create_task(self._monitor_downloads_loop()),       # 下载监控 (30s)
            asyncio.create_task(self._auto_cleanup_loop()),            # 自动清理 (60s)
        ]
        
        logger.info("4 个定时任务已启动")
    
    async def stop(self):
        """停止编排引擎"""
        self._running = False
        
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        logger.info("编排引擎已停止")
    
    # =========================================================================
    # 启动时恢复逻辑
    # =========================================================================
    
    async def _sync_instance_status(self):
        """系统启动时同步 swipe 实例状态"""
        logger.info("同步 swipe 实例状态...")
        
        linode_manager = get_linode_manager()
        
        try:
            # 检查远程是否存在 swipe 实例
            remote_instance = await linode_manager.get_instance_by_label(
                self.SWIPE_INSTANCE_LABEL
            )
            
            if remote_instance:
                linode_id = remote_instance["id"]
                status = remote_instance.get("status", "unknown")
                ip_address = remote_instance.get("ipv4", [None])[0]
                
                logger.info(
                    f"发现已存在的 swipe 实例: ID={linode_id}, "
                    f"状态={status}, IP={ip_address}"
                )
                
                # 同步到本地数据库
                async with get_db_context() as db:
                    # 查找或创建本地记录
                    stmt = select(Linode).where(Linode.linode_id == linode_id)
                    result = await db.execute(stmt)
                    local_linode = result.scalar_one_or_none()
                    
                    settings = get_settings()
                    
                    if local_linode is None:
                        # 远程存在但本地无记录，创建记录 (使用配置中的固定 SOCKS5 凭据)
                        local_linode = Linode(
                            linode_id=linode_id,
                            label=self.SWIPE_INSTANCE_LABEL,
                            region=remote_instance.get("region", "unknown"),
                            ip_address=ip_address,
                            status=LinodeStatus.RUNNING.value if status == "running" else LinodeStatus.PROVISIONING.value,
                            socks5_port=settings.socks5_port,
                            socks5_username=settings.socks5_username,
                            socks5_password=settings.socks5_password,
                        )
                        db.add(local_linode)
                        logger.info(f"已创建本地 Linode 记录: {linode_id}")
                    else:
                        # 更新本地状态
                        local_linode.ip_address = ip_address
                        if status == "running":
                            local_linode.status = LinodeStatus.RUNNING.value
                            if not local_linode.ready_at:
                                local_linode.ready_at = datetime.utcnow()
                    
                    await db.commit()
                    
                    # 如果实例正在运行，使用配置中的凭据配置 Aria2 代理
                    if status == "running" and ip_address:
                        await self._configure_aria2_proxy(
                            ip_address, 
                            settings.socks5_port,
                            settings.socks5_username,
                            settings.socks5_password
                        )
            else:
                logger.info("未发现远程 swipe 实例")
                
                # 清理本地可能的残留记录
                async with get_db_context() as db:
                    stmt = select(Linode).where(
                        Linode.label == self.SWIPE_INSTANCE_LABEL,
                        Linode.status != LinodeStatus.DESTROYED.value
                    )
                    result = await db.execute(stmt)
                    stale_records = result.scalars().all()
                    
                    for record in stale_records:
                        record.status = LinodeStatus.DESTROYED.value
                        record.destroyed_at = datetime.utcnow()
                        logger.warning(f"标记过期的本地记录为已销毁: {record.linode_id}")
                    
                    await db.commit()
                    
        except Exception as e:
            logger.error(f"同步实例状态失败: {e}", exc_info=True)
    
    # =========================================================================
    # 确认转存任务 (每 30s)
    # =========================================================================
    
    async def _confirm_and_provision_loop(self):
        """确认转存任务循环: 处理 CONFIRMED 任务，创建实例，触发转存"""
        while self._running:
            try:
                await self._process_confirmed_tasks()
            except Exception as e:
                logger.error(f"确认转存任务异常: {e}", exc_info=True)
            await asyncio.sleep(30)
    
    async def _process_confirmed_tasks(self):
        """处理 CONFIRMED 状态的任务"""
        async with get_db_context() as db:
            # 1. 扫描 CONFIRMED 任务
            stmt = select(Task).where(Task.status == TaskStatus.CONFIRMED.value)
            result = await db.execute(stmt)
            confirmed_tasks = result.scalars().all()
            
            if not confirmed_tasks:
                return
            
            logger.info(f"发现 {len(confirmed_tasks)} 个待处理任务")
            
            # 2. 检查 swipe 实例是否存在
            linode_manager = get_linode_manager()
            instance = await linode_manager.get_instance_by_label(
                self.SWIPE_INSTANCE_LABEL
            )
            
            if instance is None:
                # 实例不存在，触发创建
                if not self._instance_creating:
                    self._instance_creating = True
                    asyncio.create_task(self._create_swipe_instance())
                logger.info("等待 swipe 实例创建完成...")
                return
            
            if instance.get("status") != "running":
                logger.info(f"swipe 实例状态: {instance.get('status')}，等待就绪...")
                return
            
            # 3. 确保 Aria2 代理已配置
            await self._ensure_aria2_proxy_configured()
            
            # 4. 实例已就绪，执行 PikPak 转存
            pikpak_service = get_pikpak_service()
            
            for task in confirmed_tasks:
                try:
                    await self._transfer_to_pikpak(db, task, pikpak_service)
                except Exception as e:
                    logger.error(f"任务 {task.id} 转存失败: {e}", exc_info=True)
                    task.status = TaskStatus.ERROR.value
                    task.error_message = str(e)[:500]
            
            await db.commit()
    
    async def _create_swipe_instance(self):
        """创建 swipe 实例"""
        logger.info("正在创建 swipe 实例...")
        
        try:
            linode_manager = get_linode_manager()
            
            instance_data = await linode_manager.create_instance(
                label=self.SWIPE_INSTANCE_LABEL
            )
            
            linode_id = instance_data["id"]
            socks5_port = instance_data.get("socks5_port", 1080)
            socks5_username = instance_data.get("socks5_username", "proxy")
            socks5_password = instance_data.get("socks5_password", "")
            region = instance_data.get("region", "unknown")
            
            # 保存到数据库
            async with get_db_context() as db:
                linode = Linode(
                    linode_id=linode_id,
                    label=self.SWIPE_INSTANCE_LABEL,
                    region=region,
                    socks5_port=socks5_port,
                    socks5_username=socks5_username,
                    socks5_password=socks5_password,
                    status=LinodeStatus.PROVISIONING.value
                )
                db.add(linode)
                await db.commit()
            
            logger.info(f"Linode 实例 {linode_id} 创建成功，等待就绪...")
            
            # 等待实例运行
            ip_address = await linode_manager.wait_for_running(
                linode_id, timeout_seconds=300
            )
            
            if ip_address:
                async with get_db_context() as db:
                    stmt = select(Linode).where(Linode.linode_id == linode_id)
                    result = await db.execute(stmt)
                    linode = result.scalar_one_or_none()
                    
                    if linode:
                        linode.ip_address = ip_address
                        linode.status = LinodeStatus.RUNNING.value
                        linode.ready_at = datetime.utcnow()
                        await db.commit()
                
                logger.info(f"Linode {linode_id} 已就绪: {ip_address}")
                
                # 等待 SOCKS5 服务启动
                await asyncio.sleep(30)
                
                # 配置 Aria2 代理
                await self._configure_aria2_proxy(
                    ip_address, socks5_port, socks5_username, socks5_password
                )
            else:
                logger.error(f"Linode {linode_id} 启动超时")
                async with get_db_context() as db:
                    stmt = select(Linode).where(Linode.linode_id == linode_id)
                    result = await db.execute(stmt)
                    linode = result.scalar_one_or_none()
                    if linode:
                        linode.status = LinodeStatus.ZOMBIE.value
                        await db.commit()
                        
        except Exception as e:
            logger.error(f"创建 swipe 实例失败: {e}", exc_info=True)
        finally:
            self._instance_creating = False
    
    async def _transfer_to_pikpak(
        self, 
        db: AsyncSession, 
        task: Task, 
        pikpak_service
    ):
        """执行 PikPak 转存"""
        source_url = task.source_url
        
        if pikpak_service.is_magnet_link(source_url):
            # 磁力链接：离线下载
            logger.info(f"任务 {task.id}: 离线下载磁力链接...")
            result = await pikpak_service.offline_download(source_url)
            file_id = result.get("task", {}).get("file_id")
            if not file_id:
                raise Exception("PikPak 离线下载失败: 未返回 file_id")
            task.pikpak_file_id = file_id
        else:
            # PikPak 分享链接：执行转存
            logger.info(f"任务 {task.id}: 转存分享链接内容:{source_url}")
            # 返回 [(file_name, original_id), ...]
            transfer_results = await pikpak_service.transfer_share_content(source_url)
            if not transfer_results:
                raise Exception("PikPak 转存分享失败: 未返回 file_id")
            
            # 取第一个文件
            file_name, original_id = transfer_results[0]
            task.pikpak_file_id = original_id  # 暂存原始 ID，is_file_ready 会用文件名匹配
            task.pikpak_file_name = file_name  # 用于按名查找实际 ID
        
        # 更新状态
        task.status = TaskStatus.PIKPAK_TRANSFERRING.value
        logger.info(
            f"任务 {task.id} 已进入 PikPak 转存状态, "
            f"file_id={task.pikpak_file_id}, file_name={task.pikpak_file_name}"
        )
    
    # =========================================================================
    # Aria2 推送任务 (每 30s)
    # =========================================================================
    
    async def _push_to_aria2_loop(self):
        """Aria2 推送任务循环: 检查 PikPak 就绪状态，推送到 Aria2"""
        while self._running:
            try:
                await self._push_ready_transfers()
            except Exception as e:
                logger.error(f"Aria2 推送任务异常: {e}", exc_info=True)
            await asyncio.sleep(30)
    
    async def _push_ready_transfers(self):
        """检查 PikPak 转存状态并推送到 Aria2"""
        async with get_db_context() as db:
            stmt = select(Task).where(
                Task.status == TaskStatus.PIKPAK_TRANSFERRING.value
            )
            result = await db.execute(stmt)
            transferring_tasks = result.scalars().all()
            
            if not transferring_tasks:
                return
            
            logger.info(f"检查 {len(transferring_tasks)} 个转存中的任务")
            
            pikpak_service = get_pikpak_service()
            aria2_client = get_aria2_client()
            
            for task in transferring_tasks:
                try:
                    if not task.pikpak_file_id:
                        logger.warning(f"任务 {task.id} 无 pikpak_file_id，跳过")
                        continue
                    
                    # 检查文件是否就绪 (传入文件名用于按名查找)
                    is_ready, actual_file_id = await pikpak_service.is_file_ready(
                        task.pikpak_file_id,
                        task.pikpak_file_name
                    )
                    
                    if not is_ready:
                        logger.info(f"任务 {task.id} PikPak 文件尚未就绪")
                        continue
                    
                    # 如果通过文件名找到了实际 ID，更新任务
                    if actual_file_id and actual_file_id != task.pikpak_file_id:
                        logger.info(
                            f"任务 {task.id} 更新 pikpak_file_id: "
                            f"{task.pikpak_file_id} -> {actual_file_id}"
                        )
                        task.pikpak_file_id = actual_file_id
                    
                    # 获取视频文件直链并推送到 Aria2
                    await self._push_to_aria2(db, task, pikpak_service, aria2_client)
                    
                except Exception as e:
                    logger.error(f"任务 {task.id} Aria2 推送失败: {e}", exc_info=True)
                    task.status = TaskStatus.ERROR.value
                    task.error_message = str(e)[:500]
            
            await db.commit()
    
    async def _push_to_aria2(
        self,
        db: AsyncSession,
        task: Task,
        pikpak_service,
        aria2_client
    ):
        """推送任务到 Aria2"""
        logger.info(f"任务 {task.id}: 获取视频文件列表...")
        
        # 递归获取所有视频文件
        videos = await pikpak_service.get_video_files_recursive(task.pikpak_file_id)
        
        if not videos:
            logger.warning(f"任务 {task.id}: 未找到视频文件")
            task.status = TaskStatus.ERROR.value
            task.error_message = "未找到视频文件"
            return
        
        logger.info(f"任务 {task.id}: 发现 {len(videos)} 个视频文件")
        
        # 推送到 Aria2
        gids = []
        for file_id, filename, file_size, download_url in videos:
            gid = await aria2_client.add_uri(
                [download_url],
                options={
                    "dir": self.settings.download_base_path,
                    "out": filename
                }
            )
            gids.append(gid)
            logger.info(f"任务 {task.id}: 已推送 {filename} -> GID: {gid}")
        
        # 保存 GID 列表
        task.set_aria2_gids(gids)
        task.status = TaskStatus.DOWNLOADING.value
        
        logger.info(f"任务 {task.id} 已进入下载状态, {len(gids)} 个文件")
    
    # =========================================================================
    # 下载监控任务 (每 30s)
    # =========================================================================
    
    async def _monitor_downloads_loop(self):
        """下载监控任务循环: 监控 Aria2 进度，更新完成状态"""
        while self._running:
            try:
                await self._monitor_downloads()
            except Exception as e:
                logger.error(f"下载监控任务异常: {e}", exc_info=True)
            await asyncio.sleep(30)
    
    async def _monitor_downloads(self):
        """监控下载进度并更新状态"""
        async with get_db_context() as db:
            stmt = select(Task).where(Task.status == TaskStatus.DOWNLOADING.value)
            result = await db.execute(stmt)
            downloading_tasks = result.scalars().all()
            
            if not downloading_tasks:
                return
            
            aria2_client = get_aria2_client()
            
            for task in downloading_tasks:
                try:
                    gids = task.get_aria2_gids()
                    if not gids:
                        logger.warning(f"任务 {task.id} 无 aria2_gids，标记为错误")
                        task.status = TaskStatus.ERROR.value
                        task.error_message = "无下载任务 GID"
                        continue
                    
                    all_complete = True
                    has_error = False
                    
                    for gid in gids:
                        try:
                            status = await aria2_client.tell_status(gid, ["status"])
                            aria2_status = status.get("status")
                            
                            if aria2_status == "error":
                                has_error = True
                                break
                            elif aria2_status != "complete":
                                all_complete = False
                        except Exception as e:
                            # GID 可能不存在，视为完成或忽略
                            logger.warning(f"查询 GID {gid} 状态失败: {e}")
                            # 保守处理，认为还在进行中
                            all_complete = False
                    
                    if has_error:
                        task.status = TaskStatus.ERROR.value
                        task.error_message = "Aria2 下载失败"
                        logger.warning(f"任务 {task.id} 下载失败")
                    elif all_complete:
                        task.status = TaskStatus.COMPLETE.value
                        task.completed_at = datetime.utcnow()
                        logger.info(f"任务 {task.id} 下载完成")
                        
                except Exception as e:
                    logger.warning(f"监控任务 {task.id} 状态失败: {e}")
            
            await db.commit()
    
    # =========================================================================
    # 自动清理任务 (每 60s)
    # =========================================================================
    
    async def _auto_cleanup_loop(self):
        """自动清理任务循环: 系统空闲后销毁实例"""
        while self._running:
            try:
                await self._check_and_cleanup()
            except Exception as e:
                logger.error(f"自动清理任务异常: {e}", exc_info=True)
            await asyncio.sleep(60)
    
    async def _check_and_cleanup(self):
        """检查是否需要销毁实例"""
        async with get_db_context() as db:
            # 检查是否有活跃任务
            active_statuses = [
                TaskStatus.CONFIRMED.value,
                TaskStatus.PIKPAK_TRANSFERRING.value,
                TaskStatus.DOWNLOADING.value
            ]
            
            stmt = select(func.count()).select_from(Task).where(
                Task.status.in_(active_statuses)
            )
            result = await db.execute(stmt)
            active_count = result.scalar()
            
            if active_count > 0:
                return
            
            # 获取最后完成任务的时间
            stmt = select(Task.completed_at).where(
                Task.status == TaskStatus.COMPLETE.value,
                Task.completed_at.isnot(None)
            ).order_by(Task.completed_at.desc()).limit(1)
            result = await db.execute(stmt)
            last_completed = result.scalar()
            
            if last_completed is None:
                # 没有完成的任务，检查是否有未销毁的实例 (可能是遗留的)
                await self._cleanup_stale_instance()
                return
            
            # 检查是否已空闲超过 5 分钟
            idle_threshold = datetime.utcnow() - timedelta(minutes=5)
            if last_completed > idle_threshold:
                return
            
            # 执行销毁
            logger.info("系统空闲超过 5 分钟，准备销毁 swipe 实例...")
            await self._destroy_swipe_instance()
    
    async def _cleanup_stale_instance(self):
        """清理可能遗留的实例"""
        linode_manager = get_linode_manager()
        
        instance = await linode_manager.get_instance_by_label(
            self.SWIPE_INSTANCE_LABEL
        )
        
        if instance is None:
            return
        
        # 检查本地数据库中是否有活跃任务记录
        async with get_db_context() as db:
            stmt = select(Linode).where(
                Linode.label == self.SWIPE_INSTANCE_LABEL,
                Linode.status.in_([
                    LinodeStatus.PROVISIONING.value,
                    LinodeStatus.RUNNING.value
                ])
            )
            result = await db.execute(stmt)
            local_linode = result.scalar_one_or_none()
            
            if local_linode:
                # 先检查是否有活跃任务，有的话不销毁
                active_statuses = [
                    TaskStatus.CONFIRMED.value,
                    TaskStatus.PIKPAK_TRANSFERRING.value,
                    TaskStatus.DOWNLOADING.value
                ]
                stmt = select(func.count()).select_from(Task).where(
                    Task.status.in_(active_statuses)
                )
                result = await db.execute(stmt)
                if result.scalar() > 0:
                    # 有活跃任务，不销毁
                    return
                
                # 检查实例创建时间，如果超过 30 分钟且无任务，则销毁
                if local_linode.created_at:
                    age = datetime.utcnow() - local_linode.created_at
                    if age > timedelta(minutes=30):
                        logger.warning(
                            f"发现空闲超过 30 分钟的实例: {local_linode.linode_id}，执行销毁"
                        )
                        await self._destroy_swipe_instance()
    
    async def _destroy_swipe_instance(self):
        """销毁 swipe 实例"""
        linode_manager = get_linode_manager()
        
        instance = await linode_manager.get_instance_by_label(
            self.SWIPE_INSTANCE_LABEL
        )
        
        if instance is None:
            logger.info("swipe 实例不存在，无需销毁")
            return
        
        linode_id = instance["id"]
        
        try:
            # 更新本地状态
            async with get_db_context() as db:
                stmt = select(Linode).where(Linode.linode_id == linode_id)
                result = await db.execute(stmt)
                linode = result.scalar_one_or_none()
                
                if linode:
                    linode.status = LinodeStatus.DESTROYING.value
                    await db.commit()
            
            # 调用 API 删除
            success = await linode_manager.delete_instance(linode_id)
            
            async with get_db_context() as db:
                stmt = select(Linode).where(Linode.linode_id == linode_id)
                result = await db.execute(stmt)
                linode = result.scalar_one_or_none()
                
                if linode:
                    if success:
                        linode.status = LinodeStatus.DESTROYED.value
                        linode.destroyed_at = datetime.utcnow()
                        
                        if linode.ready_at:
                            minutes = int(
                                (datetime.utcnow() - linode.ready_at).total_seconds() / 60
                            )
                            linode.total_minutes = minutes
                        
                        logger.info(f"Linode {linode_id} 已销毁")
                    else:
                        linode.status = LinodeStatus.ZOMBIE.value
                        logger.error(f"Linode {linode_id} 销毁失败")
                    
                    await db.commit()
            
            # 清除 Aria2 代理
            aria2_client = get_aria2_client()
            try:
                await aria2_client.set_proxy(None)
                logger.info("Aria2 代理已清除")
            except Exception as e:
                logger.warning(f"清除代理失败: {e}")
                
        except Exception as e:
            logger.error(f"销毁 swipe 实例异常: {e}", exc_info=True)
    
    # =========================================================================
    # 辅助方法
    # =========================================================================
    
    async def _configure_aria2_proxy(
        self, 
        ip_address: str, 
        port: int, 
        username: str,
        password: str
    ):
        """
        配置 Aria2 使用远程 HTTP 代理
        
        Args:
            ip_address: 代理服务器 IP
            port: SOCKS5 端口基础值 (HTTP 端口 = port + 7000)
            username: 认证用户名
            password: 认证密码
        """
        from urllib.parse import quote
        
        # HTTP 代理端口 = SOCKS5 端口 + 7000
        http_port = port + 7000
        
        # 对密码进行 URL 编码，防止特殊字符导致解析失败
        encoded_password = quote(password, safe='')
        
        # 构建 HTTP 代理 URL (带认证)
        proxy_url = f"http://{username}:{encoded_password}@{ip_address}:{http_port}"
        
        try:
            aria2_client = get_aria2_client()
            await aria2_client.set_proxy(proxy_url)
            logger.info(f"Aria2 HTTP 代理已配置: http://{username}:***@{ip_address}:{http_port}")
        except Exception as e:
            logger.error(f"配置 Aria2 代理失败: {e}")
    
    async def _ensure_aria2_proxy_configured(self):
        """确保 Aria2 代理已配置"""
        async with get_db_context() as db:
            stmt = select(Linode).where(
                Linode.label == self.SWIPE_INSTANCE_LABEL,
                Linode.status == LinodeStatus.RUNNING.value
            )
            result = await db.execute(stmt)
            linode = result.scalar_one_or_none()
            
            if linode and linode.ip_address and linode.socks5_password:
                await self._configure_aria2_proxy(
                    linode.ip_address,
                    linode.socks5_port,
                    linode.socks5_username,
                    linode.socks5_password
                )
    
    # =========================================================================
    # 公共 API
    # =========================================================================
    
    async def emergency_destroy_all(self) -> int:
        """紧急销毁所有实例"""
        logger.warning("执行紧急销毁！")
        
        linode_manager = get_linode_manager()
        
        # 销毁所有 swipe 相关实例
        deleted_count = await linode_manager.delete_all_instances("swipe")
        
        # 更新数据库记录
        async with get_db_context() as db:
            stmt = (
                update(Linode)
                .where(Linode.status != LinodeStatus.DESTROYED.value)
                .values(
                    status=LinodeStatus.DESTROYED.value,
                    destroyed_at=datetime.utcnow()
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
    
    async def get_status(self) -> Dict[str, Any]:
        """获取编排引擎状态"""
        async with get_db_context() as db:
            # 统计各状态任务数
            status_counts = {}
            for status in TaskStatus:
                stmt = select(func.count()).select_from(Task).where(
                    Task.status == status.value
                )
                result = await db.execute(stmt)
                status_counts[status.value] = result.scalar()
            
            # 获取当前实例信息
            linode_manager = get_linode_manager()
            instance = await linode_manager.get_instance_by_label(
                self.SWIPE_INSTANCE_LABEL
            )
            
            return {
                "running": self._running,
                "instance_creating": self._instance_creating,
                "task_counts": status_counts,
                "swipe_instance": {
                    "exists": instance is not None,
                    "status": instance.get("status") if instance else None,
                    "ip": instance.get("ipv4", [None])[0] if instance else None,
                } if instance else None
            }


# 全局编排器实例
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """获取编排器单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
