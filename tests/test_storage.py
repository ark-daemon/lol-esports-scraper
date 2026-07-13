from pathlib import Path

import pytest

from lol_esports_scraper.models import MatchRecord, ParsedBatch
from lol_esports_scraper.storage import Database


@pytest.mark.asyncio
async def test_storage_initializes_and_upserts_match(tmp_path: Path) -> None:
    db = Database(tmp_path / "lol.db")
    await db.initialize()
    match = MatchRecord(source="gol", tournament="LCK Spring", match_date="2026-01-01", team1="T1", team2="GEN")
    await db.upsert_batch(ParsedBatch(matches=[match]))

    counts = await db.status_counts()

    assert counts["matches"] == 1
    assert counts["games"] == 0
