"""日志：控制台 + 文件双输出，文件自动轮转

logs/jobhunting.log  (1MB × 5 个备份，自动滚动)
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LOG_DIR = _PROJECT_ROOT / "logs"
_LOG_FILE = _LOG_DIR / "jobhunting.log"

_FMT = "%(asctime)s %(levelname)-7s %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """初始化并返回名为 jobhunting 的 logger（幂等，可重复调用）"""
    logger = logging.getLogger("jobhunting")
    if logger.handlers:  # 已初始化
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    formatter = logging.Formatter(_FMT, datefmt=_DATE_FMT)

    # 控制台
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    # 文件（轮转：1MB × 5）
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            _LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        # 日志目录不可写不阻塞主流程
        logger.warning(f"日志文件初始化失败（仅控制台输出）: {e}")

    logger.propagate = False
    return logger
