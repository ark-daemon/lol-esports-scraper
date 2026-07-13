# lol-esports-scraper

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-beta-orange.svg)](CHANGELOG.md)

Async multi-source pipeline for **League of Legends esports** — gol.gg and loltv.gg via CloakBrowser (HTML + captured XHR JSON), Leaguepedia via httpx — SQLite store with light multi-source reconcile and Parquet export.

**Fleet:** [vlr-scraper](https://github.com/ark-daemon/vlr-scraper) · [hltv-scraper](https://github.com/ark-daemon/hltv-scraper) · [dota2-scraper](https://github.com/ark-daemon/dota2-scraper) · [rocket-league-scraper](https://github.com/ark-daemon/rocket-league-scraper)

---

## What it does

Collects match/series rows, games, draft picks, player game stats, timelines/objectives (when present in payloads), teams, players, rosters, staff, tournaments, and earnings into one SQLite schema. A `Reconciler` merges overlapping records from different sources where keys align; incomplete pages become NULL fields rather than hard failures.

Maturity: **beta (`0.1.0`)**, earliest of the five fleet tools in terms of battle-testing. Prefer Leaguepedia for structure; treat gol/loltv as opportunistic deep stats. Not affiliated with Riot Games, gol.gg, loltv.gg, or Liquipedia.

---

## Architecture

```
lol-scraper scrape {gol|loltv|leaguepedia|all}
        │
        ▼
 ScrapePipeline
   fetch workers ──► parse workers ──► store worker
        │                  │                │
        │                  │                ▼
        │                  │         Database.upsert_batch
        │                  │         (+ Reconciler on multi-source)
        │                  ▼
        │            parsers.py
        │            (JSON payloads preferred over HTML when present)
        ▼
  GOLFetcher / LOLTVFetcher          LeaguepediaFetcher
  CloakBrowserClient.render          httpx GET + User-Agent
  (captures xhr/fetch JSON)          region season page seeds
```

**Resilience vocabulary:**

- **tenacity** retries on fetchers (exponential wait, 3 attempts).
- **`rate_limit_seconds`** sleep after successful browser/HTTP fetch in the pipeline.
- **No circuit breaker** (vlr-scraper-only term in this fleet).
- **CloakBrowser** is the primary transport for gol.gg and loltv.gg, not Playwright alone — though CloakBrowser sits on a Chromium automation stack.

`scrape all` runs sources `gol`, `loltv`, `leaguepedia` in one pipeline invocation (shared visited-URL set).

---

## Quickstart

```bash
git clone https://github.com/ark-daemon/lol-esports-scraper.git
cd lol-esports-scraper

python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -e ".[dev]"
# gol/loltv require CloakBrowser; first render downloads Chromium.
# If browser launch fails, install the stealth stack’s browser deps
# (CloakBrowser/patchright), similar to other fleet repos.

cp .env.example .env
# set LOL_USER_AGENT contact

lol-scraper --help
lol-scraper scrape leaguepedia     # safest first path (httpx only)
lol-scraper scrape gol
lol-scraper scrape loltv
lol-scraper scrape all
lol-scraper status
lol-scraper export --out exports
```

---

## Configuration

`pydantic-settings` with prefix **`LOL_`** (`src/lol_esports_scraper/config.py`).

| Variable | Default | Role |
|----------|---------|------|
| `LOL_GOL_BASE_URL` | `https://gol.gg` | gol origin |
| `LOL_LOLTV_BASE_URL` | `https://www.loltv.gg` | loltv origin |
| `LOL_LEAGUEPEDIA_BASE_URL` | `https://liquipedia.net/leagueoflegends` | wiki origin |
| `LOL_TARGET_REGIONS` | `LCK,LPL,LEC,LCP,LCS` | Region list (comma-separated env OK) |
| `LOL_DB_PATH` | `lol.db` | SQLite |
| `LOL_LOGS_DIR` | `logs` | Logs |
| `LOL_EXPORT_DIR` | `exports` | Parquet dir |
| `LOL_CONCURRENCY` | `2` | Fetch worker count (capped in pipeline) |
| `LOL_BROWSER_CONCURRENCY` | `1` | Reserved browser concurrency setting |
| `LOL_RATE_LIMIT_SECONDS` | `1.5` | Sleep after each fetch |
| `LOL_REQUEST_TIMEOUT_SECONDS` | `30` | httpx timeout (Leaguepedia) |
| `LOL_FINGERPRINT_SEED` | `42069` | CloakBrowser `--fingerprint=` |
| `LOL_USER_AGENT` | `LoLEsportsResearchBot/0.1 (+…; contact: …)` | Research UA (not a Chrome spoof) |

Leaguepedia seeds expand per region into season portal paths (2020–2026 where coded in `leaguepedia_fetcher.py`).

---

## Data model + sample output

Tables (`storage.TABLES` / embedded `SCHEMA`):

`matches`, `games`, `drafts`, `draft_picks`, `player_game_stats`, `game_timelines`, `objectives`, `teams`, `players`, `rosters`, `staff`, `tournaments`, `earnings`.

IDs are **stable string keys** (`stable_key` / text PKs), not autoincrement integers like HLTV/VLR.

**Schema-shaped sample** (illustrative — local DBs may be empty until a successful scrape):

```json
// matches
{"id": "…", "source": "loltv", "region": "LCK", "tournament": "LCK Spring",
 "team1": "T1", "team2": "GEN", "team1_score": 2, "team2_score": 1,
 "series_format": "Bo3", "date": "2026-01-01"}

// games
{"match_id": "…", "game_number": 1, "blue_team": "T1", "red_team": "GEN",
 "winner": "T1", "patch": "16.1"}
```

Export: Parquet via `lol-scraper export` (`exporter.export_parquet`).

Unit tests assert defensive parsing on synthetic HTML/JSON (`tests/test_parsers.py`).

---

## Current limitations

- **Least production-hardened** of the fleet; expect empty or partial tables on first runs.
- **gol.gg / loltv.gg require browser automation** and may break on UI or anti-bot changes.
- **Leaguepedia HTML is season-template dependent**; region seed list is incomplete for all circuits.
- **Reconcile is best-effort**, not a full entity-resolution system.
- **No circuit breaker**; only tenacity + fixed sleep.
- **`browser_concurrency` is configured** but fetch concurrency is primarily `concurrency` on the shared queue.
- **Legal/ToS** for third-party sites is the operator’s problem.
- **Tests** are unit/smoke level; no CI live scrape.

---

## Tech stack

| Layer | Actually used |
|-------|----------------|
| Runtime | Python ≥3.11, asyncio |
| CLI | typer, rich (`lol-scraper`) |
| Config | pydantic + pydantic-settings |
| HTTP | httpx (Leaguepedia) |
| Browser | cloakbrowser (`CloakBrowserClient`) for gol/loltv |
| HTML/JSON | beautifulsoup4 + selectolax; network JSON preferred in parsers |
| Retry | tenacity |
| Storage | aiosqlite |
| Export | pandas + pyarrow → Parquet |
| Logging | loguru; tqdm progress in pipeline |
| Quality | pytest, pytest-asyncio (dev) |

---

## License

MIT © ark-daemon — see [LICENSE](LICENSE).

See also [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), [CHANGELOG.md](CHANGELOG.md).
