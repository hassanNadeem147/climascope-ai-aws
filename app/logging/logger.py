from pathlib import Path
import sys
from loguru import logger
# Point to project root /logs folder
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
# Remove default console handler
logger.remove()

# 1. Console Output (Terminal)
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)

# add a file handler for logging to a info_file
logger.add(
    LOG_DIR / "app_info.log",
    level="INFO",
    filter=lambda record: record["level"].name in ["INFO", "WARNING"],
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
           "{name}:{function}:{line} - {message}",
    rotation="10 MB",
    retention="7 days",
    compression="zip",
)

# add a file handler for logging to a error_file
logger.add(
    LOG_DIR / "app_error.log",
    level="ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
           "{name}:{function}:{line} - {message}",
    rotation="10 MB",
    retention="7 days",
    compression="zip",
)