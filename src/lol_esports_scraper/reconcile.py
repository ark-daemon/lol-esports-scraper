from __future__ import annotations

from dataclasses import replace
from typing import TypeVar

from .models import MatchRecord, ParsedBatch


T = TypeVar("T")


def prefer(left: T | None, right: T | None) -> T | None:
    return left if left not in (None, "") else right


class Reconciler:
    """Deduplicate series across sources using tournament + teams + date."""

    def reconcile_batch(self, batch: ParsedBatch) -> ParsedBatch:
        merged = ParsedBatch()
        matches_by_key: dict[str, MatchRecord] = {}
        for match in batch.matches:
            key = match.reconciliation_key
            current = matches_by_key.get(key)
            matches_by_key[key] = match if current is None else self._merge_match(current, match)
        merged.matches = list(matches_by_key.values())
        merged.games = batch.games
        merged.draft_picks = batch.draft_picks
        merged.player_stats = batch.player_stats
        merged.timelines = batch.timelines
        merged.objectives = batch.objectives
        merged.teams = self._dedupe_by(batch.teams, lambda item: item.name.lower())
        merged.players = self._dedupe_by(batch.players, lambda item: item.ign.lower())
        merged.rosters = self._dedupe_by(batch.rosters, lambda item: f"{item.team}|{item.player}|{item.status}".lower())
        merged.staff = self._dedupe_by(batch.staff, lambda item: f"{item.team}|{item.name}|{item.title}".lower())
        merged.tournaments = self._dedupe_by(batch.tournaments, lambda item: item.name.lower())
        merged.earnings = self._dedupe_by(
            batch.earnings,
            lambda item: f"{item.entity_type}|{item.entity_name}|{item.tournament}|{item.team}|{item.placement}".lower(),
        )
        return merged

    def _merge_match(self, left: MatchRecord, right: MatchRecord) -> MatchRecord:
        raw = {"sources": [left.raw, right.raw]}
        return replace(
            left,
            source=",".join(sorted(set(left.source.split(",") + right.source.split(",")))),
            tournament=prefer(left.tournament, right.tournament),
            region=prefer(left.region, right.region),
            split=prefer(left.split, right.split),
            match_date=prefer(left.match_date, right.match_date),
            team1=prefer(left.team1, right.team1),
            team2=prefer(left.team2, right.team2),
            team1_score=prefer(left.team1_score, right.team1_score),
            team2_score=prefer(left.team2_score, right.team2_score),
            series_format=prefer(left.series_format, right.series_format),
            patch=prefer(left.patch, right.patch),
            h2h_all_time=prefer(left.h2h_all_time, right.h2h_all_time),
            h2h_current_split=prefer(left.h2h_current_split, right.h2h_current_split),
            raw=raw,
        )

    def _dedupe_by(self, records: list[T], key_fn: object) -> list[T]:
        seen: dict[str, T] = {}
        for record in records:
            key = key_fn(record)  # type: ignore[misc]
            if key and key not in seen:
                seen[key] = record
        return list(seen.values())
