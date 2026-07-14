from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from .cli_ui import (
    configure_rich_logging,
    end_summary_table,
    scrape_progress,
    startup_panel,
    status_table,
    timed_run,
)
from .config import Settings, get_settings
from .exporter import export_parquet
from .pipeline import ScrapePipeline
from .storage import TABLES, Database

app = typer.Typer(
    name="lol-scraper",
    help="League of Legends esports scraper ([bold]gol.gg[/], [bold]loltv.gg[/], [bold]Leaguepedia[/]).",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
)
scrape_app = typer.Typer(
    help="Scrape one or more sources.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
app.add_typer(scrape_app, name="scrape")


def load_runtime() -> tuple[Settings, Database]:
    settings = get_settings()
    configure_rich_logging("INFO", settings.logs_dir / "scraper.log")
    return settings, Database(settings.db_path)


def _boot(settings: Settings, sources: list[str]) -> None:
    startup_panel(
        title="lol-scraper · run config",
        rows={
            "Target": ", ".join(sources),
            "DB path": settings.db_path,
            "Export dir": settings.export_dir,
            "Regions": ", ".join(settings.target_regions),
            "Concurrency": settings.concurrency,
            "Rate limit (s)": settings.rate_limit_seconds,
            "Output format": "parquet (on export)",
            "User-Agent": settings.user_agent[:56] + ("…" if len(settings.user_agent) > 56 else ""),
        },
    )


async def run_scrape(sources: list[str]) -> dict[str, int]:
    settings, db = load_runtime()
    pipeline = ScrapePipeline(settings, db)
    batch = await pipeline.scrape(sources)
    return {
        "matches": len(batch.matches),
        "games": len(batch.games),
        "draft picks": len(batch.draft_picks),
        "player stats": len(batch.player_stats),
        "tournaments": len(batch.tournaments),
    }


def _scrape(sources: list[str]) -> None:
    settings = get_settings()
    _boot(settings, sources)
    label = "+".join(sources)
    with timed_run() as elapsed, scrape_progress() as progress:
        task = progress.add_task(f"scrape {label}", total=None)
        totals = asyncio.run(run_scrape(sources))
        progress.update(task, description=f"scrape {label} · done")
    end_summary_table(
        title="Scrape summary",
        rows=[(k, f"{v:,}") for k, v in totals.items()],
        duration_s=elapsed[0],
    )


@scrape_app.command("gol")
def scrape_gol() -> None:
    """Scrape gol.gg (CloakBrowser + network JSON capture)."""
    _scrape(["gol"])


@scrape_app.command("loltv")
def scrape_loltv() -> None:
    """Scrape loltv.gg (CloakBrowser + network JSON capture)."""
    _scrape(["loltv"])


@scrape_app.command("leaguepedia")
def scrape_leaguepedia() -> None:
    """Scrape Leaguepedia / Liquipedia LoL via httpx."""
    _scrape(["leaguepedia"])


@scrape_app.command("all")
def scrape_all() -> None:
    """Scrape gol.gg, loltv.gg, and Leaguepedia in one pipeline run."""
    _scrape(["gol", "loltv", "leaguepedia"])


@app.command("export")
def export(
    out: Annotated[Path | None, typer.Option(help="Output directory for Parquet files.")] = None,
    table: Annotated[list[str] | None, typer.Option(help="Specific table(s) to export.")] = None,
) -> None:
    """Export SQLite tables to Parquet."""
    settings, db = load_runtime()
    asyncio.run(db.initialize())
    selected = table or TABLES
    target = out or settings.export_dir
    startup_panel(
        title="lol-scraper · export",
        rows={
            "DB path": settings.db_path,
            "Output format": "parquet",
            "Export dir": target,
            "Tables": ", ".join(selected),
        },
    )
    with timed_run() as elapsed:
        written = asyncio.run(export_parquet(settings.db_path, target, selected))
    end_summary_table(
        title="Export summary",
        rows=[("Tables", len(written))],
        outputs=written,
        duration_s=elapsed[0],
    )


@app.command("status")
def status() -> None:
    """Show database row counts."""
    settings, db = load_runtime()
    counts = asyncio.run(db.status_counts())
    status_table(f"SQLite · {settings.db_path}", {name: counts[name] for name in TABLES})


@app.command("snapshot")
def snapshot(
    out: Annotated[
        Path,
        typer.Option("--out", "-o", help="Directory for data.json/csv/parquet + manifest.json."),
    ] = Path("export"),
) -> None:
    """Write fleet match-level snapshot for dashboard / R2 publish."""
    from .snapshot import write_snapshot

    settings, _db = load_runtime()
    startup_panel(
        title="lol-scraper · snapshot",
        rows={
            "DB path": settings.db_path,
            "Output dir": out,
            "Grain": "match/series",
            "ID strategy": "lol:{id} (stable_key text PK)",
        },
    )
    with timed_run() as elapsed:
        manifest = write_snapshot(settings.db_path, out)
    end_summary_table(
        title="Snapshot summary",
        rows=[
            ("Records", manifest.get("record_count")),
            ("Status mapped", manifest.get("stats", {}).get("status_mapped")),
            ("Status heuristic", manifest.get("stats", {}).get("status_heuristic")),
            ("Dropped (no teams)", manifest.get("stats", {}).get("dropped_no_teams")),
        ],
        outputs=[out / "manifest.json", out / "data.json", out / "data.csv", out / "data.parquet"],
        duration_s=elapsed[0],
    )


if __name__ == "__main__":
    app()
