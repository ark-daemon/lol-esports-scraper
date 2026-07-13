from __future__ import annotations

from urllib.parse import urljoin

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from .browser import CloakBrowserClient
from .config import Settings
from .models import SourcePage


GOL_OPTIONAL_TAB_SELECTORS = [
    "a[href*='game']",
    "a[href*='stats']",
    "a[href*='draft']",
    "button:has-text('Stats')",
    "button:has-text('Draft')",
    "button:has-text('Timeline')",
]


class GOLFetcher:
    source = "gol"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.browser = CloakBrowserClient(settings.fingerprint_seed)

    def seed_urls(self, region: str | None = None) -> list[str]:
        base = self.settings.gol_base_url
        return [
            urljoin(base + "/", "tournament/list/"),
            urljoin(base + "/", "teams/list/season-ALL/split-ALL/tournament-ALL/"),
            urljoin(base + "/", "players/list/season-ALL/split-ALL/tournament-ALL/"),
        ]

    @retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(3), reraise=True)
    async def fetch_url(self, url: str, region: str | None = None) -> SourcePage:
        logger.info("Rendering gol.gg {}", url)
        click_selectors = GOL_OPTIONAL_TAB_SELECTORS if 'game' in url or 'match' in url else []
        rendered = await self.browser.render(url, click_selectors=click_selectors)
        logger.debug("Captured {} gol.gg JSON/XHR payloads from {}", len(rendered.json_payloads), url)
        return SourcePage(source=self.source, url=url, html=rendered.html, region=region, json_payloads=rendered.json_payloads)
