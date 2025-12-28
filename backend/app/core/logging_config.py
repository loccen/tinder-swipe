import os
import logging
import logging.handlers
import sys
from pathlib import Path

def setup_logging(name: str = "backend", level=logging.INFO):
    """
    统一的日志配置
    - 格式包含时间、级别、文件名、行号、函数名
    - 支持控制台输出和文件滚动持久化
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s - %(message)s"
    
    # 获取日志目录，优先使用环境变量
    log_dir = Path(os.getenv("LOG_DIR", "/data/logs"))
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError):
        # 如果无法创建目录（如权限问题或 macOS 本地运行），回退到项目根目录下的 logs
        # app/core/logging_config.py -> app/core -> app -> backend -> logs
        log_dir = Path(__file__).parent.parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
    log_file = log_dir / f"{name}.log"
    
    # 配置根日志
    root_logger = logging.getLogger()
    
    # 清理旧的 handler
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.setLevel(level)
    
    # 控制台 Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)
    
    # 文件滚动 Handler
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Failed to setup file logging: {e}")
    
    return logging.getLogger(name)
