from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .config import Settings, get_settings
from .exporter import export_parquet
from .logging import configure_logging
from .pipeline import ScrapePipeline
from .storage import Database, TABLES


app = typer.Typer(help="League of Legends esports data scraper.")
scrape_app = typer.Typer(help="Scrape one or more sources.")
app.add_typer(scrape_app, name="scrape")
console = Console()


def load_runtime() -> tuple[Settings, Database]:
    settings = get_settings()
    configure_logging(settings.logs_dir)
    return settings, Database(settings.db_path)


async def run_scrape(sources: list[str]) -> None:
    settings, db = load_runtime()
    pipeline = ScrapePipeline(settings, db)
    batch = await pipeline.scrape(sources)
    total = {
        "matches": len(batch.matches),
        "games": len(batch.games),
        "draft picks": len(batch.draft_picks),
        "player stats": len(batch.player_stats),
        "tournaments": len(batch.tournaments),
    }
    table = Table(title="Scrape Summary")
    table.add_column("Record Type")
    table.add_column("Count", justify="right")
    for name, count in total.items():
        table.add_row(name, str(count))
    console.print(table)


@scrape_app.command("gol")
def scrape_gol() -> None:
    """Scrape gol.gg."""
    asyncio.run(run_scrape(["gol"]))


@scrape_app.command("loltv")
def scrape_loltv() -> None:
    """Scrape loltv.gg."""
    asyncio.run(run_scrape(["loltv"]))


@scrape_app.command("leaguepedia")
def scrape_leaguepedia() -> None:
    """Scrape Leaguepedia."""
    asyncio.run(run_scrape(["leaguepedia"]))


@scrape_app.command("all")
def scrape_all() -> None:
    """Scrape gol.gg, loltv.gg, and Leaguepedia."""
    asyncio.run(run_scrape(["gol", "loltv", "leaguepedia"]))


@app.command("export")
def export(
    out: Annotated[Path | None, typer.Option(help="Output directory for Parquet files.")] = None,
    table: Annotated[list[str] | None, typer.Option(help="Specific table(s) to export.")] = None,
) -> None:
    """Export SQLite tables to Parquet."""
    settings, db = load_runtime()
    asyncio.run(db.initialize())
    selected = table or TABLES
    written = asyncio.run(export_parquet(settings.db_path, out or settings.export_dir, selected))
    for path in written:
        console.print(f"[green]wrote[/green] {path}")


@app.command("status")
def status() -> None:
    """Show database row counts."""
    settings, db = load_runtime()
    counts = asyncio.run(db.status_counts())
    table = Table(title=f"SQLite Status: {settings.db_path}")
    table.add_column("Table")
    table.add_column("Rows", justify="right")
    for name in TABLES:
        table.add_row(name, str(counts[name]))
    console.print(table)


if __name__ == "__main__":
    app()
