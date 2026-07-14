# LoL Esports Scraper

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-beta-orange.svg)](CHANGELOG.md)

> Async multi-source pipeline for League of Legends esports -- gol.gg and loltv.gg via CloakBrowser (HTML + captured XHR JSON), Leaguepedia via httpx -- SQLite store, light multi-source reconcile, Parquet export, and fleet match snapshots.

**Fleet:** [vlr-scraper](https://github.com/ark-daemon/vlr-scraper) · [hltv-scraper](https://github.com/ark-daemon/hltv-scraper) · [dota2-scraper](https://github.com/ark-daemon/dota2-scraper) · [rocket-league-scraper](https://github.com/ark-daemon/rocket-league-scraper)

## Features

- **Three sources** -- gol.gg, loltv.gg (browser + XHR capture), Leaguepedia (httpx)
- **Pipeline stages** -- fetch workers -> parse workers -> store worker
- **JSON-preferring parsers** -- network payloads preferred over brittle HTML when present
- **Light reconcile** -- best-effort merge of overlapping multi-source records
- **Parquet table export** -- pandas + pyarrow
- **Fleet snapshot** -- match-grain `export/` (`data.json` + `csv` + `parquet` + `manifest.json`)
- **Optional R2 publish** -- overwrite-in-place upload with public manifest verification

Maturity: **beta (`0.1.0`)**, earliest of the five fleet tools in battle-testing. Prefer Leaguepedia for structure; treat gol/loltv as opportunistic deep stats. Not affiliated with Riot Games, gol.gg, loltv.gg, or Liquipedia.

## Getting started

```bash
git clone https://github.com/ark-daemon/lol-esports-scraper.git
cd lol-esports-scraper

python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env
# set LOL_USER_AGENT contact

lol-scraper --help
```

gol/loltv require CloakBrowser (Chromium on first render). If browser launch fails, install the stealth stack's browser deps (CloakBrowser/patchright), similar to other fleet repos.

## Usage

```bash
lol-scraper scrape leaguepedia     # safest first path (httpx only)
lol-scraper scrape gol
lol-scraper scrape loltv
lol-scraper scrape all             # gol + loltv + leaguepedia
lol-scraper status
lol-scraper export --out exports

# Fleet match snapshot (export/)
lol-scraper snapshot
lol-scraper snapshot --publish
lol-scraper publish
```

Full Typer-generated CLI docs: [COMMANDS.md](COMMANDS.md).

## Architecture

```
lol-scraper scrape {gol|loltv|leaguepedia|all}
        |
        v
 ScrapePipeline
   fetch workers --> parse workers --> store worker
        |                  |                |
        |                  |                v
        |                  |         Database.upsert_batch
        |                  |         (+ Reconciler on multi-source)
        |                  v
        |            parsers.py
        |            (JSON payloads preferred over HTML)
        v
  GOLFetcher / LOLTVFetcher          LeaguepediaFetcher
  CloakBrowserClient.render          httpx GET + User-Agent
  (captures xhr/fetch JSON)          region season page seeds
```

**Resilience:**

- **tenacity** retries on fetchers (exponential wait, 3 attempts)
- **`rate_limit_seconds`** sleep after successful browser/HTTP fetch
- **No circuit breaker** (vlr-scraper-only term in this fleet)
- CloakBrowser is the primary transport for gol.gg and loltv.gg

`scrape all` runs sources `gol`, `loltv`, `leaguepedia` in one pipeline invocation (shared visited-URL set).

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
| `LOL_USER_AGENT` | `LoLEsportsResearchBot/0.1 (+...; contact: ...)` | Research UA (not a Chrome spoof) |

Leaguepedia seeds expand per region into season portal paths (2020-2026 where coded in `leaguepedia_fetcher.py`).

**R2 publish** (optional):

| Variable | Role |
|----------|------|
| `R2_ACCOUNT_ID` | Cloudflare account id |
| `R2_ACCESS_KEY_ID` | R2 API token access key |
| `R2_SECRET_ACCESS_KEY` | R2 API token secret |
| `R2_BUCKET` | Bucket name |
| `R2_PUBLIC_BASE_URL` | Public base, no trailing slash |

Objects land at `{base}/lol/{data.json,data.csv,data.parquet,manifest.json}`.

## Data model

Tables (`storage.TABLES` / embedded `SCHEMA`):

`matches`, `games`, `drafts`, `draft_picks`, `player_game_stats`, `game_timelines`, `objectives`, `teams`, `players`, `rosters`, `staff`, `tournaments`, `earnings`.

IDs are **stable string keys** (`stable_key` / text PKs), not autoincrement integers like HLTV/VLR.

Schema-shaped sample (illustrative -- local DBs may be empty until a successful scrape):

```json
{"id": "...", "source": "loltv", "region": "LCK", "tournament": "LCK Spring",
 "team1": "T1", "team2": "GEN", "team1_score": 2, "team2_score": 1,
 "series_format": "Bo3", "date": "2026-01-01"}

{"match_id": "...", "game_number": 1, "blue_team": "T1", "red_team": "GEN",
 "winner": "T1", "patch": "16.1"}
```

CLI `export` writes Parquet via `exporter.export_parquet`.

### Fleet snapshot (`export/`)

Match/series grain, `schema_version` **1.0**:

`match_id`, `match_date`, `team_a`, `team_b`, `winner`, `source_url`, `status`, `score_a`, `score_b`, `event_name`, `format`, `raw_status`

> [!NOTE]
> Snapshot `export/` is separate from table Parquet dumps (`export` command / `LOL_EXPORT_DIR`).

## Limitations

> [!WARNING]
> Least production-hardened of the fleet; expect empty or partial tables on first runs. Legal/ToS for third-party sites is the operator's responsibility.

- gol.gg / loltv.gg require browser automation and may break on UI or anti-bot changes
- Leaguepedia HTML is season-template dependent; region seed list is incomplete for all circuits
- Reconcile is best-effort, not a full entity-resolution system
- No circuit breaker; only tenacity + fixed sleep
- `browser_concurrency` is configured but fetch concurrency is primarily `concurrency` on the shared queue
- Tests are unit/smoke level; no CI live scrape

## Tech stack

| Layer | Used |
|-------|------|
| Runtime | Python >=3.11, asyncio |
| CLI | typer + rich (`lol-scraper`) |
| Config | pydantic + pydantic-settings |
| HTTP | httpx (Leaguepedia) |
| Browser | cloakbrowser (`CloakBrowserClient`) for gol/loltv |
| HTML/JSON | beautifulsoup4 + selectolax; network JSON preferred in parsers |
| Retry | tenacity |
| Storage | aiosqlite |
| Export | pandas + pyarrow -> Parquet; snapshot also JSON/CSV |
| Logging | loguru; tqdm / rich CLI chrome |
| Publish | boto3 optional at runtime (`pip install boto3`) |
| Quality | pytest, pytest-asyncio (dev) |
