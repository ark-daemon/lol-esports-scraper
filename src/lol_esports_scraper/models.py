from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


JsonDict = dict[str, Any]


def stable_key(*parts: object) -> str:
    normalized = "|".join("" if part is None else str(part).strip().lower() for part in parts)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def to_json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def parse_date(value: str | date | datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = value.strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


@dataclass(slots=True)
class SourcePage:
    source: str
    url: str
    html: str
    region: str | None = None
    json_payloads: list[JsonDict] = field(default_factory=list)


@dataclass(slots=True)
class MatchRecord:
    source: str
    tournament: str | None = None
    region: str | None = None
    split: str | None = None
    match_date: str | None = None
    team1: str | None = None
    team2: str | None = None
    team1_score: int | None = None
    team2_score: int | None = None
    series_format: str | None = None
    patch: str | None = None
    h2h_all_time: str | None = None
    h2h_current_split: str | None = None
    raw: JsonDict | None = None

    @property
    def reconciliation_key(self) -> str:
        teams = sorted([self.team1 or "", self.team2 or ""])
        return stable_key(self.tournament, teams[0], teams[1], self.match_date)


@dataclass(slots=True)
class GameRecord:
    source: str
    match_key: str
    game_number: int | None = None
    blue_team: str | None = None
    red_team: str | None = None
    winner: str | None = None
    duration_seconds: int | None = None
    patch: str | None = None
    raw: JsonDict | None = None


@dataclass(slots=True)
class DraftPickRecord:
    match_key: str
    game_number: int | None
    phase: str | None
    action: str | None
    draft_order: int | None
    team: str | None
    side: str | None
    champion: str | None
    role: str | None = None
    is_first_pick: bool | None = None
    is_counter_pick: bool | None = None
    champion_patch_win_rate: float | None = None
    champion_side_win_rate: float | None = None
    champion_role_win_rate: float | None = None
    raw: JsonDict | None = None


@dataclass(slots=True)
class PlayerGameStatRecord:
    match_key: str
    game_number: int | None
    team: str | None = None
    player: str | None = None
    champion: str | None = None
    role: str | None = None
    stats: JsonDict = field(default_factory=dict)


@dataclass(slots=True)
class TimelineRecord:
    match_key: str
    game_number: int | None
    metrics: JsonDict = field(default_factory=dict)


@dataclass(slots=True)
class ObjectiveRecord:
    match_key: str
    game_number: int | None
    objective_type: str | None
    team: str | None = None
    player: str | None = None
    minute: float | None = None
    detail: str | None = None


@dataclass(slots=True)
class TeamRecord:
    name: str
    region: str | None = None
    current_record: str | None = None
    points: str | None = None
    ranking: str | None = None
    recent_form_5: str | None = None
    recent_form_10: str | None = None
    blue_side_win_rate: float | None = None
    red_side_win_rate: float | None = None
    average_game_duration_seconds: int | None = None
    raw: JsonDict | None = None


@dataclass(slots=True)
class PlayerRecord:
    ign: str
    real_name: str | None = None
    role: str | None = None
    nationality: str | None = None
    raw: JsonDict | None = None


@dataclass(slots=True)
class RosterRecord:
    team: str
    player: str
    role: str | None = None
    status: str | None = None
    nationality: str | None = None
    join_date: str | None = None
    real_name: str | None = None
    raw: JsonDict | None = None


@dataclass(slots=True)
class StaffRecord:
    team: str
    name: str
    title: str | None = None
    nationality: str | None = None
    raw: JsonDict | None = None


@dataclass(slots=True)
class TournamentRecord:
    name: str
    tier: str | None = None
    region: str | None = None
    prize_pool_total: str | None = None
    stage_name: str | None = None
    format: str | None = None
    qualification_paths: JsonDict | None = None
    raw: JsonDict | None = None


@dataclass(slots=True)
class EarningRecord:
    entity_type: str
    entity_name: str
    tournament: str | None = None
    team: str | None = None
    amount: str | None = None
    placement: str | None = None
    raw: JsonDict | None = None


@dataclass(slots=True)
class ParsedBatch:
    matches: list[MatchRecord] = field(default_factory=list)
    games: list[GameRecord] = field(default_factory=list)
    draft_picks: list[DraftPickRecord] = field(default_factory=list)
    player_stats: list[PlayerGameStatRecord] = field(default_factory=list)
    timelines: list[TimelineRecord] = field(default_factory=list)
    objectives: list[ObjectiveRecord] = field(default_factory=list)
    teams: list[TeamRecord] = field(default_factory=list)
    players: list[PlayerRecord] = field(default_factory=list)
    rosters: list[RosterRecord] = field(default_factory=list)
    staff: list[StaffRecord] = field(default_factory=list)
    tournaments: list[TournamentRecord] = field(default_factory=list)
    earnings: list[EarningRecord] = field(default_factory=list)
    discovered_urls: list[str] = field(default_factory=list)

    def extend(self, other: "ParsedBatch") -> None:
        for name in self.__dataclass_fields__:
            getattr(self, name).extend(getattr(other, name))
