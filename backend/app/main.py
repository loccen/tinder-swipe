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
    
    logger.info("应用启动完成")
    
    yield
    
    # 关闭时
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
    
    @app.get("/health")
    async def health_check():
        """健康检查"""
        return {"status": "ok"}
    
    return app


# 创建应用实例
app = create_app()
