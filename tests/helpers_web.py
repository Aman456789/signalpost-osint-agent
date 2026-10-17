import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from agent_engine.config import load_settings
from agent_engine.scraper import Scraper
from governor.budget_ledger import BudgetLedger
from tests.helpers import no_sleep

PAGES = Path(__file__).parent / "fixtures" / "trap_pages"
HOST = "eksempelkonsult.no"
HOME = f"https://{HOST}/"
PUBLIC_IP = "93.184.216.34"


@dataclass
class Page:
    body: str | bytes = ""
    status: int = 200
    headers: dict = field(default_factory=dict)
    delay: float = 0
    content_type: str = "text/html; charset=utf-8"


def fixture(name: str, **kwargs) -> Page:
    return Page(body=(PAGES / name).read_text(encoding="utf-8"), **kwargs)


def redirect(to: str, status: int = 301, delay: float = 0) -> Page:
    return Page(status=status, headers={"location": to}, delay=delay, content_type="text/plain")


class FakeWeb:
    """Serves pages by URL. A list is served in order and its last item repeats."""

    def __init__(self, routes: dict):
        self.routes = {url: list(page) if isinstance(page, list) else [page] for url, page in routes.items()}
        self.calls: list[str] = []
        self.transport = httpx.MockTransport(self.handle)

    async def handle(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.calls.append(url)
        pages = self.routes.get(url)
        if pages is None:
            return httpx.Response(404, content=b"not found", headers={"content-type": "text/plain"})
        page = pages.pop(0) if len(pages) > 1 else pages[0]
        if page.delay:
            await asyncio.sleep(page.delay)
        body = page.body.encode("utf-8") if isinstance(page.body, str) else page.body
        headers = {"content-type": page.content_type, **page.headers}
        return httpx.Response(page.status, content=body, headers=headers)

    def count(self, url: str) -> int:
        return self.calls.count(url)


PRIVATE_HOSTS = {"intranet.eksempelkonsult.no": "10.0.0.5"}


async def fake_resolver(host: str) -> list[str]:
    return [PRIVATE_HOSTS.get(host, PUBLIC_IP)]


async def make_scraper(web: FakeWeb, ledger=None, **overrides):
    """Returns (scraper, ledger, http client). The caller closes the client."""
    settings = load_settings(**overrides)
    ledger = ledger or BudgetLedger()
    http = httpx.AsyncClient(transport=web.transport)
    return Scraper(http, ledger, settings, resolver=fake_resolver, sleep=no_sleep), ledger, http
