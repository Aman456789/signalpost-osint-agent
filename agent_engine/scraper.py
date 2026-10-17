import asyncio
import logging
import re
from dataclasses import dataclass, field
from urllib import robotparser
from urllib.parse import urldefrag, urljoin, urlsplit

import httpx
from selectolax.lexbor import LexborHTMLParser

from agent_engine.errors import BudgetDenied
from agent_engine.schemas import Flag
from agent_engine.url_guard import UnsafeUrl, check_url, is_official_host, resolve

log = logging.getLogger("signalpost.scraper")

USER_AGENT = "signalpost-agent/0.3"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
MAX_HOPS = 5
MAX_WIRE_BYTES = 2 * 1024 * 1024
MAX_DECODED_BYTES = 10 * 1024 * 1024
RETRY_PAUSE_S = (1.0, 2.0)
REDIRECTS = {301, 302, 303, 307, 308}

ABOUT_WORDS = ("om-oss", "om_oss", "omoss", "om oss", "about", "hvem-er-vi", "om-selskapet", "om-bedriften", "om-firmaet")
CONTACT_WORDS = ("kontakt", "contact")
SKIP_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip", ".doc", ".docx", ".xls", ".xlsx", ".mp4")


class FetchFailed(Exception):
    """A page that will not be used. Retrying would not help."""

    def __init__(self, reason: str, flag: Flag | None = None):
        super().__init__(reason)
        self.reason = reason
        self.flag = flag


class Retryable(Exception):
    """429 or 5xx: worth another attempt."""


@dataclass
class FetchedPage:
    url: str
    final_url: str
    status: int
    text: str
    headers: dict
    hops: list[str]


@dataclass
class SiteFetch:
    pages: list[FetchedPage] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def record(self, failure: FetchFailed) -> None:
        self.notes.append(failure.reason)
        if failure.flag:
            self.flags.append(failure.flag)


def time_left(deadline) -> float:
    return max(deadline.when() - asyncio.get_running_loop().time(), 0.001)


