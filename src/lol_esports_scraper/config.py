from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the scraper."""

    model_config = SettingsConfigDict(env_prefix="LOL_", env_file=".env", env_file_encoding="utf-8")

    gol_base_url: str = "https://gol.gg"
    loltv_base_url: str = "https://www.loltv.gg"
    leaguepedia_base_url: str = "https://liquipedia.net/leagueoflegends"

    target_regions: list[str] = Field(default_factory=lambda: ["LCK", "LPL", "LEC", "LCP", "LCS"])
    db_path: Path = Path("lol.db")
    logs_dir: Path = Path("logs")
    export_dir: Path = Path("exports")

    concurrency: int = 2
    browser_concurrency: int = 1
    rate_limit_seconds: float = 1.5
    request_timeout_seconds: float = 30.0
    fingerprint_seed: int = 42069
    user_agent: str = (
        "LoLEsportsResearchBot/0.1 "
        "(+https://github.com/ark-daemon/lol-esports-scraper; contact: you@example.com)"
    )

    @field_validator("gol_base_url", "loltv_base_url", "leaguepedia_base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("target_regions", mode="before")
    @classmethod
    def parse_regions(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip().upper() for part in value.split(",") if part.strip()]
        return value


def get_settings() -> Settings:
    return Settings()
