"""Smoke tests for packaging and defaults."""

from lol_esports_scraper import __version__
from lol_esports_scraper.config import Settings


def test_version() -> None:
    assert __version__


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)
    assert "gol.gg" in settings.gol_base_url
    assert "liquipedia" in settings.leaguepedia_base_url
    assert "ResearchBot" in settings.user_agent or "LoL" in settings.user_agent
    assert "Mozilla" not in settings.user_agent
