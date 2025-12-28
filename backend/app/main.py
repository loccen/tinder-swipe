"""
FastAPI 主应用
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api import api_router
from app.core.config import get_settings
from app.core.database import init_db
from app.services import get_orchestrator

from app.core.logging_config import setup_logging

# 初始化日志
logger = setup_logging("backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    settings = get_settings()
    
    # 启动时
    logger.info("正在初始化数据库...")
    await init_db()
    
    # 确保预览图目录存在
    previews_path = Path(settings.previews_path)
    previews_path.mkdir(parents=True, exist_ok=True)
    
    # 启动编排器
    logger.info("正在启动编排引擎...")
    orchestrator = get_orchestrator()
    await orchestrator.start()
    
    # 启动 Telegram 采集器（如果配置了）
    telegram_collector = None
    if settings.telegram_api_id and settings.telegram_api_hash and settings.telegram_phone:
        logger.info("正在启动 Telegram 采集器...")
        from app.services.telegram import get_telegram_collector
        telegram_collector = get_telegram_collector()
        try:
            await telegram_collector.start()
        except Exception as e:
            logger.error(f"Telegram 采集器启动失败: {e}", exc_info=True)
            logger.warning("应用将继续运行，但 Telegram 监听功能不可用")
    else:
        logger.info("未配置 Telegram 参数，跳过 Telegram 采集器启动")
    
    logger.info("应用启动完成")
    
    yield
    
    # 关闭时
    if telegram_collector:
        logger.info("正在关闭 Telegram 采集器...")
        try:
            await telegram_collector.stop()
        except Exception as e:
            logger.error(f"Telegram 采集器关闭失败: {e}")
    
    logger.info("正在关闭编排引擎...")
    await orchestrator.stop()
    logger.info("应用已关闭")



def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    settings = get_settings()
    
    app = FastAPI(
        title="PikPak Tinder-Swipe API",
        description="影视资源自动化收集系统 API",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应限制具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册 API 路由
    app.include_router(api_router)
    
    # 静态文件 (预览图)
    previews_path = Path(settings.previews_path)
    if previews_path.exists():
        app.mount(
            "/previews",
            StaticFiles(directory=str(previews_path)),
            name="previews"
        )
    
    # 前端静态文件托管（生产环境）
    static_path = Path(__file__).parent.parent / "static"
    if static_path.exists():
        from fastapi.responses import FileResponse
        
        # 挂载静态资源目录（CSS、JS、图片等）
        assets_path = static_path / "assets"
        if assets_path.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")
        
        # 处理其他静态文件（如 icon、manifest 等）
        @app.get("/icon-192.png")
        @app.get("/icon-512.png")
        @app.get("/manifest.json")
        @app.get("/favicon.ico")
        async def serve_static_files(request):
            filename = request.url.path.lstrip("/")
            file_path = static_path / filename
            if file_path.exists():
                return FileResponse(file_path)
            return FileResponse(static_path / "index.html")
        
        # SPA 路由回退 - 所有未匹配的路由返回 index.html
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            # API 路由已经被 api_router 处理
            # 预览图路由已经被 /previews 挂载处理
            # 健康检查路由已经被单独定义
            # 所有其他路由返回前端应用
            index_file = static_path / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return {"error": "Frontend not found"}
    
    @app.get("/health")
    async def health_check():
        """健康检查"""
        return {"status": "ok"}
    
    return app


# 创建应用实例
app = create_app()

