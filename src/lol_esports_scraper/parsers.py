from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from loguru import logger
from selectolax.parser import HTMLParser

from .models import (
    DraftPickRecord,
    EarningRecord,
    GameRecord,
    MatchRecord,
    ParsedBatch,
    PlayerGameStatRecord,
    PlayerRecord,
    RosterRecord,
    SourcePage,
    StaffRecord,
    TeamRecord,
    TimelineRecord,
    TournamentRecord,
    parse_date,
)


MATCH_FIELD_ALIASES = {
    "date": {"date", "time", "match date", "start time"},
    "tournament": {"tournament", "event", "league", "competition"},
    "team1": {"team", "team 1", "blue team", "home", "team a"},
    "team2": {"opponent", "team 2", "red team", "away", "team b"},
    "score": {"score", "result"},
    "patch": {"patch", "version"},
    "format": {"format", "series", "bo"},
}

PLAYER_STAT_KEYS = {
    "player",
    "champion",
    "role",
    "position",
    "kda",
    "kp",
    "cs",
    "cspm",
    "gold",
    "gpm",
    "dmg",
    "vision",
    "wards",
}


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text or None


def normalize_header(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"-?\d+", str(value).replace(",", ""))
    return int(match.group(0)) if match else None


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def split_score(value: str | None) -> tuple[int | None, int | None]:
    if not value:
        return None, None
    match = re.search(r"(\d+)\s*[-:]\s*(\d+)", value)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def iter_json_nodes(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from iter_json_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_json_nodes(child)


def table_dicts(html: str) -> list[dict[str, str | None]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str | None]] = []
    for table in soup.find_all("table"):
        headers = [normalize_header(cell.get_text(" ")) for cell in table.find_all("th")]
        if not headers:
            first_row = table.find("tr")
            if first_row:
                headers = [normalize_header(cell.get_text(" ")) for cell in first_row.find_all(["td", "th"])]
        if not headers:
            continue
        for tr in table.find_all("tr"):
            cells = [clean_text(cell.get_text(" ")) for cell in tr.find_all("td")]
            if not cells or len(cells) < 2:
                continue
            row = {headers[index] if index < len(headers) else f"col_{index}": value for index, value in enumerate(cells)}
            rows.append(row)
    return rows


def first_value(row: dict[str, Any], aliases: set[str]) -> Any:
    normalized = {normalize_header(key): value for key, value in row.items()}
    for key in aliases:
        if key in normalized and normalized[key] not in ("", None):
            return normalized[key]
    for key, value in normalized.items():
        if any(alias in key for alias in aliases) and value not in ("", None):
            return value
    return None


def parse_match_row(source: str, row: dict[str, Any], region: str | None = None) -> MatchRecord | None:
    team1 = first_value(row, MATCH_FIELD_ALIASES["team1"])
    team2 = first_value(row, MATCH_FIELD_ALIASES["team2"])
    score = first_value(row, MATCH_FIELD_ALIASES["score"])
    score1, score2 = split_score(str(score) if score else None)
    if not team1 or not team2:
        teams = [
            value
            for key, value in row.items()
            if "team" in normalize_header(key) and clean_text(str(value))
        ]
        if len(teams) >= 2:
            team1, team2 = teams[0], teams[1]
    if not team1 or not team2:
        return None
    return MatchRecord(
        source=source,
        tournament=clean_text(str(first_value(row, MATCH_FIELD_ALIASES["tournament"]) or "")),
        region=region,
        match_date=parse_date(str(first_value(row, MATCH_FIELD_ALIASES["date"]) or "")),
        team1=clean_text(str(team1)),
        team2=clean_text(str(team2)),
        team1_score=score1,
        team2_score=score2,
        series_format=clean_text(str(first_value(row, MATCH_FIELD_ALIASES["format"]) or "")),
        patch=clean_text(str(first_value(row, MATCH_FIELD_ALIASES["patch"]) or "")),
        raw=row,
    )


def parse_json_matches(source: str, payloads: list[dict[str, Any]], region: str | None) -> list[MatchRecord]:
    records: list[MatchRecord] = []
    for payload in payloads:
        for node in iter_json_nodes(payload.get("payload", payload)):
            if not isinstance(node, dict):
                continue
            normalized_keys = {normalize_header(key) for key in node}
            has_team_signal = any("team" in key for key in normalized_keys)
            has_match_signal = bool({"match", "game", "series", "date", "result"} & normalized_keys)
            if not has_team_signal or not has_match_signal:
                continue
            record = parse_match_row(source, node, region)
            if record:
                records.append(record)
    return records


def parse_html_matches(source: str, html: str, region: str | None) -> list[MatchRecord]:
    records: list[MatchRecord] = []
    for row in table_dicts(html):
        record = parse_match_row(source, row, region)
        if record:
            records.append(record)
    return records


