# LoL Esports Scraper

Async Python 3.11+ scraper for **League of Legends esports data** from:

- [gol.gg](https://gol.gg) â€” per-game stats, drafts, timelines
- [loltv.gg](https://www.loltv.gg) â€” match results and form
- [Leaguepedia / Liquipedia LoL](https://liquipedia.net/leagueoflegends) â€” tournaments, rosters, transfers, earnings

Data is stored in local SQLite and exportable to Parquet.

---

## Install

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -e ".[dev]"
```

CloakBrowser downloads its Chromium binary on first use for JS-heavy sources (gol.gg / loltv.gg).

```bash
cp .env.example .env
# Set LOL_USER_AGENT to a real contact email before heavy runs.
```

## Usage

```bash
lol-scraper scrape all
lol-scraper scrape gol
lol-scraper scrape loltv
lol-scraper scrape leaguepedia
lol-scraper export --out exports
lol-scraper status
```

## Configuration

Settings use the `LOL_` prefix (see `.env.example`).

| Variable | Default | Purpose |
|----------|---------|---------|
| `LOL_DB_PATH` | `lol.db` | SQLite path |
| `LOL_TARGET_REGIONS` | `LCK,LPL,LEC,LCP,LCS` | Focus regions |
| `LOL_RATE_LIMIT_SECONDS` | `1.5` | Delay between requests |
| `LOL_USER_AGENT` | research bot string | Identify yourself |

## Testing

```bash
pytest -q
```

## Responsible use

- Keep concurrency low; prefer Leaguepedia HTTP over browser sources when possible.
- Users must comply with each source's Terms of Service.
- Not affiliated with Riot Games, gol.gg, loltv.gg, or Liquipedia.

## License

MIT Â© 2026 ark-daemon â€” see [LICENSE](LICENSE).
## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security reports: [SECURITY.md](SECURITY.md). Changes: [CHANGELOG.md](CHANGELOG.md).
