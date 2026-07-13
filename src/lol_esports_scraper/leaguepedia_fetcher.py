from __future__ import annotations

from urllib.parse import quote, urljoin

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import Settings
from .models import SourcePage


REGION_PAGES = {
    "LCK": ["LCK"] + [f"LCK/{year}_Season" for year in range(2020, 2027)],
    "LPL": ["LPL"] + [f"LPL/{year}_Season" for year in range(2020, 2027)],
    "LEC": ["LEC"] + [f"LEC/{year}_Season" for year in range(2020, 2027)],
    "LCP": ["League_of_Legends_Championship_Pacific", "LCP/2026_Season"],
    "LCS": ["LCS"] + [f"LCS/{year}_Season" for year in range(2020, 2027)],
}


class LeaguepediaFetcher:
    source = "leaguepedia"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def seed_urls(self, region: str | None = None) -> list[str]:
        base = self.settings.leaguepedia_base_url
        pages = REGION_PAGES.get((region or "").upper(), ["Portal:Tournaments", "Portal:Transfers", "Portal:Statistics"])
        return [urljoin(base + "/", quote(page, safe="/:_")) for page in pages]

    @retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(3), reraise=True)
    async def fetch_url(self, url: str, region: str | None = None) -> SourcePage:
        logger.info("Fetching Leaguepedia {}", url)
        headers = {
            "User-Agent": self.settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
        return SourcePage(source=self.source, url=str(response.url), html=response.text, region=region, json_payloads=[])
