import asyncio
import hashlib
import json
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from agent_engine.errors import SourceUnavailable
from agent_engine.schemas import CompanyRole
from governor.backoff import CircuitBreaker, call_with_retries

log = logging.getLogger("signalpost.registry")

# Endpoint URLs: verify against the official Brreg documentation before use (task P0-05).
ENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}"
UNDERENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/underenheter/{orgnr}"
ROLLER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}/roller"
REGNSKAP_URL = "https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}"

HEADERS = {"Accept": "application/json", "User-Agent": "signalpost-agent/0.2"}
REGISTRY_TIMEOUT_S = 10.0
REGISTRY_TRIES = 3  # first try plus two reserved retries
OUTAGE_LIMIT = 3

ROLE_TYPES = {"LEDE": "chair", "NEST": "deputy_chair", "MEDL": "board_member", "DAGL": "ceo"}


@dataclass
class RegistryRecord:
    orgnr: str
    is_subunit: bool
    parent_orgnr: str | None
    legal_name: str | None
    org_form: str | None
    status: str
    website: str | None
    raw: dict
    url: str
    sha256: str
    retrieved_at: datetime


@dataclass
class AccountsResult:
    kind: str  # "ok", "none" (no accounts filed) or "outage"
    reason: str | None = None
    entries: list = field(default_factory=list)
    url: str = ""
    sha256: str | None = None
    retrieved_at: datetime | None = None


def dig(data, path):
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def decode_json(response: httpx.Response):
    try:
        return json.loads(response.text, parse_float=Decimal)
    except ValueError:
        raise SourceUnavailable("format_change") from None


def registry_status(raw: dict, deleted: bool = False) -> str:
    if deleted or raw.get("slettedato") or raw.get("nedleggelsesdato"):
        return "deleted"
    if raw.get("konkurs"):
        return "bankrupt"
    if raw.get("underAvvikling") or raw.get("underTvangsavviklingEllerTvangsopplosning"):
        return "dissolved"
    return "active"


def role_holder_name(item: dict) -> str | None:
    person = item.get("person")
    if person:
        name = person.get("navn") or {}
        parts = [name.get("fornavn"), name.get("mellomnavn"), name.get("etternavn")]
        return " ".join(part for part in parts if part) or None
    names = (item.get("enhet") or {}).get("navn") or []
    return names[0] if names else None


class RegistryClient:
    def __init__(self, http: httpx.AsyncClient, ledger, sleep=asyncio.sleep, jitter=random.random):
        self.http = http
        self.ledger = ledger
        self._sleep = sleep
        self._jitter = jitter
        self._registry_breaker = CircuitBreaker()
        self._accounts_breaker = CircuitBreaker()
        self._outage_count = 0
        self.plan_c = False

    async def _get(self, url: str, orgnr: str, breaker: CircuitBreaker) -> httpx.Response:
        async def send():
            return await self.http.get(url, headers=HEADERS)

        return await call_with_retries(
            send, self.ledger, orgnr, "registry",
            breaker=breaker, max_tries=REGISTRY_TRIES, sleep=self._sleep, jitter=self._jitter,
        )

    async def fetch_company(self, orgnr: str) -> RegistryRecord | None:
        for template, is_subunit in ((ENHETER_URL, False), (UNDERENHETER_URL, True)):
            url = template.format(orgnr=orgnr)
            response = await self._get(url, orgnr, self._registry_breaker)
            if response.status_code == 404:
                continue
            if response.status_code not in (200, 410):
                raise SourceUnavailable(f"http_{response.status_code}")
            return self._record(response, orgnr, is_subunit, url)
        return None

    def _record(self, response: httpx.Response, orgnr: str, is_subunit: bool, url: str) -> RegistryRecord:
        raw = decode_json(response)
        if not isinstance(raw, dict) or raw.get("organisasjonsnummer") != orgnr:
            raise SourceUnavailable("format_change")
        return RegistryRecord(
            orgnr=orgnr,
            is_subunit=is_subunit,
            parent_orgnr=raw.get("overordnetEnhet") if is_subunit else None,
            legal_name=raw.get("navn"),
            org_form=dig(raw, ("organisasjonsform", "kode")),
            status=registry_status(raw, deleted=response.status_code == 410),
            website=raw.get("hjemmeside") or None,
            raw=raw,
            url=url,
            sha256=hashlib.sha256(response.content).hexdigest(),
            retrieved_at=datetime.now(timezone.utc),
        )

    async def fetch_roles(self, orgnr: str) -> list[CompanyRole]:
        response = await self._get(ROLLER_URL.format(orgnr=orgnr), orgnr, self._registry_breaker)
        if response.status_code == 404:
            return []
        if response.status_code != 200:
            raise SourceUnavailable(f"http_{response.status_code}")
        body = decode_json(response)
        if not isinstance(body, dict):
            raise SourceUnavailable("format_change")
        roles = []
        for group in body.get("rollegrupper") or []:
            for item in group.get("roller") or []:
                if item.get("fratraadt") or item.get("avregistrert"):
                    continue
                name = role_holder_name(item)
                if name:
                    code = (item.get("type") or {}).get("kode")
                    roles.append(CompanyRole(name=name, role=ROLE_TYPES.get(code, "other")))
        return roles

    async def fetch_accounts(self, orgnr: str) -> AccountsResult:
        url = REGNSKAP_URL.format(orgnr=orgnr)
        if self.plan_c:
            return AccountsResult("outage", "plan_a_outage", url=url)
        try:
            response = await self._get(url, orgnr, self._accounts_breaker)
            result = self._accounts_result(response, url)
        except SourceUnavailable as exc:
            reason = "format_change" if str(exc) == "format_change" else "accounts_unreachable"
            result = AccountsResult("outage", reason, url=url)
        self._count_outage(result.kind == "outage")
        return result

    def _accounts_result(self, response: httpx.Response, url: str) -> AccountsResult:
        if response.status_code == 404:
            return AccountsResult("none", "no_accounts_filed", url=url)
        if response.status_code != 200:
            raise SourceUnavailable(f"http_{response.status_code}")
        entries = decode_json(response)
        if not isinstance(entries, list):
            raise SourceUnavailable("format_change")
        for entry in entries:
            if not isinstance(dig(entry, ("regnskapsperiode", "tilDato")), str):
                raise SourceUnavailable("format_change")
        kind = "ok" if entries else "none"
        return AccountsResult(
            kind,
            None if entries else "no_accounts_filed",
            entries=entries,
            url=url,
            sha256=hashlib.sha256(response.content).hexdigest(),
            retrieved_at=datetime.now(timezone.utc),
        )

    def _count_outage(self, is_outage: bool) -> None:
        if not is_outage:
            self._outage_count = 0
            return
        self._outage_count += 1
        if self._outage_count >= OUTAGE_LIMIT and not self.plan_c:
            self.plan_c = True
            log.warning("accounts API outage: switching to Plan C for the rest of the run")
