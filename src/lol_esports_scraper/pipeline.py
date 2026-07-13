from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from loguru import logger
from tqdm import tqdm

from .config import Settings
from .gol_fetcher import GOLFetcher
from .leaguepedia_fetcher import LeaguepediaFetcher
from .loltv_fetcher import LOLTVFetcher
from .models import ParsedBatch, SourcePage
from .parsers import parse_gol, parse_leaguepedia, parse_loltv
from .reconcile import Reconciler
from .storage import Database


class Fetcher(Protocol):
    source: str

    def seed_urls(self, region: str | None = None) -> list[str]: ...

    async def fetch_url(self, url: str, region: str | None = None) -> SourcePage: ...


@dataclass(slots=True)
class FetchJob:
    source: str
    url: str
    region: str | None = None


class ScrapePipeline:
    def __init__(self, settings: Settings, db: Database) -> None:
        self.settings = settings
        self.db = db
        self.reconciler = Reconciler()
        self.fetchers: dict[str, Fetcher] = {
            "gol": GOLFetcher(settings),
            "loltv": LOLTVFetcher(settings),
            "leaguepedia": LeaguepediaFetcher(settings),
        }
        self.visited_urls: set[str] = set()
        self.active_jobs = 0
        self.all_jobs_done = asyncio.Event()
        self.fetch_queue: asyncio.Queue[FetchJob | None] = asyncio.Queue()

    def add_job(self, url: str, source: str, region: str | None = None) -> None:
        if url not in self.visited_urls:
            self.visited_urls.add(url)
            self.active_jobs += 1
            self.fetch_queue.put_nowait(FetchJob(source=source, url=url, region=region))

    def mark_job_done(self) -> None:
        self.active_jobs -= 1
        if self.active_jobs == 0:
            self.all_jobs_done.set()

    async def scrape(self, sources: list[str]) -> ParsedBatch:
        await self.db.initialize()
        self.visited_urls.clear()
        self.active_jobs = 0
        self.all_jobs_done.clear()
        
        while not self.fetch_queue.empty():
            self.fetch_queue.get_nowait()
            
        page_queue: asyncio.Queue[SourcePage | None] = asyncio.Queue()
        batch_queue: asyncio.Queue[ParsedBatch | None] = asyncio.Queue()
        aggregate = ParsedBatch()

        for source in sources:
            fetcher = self.fetchers[source]
            if source in ("leaguepedia", "loltv"):
                for region in self.settings.target_regions:
                    for url in fetcher.seed_urls(region):
                        self.add_job(url, source, region)
            else:
                for url in fetcher.seed_urls(None):
                    self.add_job(url, source, None)

        if self.active_jobs == 0:
            return aggregate

        worker_count = min(max(self.settings.concurrency, 1), 10)
        parser_count = min(2, 5)

        progress = tqdm(desc="pages", unit="page")
        fetch_tasks = [asyncio.create_task(self._fetch_worker(page_queue, progress)) for _ in range(worker_count)]
        parse_tasks = [asyncio.create_task(self._parse_worker(page_queue, batch_queue)) for _ in range(parser_count)]
        store_task = asyncio.create_task(self._store_worker(batch_queue, parser_count, aggregate))

        # Wait until all jobs have finished flowing through the fetcher and parser
        await self.all_jobs_done.wait()
        
        # Shutdown fetch workers
        for _ in range(worker_count):
            await self.fetch_queue.put(None)
        await asyncio.gather(*fetch_tasks)
        progress.close()
        
        # Shutdown parse workers
        for _ in range(parser_count):
            await page_queue.put(None)
        await asyncio.gather(*parse_tasks)
        
        # Shutdown store worker
        await store_task
        return aggregate

    async def _fetch_worker(
        self,
        output: asyncio.Queue[SourcePage | None],
        progress: tqdm,
    ) -> None:
        while True:
            job = await self.fetch_queue.get()
            if job is None:
                self.fetch_queue.task_done()
                return
            
            success = False
            try:
                fetcher = self.fetchers[job.source]
                page = await fetcher.fetch_url(job.url, job.region)
                await asyncio.sleep(self.settings.rate_limit_seconds)
                await output.put(page)
                success = True
            except Exception as exc:
                logger.exception("Fetch failed for {}: {}", job, exc)
            finally:
                progress.update(1)
                self.fetch_queue.task_done()
                if not success:
                    # Job dies here, mark it done
                    self.mark_job_done()

    async def _parse_worker(self, queue: asyncio.Queue[SourcePage | None], output: asyncio.Queue[ParsedBatch | None]) -> None:
        while True:
            page = await queue.get()
            if page is None:
                await output.put(None)
                queue.task_done()
                return
                
            try:
                if page.source == "gol":
                    batch = parse_gol(page)
                elif page.source == "loltv":
                    batch = parse_loltv(page)
                elif page.source == "leaguepedia":
                    batch = parse_leaguepedia(page, self.settings.leaguepedia_base_url)
                else:
                    batch = ParsedBatch()
                    
                # Extract new discovered URLs and feed back into the crawler
                for url in batch.discovered_urls:
                    self.add_job(url, page.source, page.region)
                    
                await output.put(self.reconciler.reconcile_batch(batch))
            except Exception as exc:
                logger.exception("Parse failed for {}: {}", getattr(page, "url", None), exc)
            finally:
                queue.task_done()
                self.mark_job_done()

    async def _store_worker(self, queue: asyncio.Queue[ParsedBatch | None], parser_count: int, aggregate: ParsedBatch) -> None:
        completed_parsers = 0
        while completed_parsers < parser_count:
            batch = await queue.get()
            try:
                if batch is None:
                    completed_parsers += 1
                    continue
                aggregate.extend(batch)
                await self.db.upsert_batch(batch)
            finally:
                queue.task_done()