def decode_text(body: bytes, content_type: str) -> str:
    match = re.search(r"charset=([\w-]+)", content_type, re.I)
    name = match.group(1) if match else None
    if not name:
        meta = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", body[:4096], re.I)
        name = meta.group(1).decode("ascii") if meta else "utf-8"
    try:
        return body.decode(name, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def is_html(content_type: str) -> bool:
    return content_type.split(";")[0].strip().lower() in ("text/html", "application/xhtml+xml")


async def read_body(response: httpx.Response) -> bytes:
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_WIRE_BYTES:
        raise FetchFailed("too_large")
    chunks, total = [], 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > MAX_DECODED_BYTES or response.num_bytes_downloaded > MAX_WIRE_BYTES:
            raise FetchFailed("too_large")
        chunks.append(chunk)
    return b"".join(chunks)


def same_page(url: str) -> str:
    parts = urlsplit(url)
    return f"{(parts.hostname or '').removeprefix('www.')}{parts.path.rstrip('/')}?{parts.query}"


def find_page_links(html: str, base_url: str, official_domain: str, limit: int) -> list[str]:
    """About pages first, then contact pages; only links on the official domain."""
    seen = {same_page(base_url)}
    abouts, contacts = [], []
    for link in LexborHTMLParser(html).css("a[href]"):
        href = (link.attributes.get("href") or "").strip()
        if not href:
            continue
        url = urldefrag(urljoin(base_url, href))[0]
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or parts.path.lower().endswith(SKIP_EXTENSIONS):
            continue
        if not is_official_host(parts.hostname, official_domain) or same_page(url) in seen:
            continue
        label = f"{parts.path} {link.text(strip=True)}".lower()
        if any(word in label for word in ABOUT_WORDS):
            abouts.append(url)
        elif any(word in label for word in CONTACT_WORDS):
            contacts.append(url)
        else:
            continue
        seen.add(same_page(url))
    picks = abouts[:1] + contacts[:1] + abouts[1:] + contacts[1:]
    return picks[:max(limit, 0)]


class Scraper:
    def __init__(self, http: httpx.AsyncClient, ledger, settings, *, resolver=resolve, sleep=asyncio.sleep):
        self.http = http
        self.ledger = ledger
        self.timeout = settings.website_timeout_s
        self.retries = settings.website_retries
        self.max_pages = settings.website_max_pages
        self.resolve = resolver
        self.sleep = sleep
        self._robots: dict[str, robotparser.RobotFileParser] = {}
        self._robots_locks: dict[str, asyncio.Lock] = {}

    async def fetch_site(self, company_id: str, start_url: str, official_domain: str) -> SiteFetch:
        result = SiteFetch()
        try:
            home = await self._fetch_page(company_id, start_url, official_domain, optional=False)
        except FetchFailed as failure:
            result.record(failure)
            return result
        result.pages.append(home)

        for link in find_page_links(home.text, home.final_url, official_domain, self.max_pages - 1):
            try:
                result.pages.append(await self._fetch_page(company_id, link, official_domain, optional=True))
            except BudgetDenied as denied:
                if denied.reason not in ("soft_cap", "per_company_cap"):
                    raise
                result.notes.append(f"skipped:{denied.reason}")
                break
            except FetchFailed as failure:
                result.notes.append(failure.reason)  # a bad About page does not make the site unreachable
                if failure.reason == "blocked_403":
                    break
        return result

    async def _fetch_page(self, company_id: str, url: str, official_domain: str, optional: bool) -> FetchedPage:
        reason = "unknown"
        for attempt in range(self.retries + 1):
            if attempt:
                await self.sleep(RETRY_PAUSE_S[min(attempt - 1, len(RETRY_PAUSE_S) - 1)])
            try:
                # One deadline for the whole attempt: DNS, connect, TLS, every hop, the body.
                async with asyncio.timeout(self.timeout) as deadline:
                    page = await self._get(company_id, url, official_domain, deadline,
                                           first_kind="retry" if attempt else "website", optional=optional)
            except Retryable as exc:
                reason = str(exc)
            except (httpx.TransportError, OSError) as exc:  # timeouts, refused, DNS
                reason = type(exc).__name__
            else:
                return self._accept(page)
            log.warning("fetch attempt failed", extra={"fields": {
                "company": company_id, "url": url, "attempt": attempt + 1, "reason": reason}})
        raise FetchFailed(f"unreachable:{reason}", Flag.WEBSITE_UNREACHABLE)

    def _accept(self, page: FetchedPage) -> FetchedPage:
        if page.status == 403:
            raise FetchFailed("blocked_403")  # no other headers, no other identity
        if not 200 <= page.status < 300:
            raise FetchFailed(f"http_{page.status}")
        return page

    async def _get(self, company_id, url, official_domain, deadline, *, first_kind, optional,
                   is_robots=False) -> FetchedPage:
        hops: list[str] = []
        current = url
        for hop in range(MAX_HOPS + 1):
            try:
                host = await check_url(current, self.resolve)
            except UnsafeUrl as unsafe:
                raise FetchFailed(f"unsafe_url:{unsafe.reason}") from None
            if not is_official_host(host, official_domain):
                raise FetchFailed(f"off_domain:{current}")
            if not is_robots:
                await self._check_robots(company_id, current, official_domain, deadline, optional)

            kind = first_kind if hop == 0 else "redirect_hop"
            await self.ledger.reserve(company_id, kind, optional=optional and hop == 0)
            hops.append(current)

            async with self.http.stream("GET", current, headers=HEADERS, follow_redirects=False,
                                        timeout=time_left(deadline)) as response:
                location = response.headers.get("location")
                if response.status_code in REDIRECTS and location:
                    current = urldefrag(urljoin(current, location))[0]
                    continue
                if response.status_code == 429 or response.status_code >= 500:
                    raise Retryable(f"http_{response.status_code}")
                content_type = response.headers.get("content-type", "")
                body = b""
                if 200 <= response.status_code < 300:
                    if not is_robots and not is_html(content_type):
                        raise FetchFailed("not_html")
                    body = await read_body(response)
                headers = {key.lower(): value for key, value in response.headers.items()}
                return FetchedPage(url, current, response.status_code, decode_text(body, content_type), headers, hops)
        raise FetchFailed("too_many_redirects", Flag.WEBSITE_UNREACHABLE)

    async def _check_robots(self, company_id, url, official_domain, deadline, optional) -> None:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        async with self._robots_locks.setdefault(origin, asyncio.Lock()):
            rules = self._robots.get(origin)
            if rules is None:
                rules = await self._load_robots(company_id, origin, official_domain, deadline, optional)
                self._robots[origin] = rules  # a timeout never reaches this line, so it is retried
        if not rules.can_fetch(USER_AGENT, url):
            raise FetchFailed("robots_disallowed")

    async def _load_robots(self, company_id, origin, official_domain, deadline, optional):
        rules = robotparser.RobotFileParser()
        lines: list[str] = []
        try:
            robots = await self._get(company_id, origin + "/robots.txt", official_domain, deadline,
                                     first_kind="website", optional=optional, is_robots=True)
            if robots.status == 200:
                lines = robots.text.splitlines()
        except FetchFailed as failure:
            if not failure.reason.startswith("off_domain"):
                raise
        # a missing or unreadable (4xx) robots.txt means "everything allowed"
        rules.parse(lines)
        rules.modified()
        return rules
