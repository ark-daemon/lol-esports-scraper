from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass(slots=True)
class NetworkPayload:
    url: str
    method: str | None = None
    status: int | None = None
    payload: Any = None


@dataclass(slots=True)
class RenderedPage:
    url: str
    html: str
    json_payloads: list[dict[str, Any]] = field(default_factory=list)


class CloakBrowserClient:
    """Small async wrapper around CloakBrowser with safe defaults."""

    def __init__(self, fingerprint_seed: int, wait_after_load_seconds: float = 2.0) -> None:
        self.fingerprint_seed = fingerprint_seed
        self.wait_after_load_seconds = wait_after_load_seconds

    async def render(
        self,
        url: str,
        *,
        click_selectors: list[str] | None = None,
        type_actions: list[tuple[str, str]] | None = None,
    ) -> RenderedPage:
        from cloakbrowser import launch_async

        browser = await launch_async(args=[f"--fingerprint={self.fingerprint_seed}"])
        json_payloads: list[dict[str, Any]] = []
        pending_tasks: set[asyncio.Task[None]] = set()

        try:
            page = await browser.new_page()

            async def collect_response(response: Any) -> None:
                try:
                    request = response.request
                    resource_type = getattr(request, "resource_type", None)
                    if resource_type not in {"xhr", "fetch"}:
                        return
                    content_type = ""
                    try:
                        content_type = (await response.header_value("content-type")) or ""
                    except Exception:
                        pass
                    if "json" not in content_type.lower() and not response.url.lower().endswith(".json"):
                        return
                    payload = await response.json()
                    if isinstance(payload, dict):
                        json_payloads.append(
                            {
                                "_request_url": response.url,
                                "_status": getattr(response, "status", None),
                                "payload": payload,
                            }
                        )
                    elif isinstance(payload, list):
                        json_payloads.append(
                            {
                                "_request_url": response.url,
                                "_status": getattr(response, "status", None),
                                "payload": payload,
                            }
                        )
                except Exception as exc:
                    logger.debug("Skipping non-parseable network response: {}", exc)

            def on_response(response: Any) -> None:
                task = asyncio.create_task(collect_response(response))
                pending_tasks.add(task)
                task.add_done_callback(pending_tasks.discard)

            page.on("response", on_response)
            await page.goto(url, wait_until="domcontentloaded")
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception as exc:
                logger.debug("Network idle wait skipped for {}: {}", url, exc)

            for selector, value in type_actions or []:
                await page.type(selector, value, delay=50)
                await asyncio.sleep(0.4)

            for selector in click_selectors or []:
                try:
                    await page.click(selector, timeout=1500)
                    await asyncio.sleep(self.wait_after_load_seconds)
                except Exception as exc:
                    logger.debug("Optional click failed on {} selector {}: {}", url, selector, exc)

            await asyncio.sleep(self.wait_after_load_seconds)
            if pending_tasks:
                await asyncio.gather(*pending_tasks, return_exceptions=True)
            html = await page.content()
            return RenderedPage(url=url, html=html, json_payloads=json_payloads)
        finally:
            await browser.close()
