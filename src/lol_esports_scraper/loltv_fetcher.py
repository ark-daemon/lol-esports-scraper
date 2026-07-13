from __future__ import annotations

from urllib.parse import urljoin

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from .browser import CloakBrowserClient
from .config import Settings
from .models import SourcePage


class LOLTVFetcher:
    source = "loltv"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.browser = CloakBrowserClient(settings.fingerprint_seed)

    def seed_urls(self, region: str | None = None) -> list[str]:
        base = self.settings.loltv_base_url
        region_slug = (region or "").lower()
        urls = [
            urljoin(base + "/", ""),
            urljoin(base + "/", "matches"),
            urljoin(base + "/", "standings"),
        ]
        if region_slug:
            urls.extend(
                [
                    urljoin(base + "/", f"leagues/{region_slug}"),
                    urljoin(base + "/", f"teams?region={region_slug}"),
                ]
            )
        return urls

    @retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(3), reraise=True)
    async def fetch_url(self, url: str, region: str | None = None) -> SourcePage:
        logger.info("Rendering loltv.gg {}", url)
        rendered = await self.browser.render(url)
        logger.debug("Captured {} loltv.gg JSON/XHR payloads from {}", len(rendered.json_payloads), url)
        return SourcePage(source=self.source, url=url, html=rendered.html, region=region, json_payloads=rendered.json_payloads)