def parse_gol(page: SourcePage) -> ParsedBatch:
    batch = ParsedBatch()
    batch.matches.extend(parse_json_matches("gol", page.json_payloads, page.region))
    if not batch.matches:
        batch.matches.extend(parse_html_matches("gol", page.html, page.region))
    for match in batch.matches:
        match_key = match.reconciliation_key
        batch.games.append(
            GameRecord(
                source="gol",
                match_key=match_key,
                game_number=1,
                blue_team=match.team1,
                red_team=match.team2,
                patch=match.patch,
                raw=match.raw,
            )
        )
    batch.draft_picks.extend(parse_draft_tables(page.html, batch.matches))
    batch.player_stats.extend(parse_player_stat_tables(page.html, batch.matches))
    batch.timelines.extend(parse_timeline_json(page.json_payloads, batch.matches))
    
    discovered_tournaments = discover_tournament_links(page.html, page.url, page.region)
    batch.tournaments.extend(discovered_tournaments)
    for t in discovered_tournaments:
        if t.raw and t.raw.get("url"):
            batch.discovered_urls.append(t.raw["url"])
            
    batch.discovered_urls.extend(discover_match_links(page.html, page.url))
    return batch


def parse_loltv(page: SourcePage) -> ParsedBatch:
    batch = ParsedBatch()
    batch.matches.extend(parse_json_matches("loltv", page.json_payloads, page.region))
    if not batch.matches:
        batch.matches.extend(parse_html_matches("loltv", page.html, page.region))
    for match in batch.matches:
        batch.teams.append(TeamRecord(name=match.team1 or "", region=match.region, raw=match.raw)) if match.team1 else None
        batch.teams.append(TeamRecord(name=match.team2 or "", region=match.region, raw=match.raw)) if match.team2 else None
        
    discovered_tournaments = discover_tournament_links(page.html, page.url, page.region)
    batch.tournaments.extend(discovered_tournaments)
    for t in discovered_tournaments:
        if t.raw and t.raw.get("url"):
            batch.discovered_urls.append(t.raw["url"])
            
    batch.discovered_urls.extend(discover_match_links(page.html, page.url))
    return batch


def parse_leaguepedia(page: SourcePage, base_url: str) -> ParsedBatch:
    batch = ParsedBatch()
    soup = BeautifulSoup(page.html, "html.parser")
    title = clean_text(soup.find("h1").get_text(" ") if soup.find("h1") else None)
    infobox = extract_infobox(soup)
    if title:
        batch.tournaments.append(
            TournamentRecord(
                name=title,
                tier=first_infobox(infobox, "tier"),
                region=first_infobox(infobox, "region", "location"),
                prize_pool_total=first_infobox(infobox, "prize pool", "prizepool"),
                format=first_infobox(infobox, "format"),
                qualification_paths={"source_url": page.url} if "qualif" in page.html.lower() else None,
                raw=infobox,
            )
        )
    for row in table_dicts(page.html):
        row_keys = set(row)
        if {"id", "name"} & row_keys or "player" in row_keys:
            roster = roster_from_row(row, title)
            if roster:
                batch.rosters.append(roster)
                batch.players.append(
                    PlayerRecord(
                        ign=roster.player,
                        real_name=roster.real_name,
                        role=roster.role,
                        nationality=roster.nationality,
                        raw=roster.raw,
                    )
                )
        if any("coach" in key or "staff" in key or "role" == key for key in row_keys):
            staff = staff_from_row(row, title)
            if staff:
                batch.staff.append(staff)
        if any("prize" in key or "earnings" in key for key in row_keys):
            earning = earning_from_row(row, title)
            if earning:
                batch.earnings.append(earning)
        match = parse_match_row("leaguepedia", row, page.region)
        if match:
            match.tournament = match.tournament or title
            batch.matches.append(match)
    
    discovered_tournaments = discover_tournament_links(page.html, base_url, page.region)
    batch.tournaments.extend(discovered_tournaments)
    for t in discovered_tournaments:
        if t.raw and t.raw.get("url"):
            batch.discovered_urls.append(t.raw["url"])
            
    batch.discovered_urls.extend(discover_match_links(page.html, base_url))
    return batch


def extract_infobox(soup: BeautifulSoup) -> dict[str, str | None]:
    data: dict[str, str | None] = {}
    for table in soup.select(".infobox, .fo-nttax-infobox, table.wikitable"):
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) >= 2:
                key = normalize_header(cells[0].get_text(" "))
                value = clean_text(cells[1].get_text(" "))
                if key and value:
                    data[key] = value
    return data


def first_infobox(data: dict[str, str | None], *keys: str) -> str | None:
    for wanted in keys:
        wanted_norm = normalize_header(wanted)
        for key, value in data.items():
            if wanted_norm == key or wanted_norm in key:
                return value
    return None


def roster_from_row(row: dict[str, str | None], team: str | None) -> RosterRecord | None:
    player = row.get("id") or row.get("player") or row.get("ign") or row.get("name")
    if not team or not player:
        return None
    return RosterRecord(
        team=team,
        player=player,
        role=row.get("role") or row.get("position"),
        status=row.get("status") or "active",
        nationality=row.get("nationality") or row.get("country"),
        join_date=parse_date(row.get("join date") or row.get("joined")),
        real_name=row.get("real name") or row.get("name"),
        raw=row,
    )


