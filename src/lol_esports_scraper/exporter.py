from __future__ import annotations

from pathlib import Path

import aiosqlite
import pandas as pd
from loguru import logger

from .storage import TABLES


async def export_parquet(db_path: Path, output_dir: Path, tables: list[str] | None = None) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = tables or TABLES
    written: list[Path] = []
    async with aiosqlite.connect(db_path) as db:
        for table in selected:
            if table not in TABLES:
                logger.warning("Skipping unknown table {}", table)
                continue
            cursor = await db.execute(f"SELECT * FROM {table}")
            rows = await cursor.fetchall()
            columns = [column[0] for column in (cursor.description or [])]
            frame = pd.DataFrame(rows, columns=columns)
            path = output_dir / f"{table}.parquet"
            frame.to_parquet(path, index=False)
            written.append(path)
            logger.info("Exported {} rows to {}", len(frame), path)
    return written
