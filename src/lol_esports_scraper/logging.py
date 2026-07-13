from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def configure_logging(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level="INFO", colorize=True, enqueue=True)
    logger.add(
        logs_dir / "scraper_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="14 days",
        serialize=True,
        enqueue=True,
        level="DEBUG",
    )