def staff_from_row(row: dict[str, str | None], team: str | None) -> StaffRecord | None:
    name = row.get("name") or row.get("staff") or row.get("coach")
    title = row.get("title") or row.get("role") or row.get("position")
    if not team or not name or not title:
        return None
    if not any(word in title.lower() for word in ("coach", "analyst", "manager", "staff")):
        return None
    return StaffRecord(team=team, name=name, title=title, nationality=row.get("nationality"), raw=row)


def earning_from_row(row: dict[str, str | None], tournament: str | None) -> EarningRecord | None:
    entity = row.get("player") or row.get("team") or row.get("name")
    amount = row.get("prize") or row.get("earnings") or row.get("prize money")
    if not entity or not amount:
        return None
    return EarningRecord(
        entity_type="team" if row.get("team") else "player",
        entity_name=entity,
        tournament=tournament,
        team=row.get("team"),
        amount=amount,
        placement=row.get("place") or row.get("placement"),
        raw=row,
    )


def discover_tournament_links(html: str, base_url: str, region: str | None) -> list[TournamentRecord]:
    parser = HTMLParser(html)
    records: list[TournamentRecord] = []
    for anchor in parser.css("a"):
        text = clean_text(anchor.text())
        href = anchor.attributes.get("href")
        if not text or not href:
            continue
        if any(term in text.lower() for term in ("spring", "summer", "winter", "split", "playoffs", "season")):
            records.append(TournamentRecord(name=text, region=region, raw={"url": urljoin(base_url, href)}))
    return records[:50]


def discover_match_links(html: str, base_url: str) -> list[str]:
    parser = HTMLParser(html)
    records: list[str] = []
    for anchor in parser.css("a"):
        href = anchor.attributes.get("href")
        if not href:
            continue
        href_lower = href.lower()
        if "game/stats" in href_lower or "match_history" in href_lower or "scoreboards" in href_lower or "match" in href_lower:
            records.append(urljoin(base_url, href))
    return list(set(records))


def parse_draft_tables(html: str, matches: list[MatchRecord]) -> list[DraftPickRecord]:
    if not matches:
        return []
    records: list[DraftPickRecord] = []
    match_key = matches[0].reconciliation_key
    order = 1
    for row in table_dicts(html):
        keys = {normalize_header(key) for key in row}
        if not any("champion" in key for key in keys):
            continue
        action = "ban" if any("ban" in key for key in keys) else "pick"
        champion = first_value(row, {"champion", "pick", "ban"})
        if not champion:
            continue
        records.append(
            DraftPickRecord(
                match_key=match_key,
                game_number=safe_int(first_value(row, {"game", "map"})) or 1,
                phase=clean_text(str(first_value(row, {"phase"}) or "")),
                action=action,
                draft_order=safe_int(first_value(row, {"order", "#"})) or order,
                team=clean_text(str(first_value(row, {"team"}) or "")),
                side=clean_text(str(first_value(row, {"side"}) or "")),
                champion=clean_text(str(champion)),
                role=clean_text(str(first_value(row, {"role", "position"}) or "")),
                is_first_pick=order == 1 and action == "pick",
                is_counter_pick=order > 1 and action == "pick",
                champion_patch_win_rate=safe_float(first_value(row, {"patch win rate", "overall win rate"})),
                champion_side_win_rate=safe_float(first_value(row, {"side win rate"})),
                champion_role_win_rate=safe_float(first_value(row, {"role win rate", "position win rate"})),
                raw=row,
            )
        )
        order += 1
    return records


def parse_player_stat_tables(html: str, matches: list[MatchRecord]) -> list[PlayerGameStatRecord]:
    if not matches:
        return []
    records: list[PlayerGameStatRecord] = []
    match_key = matches[0].reconciliation_key
    for row in table_dicts(html):
        keys = set(row)
        if not PLAYER_STAT_KEYS & keys:
            continue
        player = row.get("player") or row.get("name")
        if not player:
            continue
        records.append(
            PlayerGameStatRecord(
                match_key=match_key,
                game_number=safe_int(row.get("game")) or 1,
                team=row.get("team"),
                player=player,
                champion=row.get("champion"),
                role=row.get("role") or row.get("position"),
                stats=row,
            )
        )
    return records


def parse_timeline_json(payloads: list[dict[str, Any]], matches: list[MatchRecord]) -> list[TimelineRecord]:
    if not matches:
        return []
    records: list[TimelineRecord] = []
    match_key = matches[0].reconciliation_key
    for payload in payloads:
        for node in iter_json_nodes(payload.get("payload", payload)):
            if not isinstance(node, dict):
                continue
            keys = {normalize_header(key) for key in node}
            if any("gold" in key or "dragon" in key or "baron" in key or "timeline" in key for key in keys):
                records.append(TimelineRecord(match_key=match_key, game_number=safe_int(node.get("game")) or 1, metrics=node))
    if len(records) > 20:
        logger.debug("Trimming noisy timeline candidates from {} to 20", len(records))
        return records[:20]
    return records
