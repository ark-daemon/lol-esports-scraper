from __future__ import annotations

from pathlib import Path
from typing import Iterable

import aiosqlite

from .models import (
    DraftPickRecord,
    EarningRecord,
    GameRecord,
    MatchRecord,
    ObjectiveRecord,
    ParsedBatch,
    PlayerGameStatRecord,
    PlayerRecord,
    RosterRecord,
    StaffRecord,
    TeamRecord,
    TimelineRecord,
    TournamentRecord,
    stable_key,
    to_json,
)


TABLES = [
    "matches",
    "games",
    "drafts",
    "draft_picks",
    "player_game_stats",
    "game_timelines",
    "objectives",
    "teams",
    "players",
    "rosters",
    "staff",
    "tournaments",
    "earnings",
]


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY,
    source TEXT,
    sources TEXT,
    tournament TEXT,
    region TEXT,
    split TEXT,
    date TEXT,
    team1 TEXT,
    team2 TEXT,
    team1_score INTEGER,
    team2_score INTEGER,
    series_format TEXT,
    patch TEXT,
    h2h_all_time TEXT,
    h2h_current_split TEXT,
    raw_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL,
    source TEXT,
    game_number INTEGER,
    blue_team TEXT,
    red_team TEXT,
    winner TEXT,
    duration_seconds INTEGER,
    patch TEXT,
    raw_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS drafts (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL,
    game_id TEXT,
    source TEXT,
    raw_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE,
    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS draft_picks (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL,
    game_id TEXT,
    draft_id TEXT,
    phase TEXT,
    action TEXT,
    draft_order INTEGER,
    team TEXT,
    side TEXT,
    champion TEXT,
    role TEXT,
    is_first_pick INTEGER,
    is_counter_pick INTEGER,
    champion_patch_win_rate REAL,
    champion_side_win_rate REAL,
    champion_role_win_rate REAL,
    raw_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE,
    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
    FOREIGN KEY(draft_id) REFERENCES drafts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS player_game_stats (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL,
    game_id TEXT,
    game_number INTEGER,
    team TEXT,
    player TEXT,
    champion TEXT,
    role TEXT,
    stats_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE,
    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS game_timelines (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL,
    game_id TEXT,
    game_number INTEGER,
    metrics_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE,
    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS objectives (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL,
    game_id TEXT,
    game_number INTEGER,
    objective_type TEXT,
    team TEXT,
    player TEXT,
    minute REAL,
    detail TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE,
    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    region TEXT,
    current_record TEXT,
    points TEXT,
    ranking TEXT,
    recent_form_5 TEXT,
    recent_form_10 TEXT,
    blue_side_win_rate REAL,
    red_side_win_rate REAL,
    average_game_duration_seconds INTEGER,
    raw_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    ign TEXT NOT NULL UNIQUE,
    real_name TEXT,
    role TEXT,
    nationality TEXT,
    raw_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rosters (
    id TEXT PRIMARY KEY,
    team TEXT NOT NULL,
    player TEXT NOT NULL,
    role TEXT,
    status TEXT,
    nationality TEXT,
    join_date TEXT,
    real_name TEXT,
    raw_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staff (
    id TEXT PRIMARY KEY,
    team TEXT NOT NULL,
    name TEXT NOT NULL,
    title TEXT,
    nationality TEXT,
    raw_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tournaments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    tier TEXT,
    region TEXT,
    prize_pool_total TEXT,
    stage_name TEXT,
    format TEXT,
    qualification_paths_json TEXT,
    raw_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS earnings (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    tournament TEXT,
    team TEXT,
    amount TEXT,
    placement TEXT,
    raw_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True) if self.path.parent != Path(".") else None
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    async def upsert_batch(self, batch: ParsedBatch) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await self._upsert_matches(db, batch.matches)
            await self._upsert_games(db, batch.games)
            await self._upsert_game_placeholders(db, batch)
            await self._upsert_drafts(db, batch.draft_picks)
            await self._upsert_draft_picks(db, batch.draft_picks)
            await self._upsert_player_stats(db, batch.player_stats)
            await self._upsert_timelines(db, batch.timelines)
            await self._upsert_objectives(db, batch.objectives)
            await self._upsert_teams(db, batch.teams)
            await self._upsert_players(db, batch.players)
            await self._upsert_rosters(db, batch.rosters)
            await self._upsert_staff(db, batch.staff)
            await self._upsert_tournaments(db, batch.tournaments)
            await self._upsert_earnings(db, batch.earnings)
            await db.commit()

    async def status_counts(self) -> dict[str, int]:
        await self.initialize()
        async with aiosqlite.connect(self.path) as db:
            counts: dict[str, int] = {}
            for table in TABLES:
                cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
                row = await cursor.fetchone()
                counts[table] = int(row[0])
            return counts

    async def _upsert_matches(self, db: aiosqlite.Connection, records: Iterable[MatchRecord]) -> None:
        for record in records:
            match_id = record.reconciliation_key
            existing = await (await db.execute("SELECT sources FROM matches WHERE id = ?", (match_id,))).fetchone()
            sources = set(filter(None, (existing[0].split(",") if existing and existing[0] else [])))
            sources.add(record.source)
            await db.execute(
                """
                INSERT INTO matches (
                    id, source, sources, tournament, region, split, date, team1, team2,
                    team1_score, team2_score, series_format, patch, h2h_all_time,
                    h2h_current_split, raw_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    source = COALESCE(excluded.source, matches.source),
                    sources = excluded.sources,
                    tournament = COALESCE(excluded.tournament, matches.tournament),
                    region = COALESCE(excluded.region, matches.region),
                    split = COALESCE(excluded.split, matches.split),
                    date = COALESCE(excluded.date, matches.date),
                    team1 = COALESCE(excluded.team1, matches.team1),
                    team2 = COALESCE(excluded.team2, matches.team2),
                    team1_score = COALESCE(excluded.team1_score, matches.team1_score),
                    team2_score = COALESCE(excluded.team2_score, matches.team2_score),
                    series_format = COALESCE(excluded.series_format, matches.series_format),
                    patch = COALESCE(excluded.patch, matches.patch),
                    h2h_all_time = COALESCE(excluded.h2h_all_time, matches.h2h_all_time),
                    h2h_current_split = COALESCE(excluded.h2h_current_split, matches.h2h_current_split),
                    raw_json = COALESCE(excluded.raw_json, matches.raw_json),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    match_id,
                    record.source,
                    ",".join(sorted(sources)),
                    record.tournament,
                    record.region,
                    record.split,
                    record.match_date,
                    record.team1,
                    record.team2,
                    record.team1_score,
                    record.team2_score,
                    record.series_format,
                    record.patch,
                    record.h2h_all_time,
                    record.h2h_current_split,
                    to_json(record.raw),
                ),
            )

    async def _upsert_games(self, db: aiosqlite.Connection, records: Iterable[GameRecord]) -> None:
        for record in records:
            game_id = stable_key(record.match_key, record.game_number)
            await db.execute(
                """
                INSERT INTO games (
                    id, match_id, source, game_number, blue_team, red_team, winner,
                    duration_seconds, patch, raw_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    source = COALESCE(excluded.source, games.source),
                    blue_team = COALESCE(excluded.blue_team, games.blue_team),
                    red_team = COALESCE(excluded.red_team, games.red_team),
                    winner = COALESCE(excluded.winner, games.winner),
                    duration_seconds = COALESCE(excluded.duration_seconds, games.duration_seconds),
                    patch = COALESCE(excluded.patch, games.patch),
                    raw_json = COALESCE(excluded.raw_json, games.raw_json),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    game_id,
                    record.match_key,
                    record.source,
                    record.game_number,
                    record.blue_team,
                    record.red_team,
                    record.winner,
                    record.duration_seconds,
                    record.patch,
                    to_json(record.raw),
                ),
            )

    async def _upsert_game_placeholders(self, db: aiosqlite.Connection, batch: ParsedBatch) -> None:
        seen: set[tuple[str, int | None]] = set()
        related = [*batch.draft_picks, *batch.player_stats, *batch.timelines, *batch.objectives]
        for record in related:
            key = (record.match_key, record.game_number)
            if key in seen:
                continue
            seen.add(key)
            game_id = stable_key(record.match_key, record.game_number)
            await db.execute(
                """
                INSERT INTO games (id, match_id, game_number, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO NOTHING
                """,
                (game_id, record.match_key, record.game_number),
            )

    async def _upsert_drafts(self, db: aiosqlite.Connection, records: Iterable[DraftPickRecord]) -> None:
        seen: set[tuple[str, int | None]] = set()
        for record in records:
            key = (record.match_key, record.game_number)
            if key in seen:
                continue
            seen.add(key)
            game_id = stable_key(record.match_key, record.game_number)
            draft_id = stable_key(record.match_key, record.game_number, "draft")
            await db.execute(
                """
                INSERT INTO drafts (id, match_id, game_id, source, raw_json, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                """,
                (draft_id, record.match_key, game_id, "gol", None),
            )

    async def _upsert_draft_picks(self, db: aiosqlite.Connection, records: Iterable[DraftPickRecord]) -> None:
        for record in records:
            game_id = stable_key(record.match_key, record.game_number)
            draft_id = stable_key(record.match_key, record.game_number, "draft")
            row_id = stable_key(record.match_key, record.game_number, record.action, record.draft_order, record.champion)
            await db.execute(
                """
                INSERT INTO draft_picks (
                    id, match_id, game_id, draft_id, phase, action, draft_order, team, side,
                    champion, role, is_first_pick, is_counter_pick, champion_patch_win_rate,
                    champion_side_win_rate, champion_role_win_rate, raw_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    team = COALESCE(excluded.team, draft_picks.team),
                    side = COALESCE(excluded.side, draft_picks.side),
                    role = COALESCE(excluded.role, draft_picks.role),
                    champion_patch_win_rate = COALESCE(excluded.champion_patch_win_rate, draft_picks.champion_patch_win_rate),
                    champion_side_win_rate = COALESCE(excluded.champion_side_win_rate, draft_picks.champion_side_win_rate),
                    champion_role_win_rate = COALESCE(excluded.champion_role_win_rate, draft_picks.champion_role_win_rate),
                    raw_json = COALESCE(excluded.raw_json, draft_picks.raw_json),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    row_id,
                    record.match_key,
                    game_id,
                    draft_id,
                    record.phase,
                    record.action,
                    record.draft_order,
                    record.team,
                    record.side,
                    record.champion,
                    record.role,
                    int(record.is_first_pick) if record.is_first_pick is not None else None,
                    int(record.is_counter_pick) if record.is_counter_pick is not None else None,
                    record.champion_patch_win_rate,
                    record.champion_side_win_rate,
                    record.champion_role_win_rate,
                    to_json(record.raw),
                ),
            )

    async def _upsert_player_stats(self, db: aiosqlite.Connection, records: Iterable[PlayerGameStatRecord]) -> None:
        for record in records:
            game_id = stable_key(record.match_key, record.game_number)
            row_id = stable_key(record.match_key, record.game_number, record.team, record.player)
            await db.execute(
                """
                INSERT INTO player_game_stats (
                    id, match_id, game_id, game_number, team, player, champion, role, stats_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    team = COALESCE(excluded.team, player_game_stats.team),
                    champion = COALESCE(excluded.champion, player_game_stats.champion),
                    role = COALESCE(excluded.role, player_game_stats.role),
                    stats_json = COALESCE(excluded.stats_json, player_game_stats.stats_json),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    row_id,
                    record.match_key,
                    game_id,
                    record.game_number,
                    record.team,
                    record.player,
                    record.champion,
                    record.role,
                    to_json(record.stats),
                ),
            )

    async def _upsert_timelines(self, db: aiosqlite.Connection, records: Iterable[TimelineRecord]) -> None:
        for record in records:
            game_id = stable_key(record.match_key, record.game_number)
            await db.execute(
                """
                INSERT INTO game_timelines (id, match_id, game_id, game_number, metrics_json, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET metrics_json = excluded.metrics_json, updated_at = CURRENT_TIMESTAMP
                """,
                (stable_key(record.match_key, record.game_number, "timeline"), record.match_key, game_id, record.game_number, to_json(record.metrics)),
            )

    async def _upsert_objectives(self, db: aiosqlite.Connection, records: Iterable[ObjectiveRecord]) -> None:
        for record in records:
            game_id = stable_key(record.match_key, record.game_number)
            await db.execute(
                """
                INSERT INTO objectives (id, match_id, game_id, game_number, objective_type, team, player, minute, detail, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET team = COALESCE(excluded.team, objectives.team), updated_at = CURRENT_TIMESTAMP
                """,
                (
                    stable_key(record.match_key, record.game_number, record.objective_type, record.team, record.minute, record.detail),
                    record.match_key,
                    game_id,
                    record.game_number,
                    record.objective_type,
                    record.team,
                    record.player,
                    record.minute,
                    record.detail,
                ),
            )

    async def _upsert_teams(self, db: aiosqlite.Connection, records: Iterable[TeamRecord]) -> None:
        for record in records:
            await db.execute(
                """
                INSERT INTO teams (
                    id, name, region, current_record, points, ranking, recent_form_5,
                    recent_form_10, blue_side_win_rate, red_side_win_rate,
                    average_game_duration_seconds, raw_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET
                    region = COALESCE(excluded.region, teams.region),
                    current_record = COALESCE(excluded.current_record, teams.current_record),
                    points = COALESCE(excluded.points, teams.points),
                    ranking = COALESCE(excluded.ranking, teams.ranking),
                    recent_form_5 = COALESCE(excluded.recent_form_5, teams.recent_form_5),
                    recent_form_10 = COALESCE(excluded.recent_form_10, teams.recent_form_10),
                    blue_side_win_rate = COALESCE(excluded.blue_side_win_rate, teams.blue_side_win_rate),
                    red_side_win_rate = COALESCE(excluded.red_side_win_rate, teams.red_side_win_rate),
                    average_game_duration_seconds = COALESCE(excluded.average_game_duration_seconds, teams.average_game_duration_seconds),
                    raw_json = COALESCE(excluded.raw_json, teams.raw_json),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    stable_key(record.name),
                    record.name,
                    record.region,
                    record.current_record,
                    record.points,
                    record.ranking,
                    record.recent_form_5,
                    record.recent_form_10,
                    record.blue_side_win_rate,
                    record.red_side_win_rate,
                    record.average_game_duration_seconds,
                    to_json(record.raw),
                ),
            )

    async def _upsert_players(self, db: aiosqlite.Connection, records: Iterable[PlayerRecord]) -> None:
        for record in records:
            await db.execute(
                """
                INSERT INTO players (id, ign, real_name, role, nationality, raw_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(ign) DO UPDATE SET
                    real_name = COALESCE(excluded.real_name, players.real_name),
                    role = COALESCE(excluded.role, players.role),
                    nationality = COALESCE(excluded.nationality, players.nationality),
                    raw_json = COALESCE(excluded.raw_json, players.raw_json),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (stable_key(record.ign), record.ign, record.real_name, record.role, record.nationality, to_json(record.raw)),
            )

    async def _upsert_rosters(self, db: aiosqlite.Connection, records: Iterable[RosterRecord]) -> None:
        for record in records:
            await db.execute(
                """
                INSERT INTO rosters (id, team, player, role, status, nationality, join_date, real_name, raw_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    role = COALESCE(excluded.role, rosters.role),
                    status = COALESCE(excluded.status, rosters.status),
                    nationality = COALESCE(excluded.nationality, rosters.nationality),
                    join_date = COALESCE(excluded.join_date, rosters.join_date),
                    real_name = COALESCE(excluded.real_name, rosters.real_name),
                    raw_json = COALESCE(excluded.raw_json, rosters.raw_json),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    stable_key(record.team, record.player, record.status),
                    record.team,
                    record.player,
                    record.role,
                    record.status,
                    record.nationality,
                    record.join_date,
                    record.real_name,
                    to_json(record.raw),
                ),
            )

    async def _upsert_staff(self, db: aiosqlite.Connection, records: Iterable[StaffRecord]) -> None:
        for record in records:
            await db.execute(
                """
                INSERT INTO staff (id, team, name, title, nationality, raw_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    title = COALESCE(excluded.title, staff.title),
                    nationality = COALESCE(excluded.nationality, staff.nationality),
                    raw_json = COALESCE(excluded.raw_json, staff.raw_json),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (stable_key(record.team, record.name, record.title), record.team, record.name, record.title, record.nationality, to_json(record.raw)),
            )

    async def _upsert_tournaments(self, db: aiosqlite.Connection, records: Iterable[TournamentRecord]) -> None:
        for record in records:
            await db.execute(
                """
                INSERT INTO tournaments (
                    id, name, tier, region, prize_pool_total, stage_name, format,
                    qualification_paths_json, raw_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET
                    tier = COALESCE(excluded.tier, tournaments.tier),
                    region = COALESCE(excluded.region, tournaments.region),
                    prize_pool_total = COALESCE(excluded.prize_pool_total, tournaments.prize_pool_total),
                    stage_name = COALESCE(excluded.stage_name, tournaments.stage_name),
                    format = COALESCE(excluded.format, tournaments.format),
                    qualification_paths_json = COALESCE(excluded.qualification_paths_json, tournaments.qualification_paths_json),
                    raw_json = COALESCE(excluded.raw_json, tournaments.raw_json),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    stable_key(record.name),
                    record.name,
                    record.tier,
                    record.region,
                    record.prize_pool_total,
                    record.stage_name,
                    record.format,
                    to_json(record.qualification_paths),
                    to_json(record.raw),
                ),
            )

    async def _upsert_earnings(self, db: aiosqlite.Connection, records: Iterable[EarningRecord]) -> None:
        for record in records:
            await db.execute(
                """
                INSERT INTO earnings (id, entity_type, entity_name, tournament, team, amount, placement, raw_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    team = COALESCE(excluded.team, earnings.team),
                    amount = COALESCE(excluded.amount, earnings.amount),
                    placement = COALESCE(excluded.placement, earnings.placement),
                    raw_json = COALESCE(excluded.raw_json, earnings.raw_json),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    stable_key(record.entity_type, record.entity_name, record.tournament, record.team, record.placement),
                    record.entity_type,
                    record.entity_name,
                    record.tournament,
                    record.team,
                    record.amount,
                    record.placement,
                    to_json(record.raw),
                ),
            )
