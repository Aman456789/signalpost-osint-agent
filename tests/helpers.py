from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx

from agent_engine.registry_client import RegistryClient
from governor.budget_ledger import BudgetLedger
from validators.orgnr_checksum import WEIGHTS

FIXTURES = Path(__file__).parent / "fixtures" / "registry"
FIXTURE_ORGNR = "923456783"

# (kind, scenario) -> (status, fixture file); anything missing falls back to the "ok" entry
RESPONSES = {
    ("main", "ok"): (200, "main_200.json"),
    ("main", "not_found"): (404, "main_404.json"),
    ("main", "subunit"): (404, "main_404.json"),
    ("main", "gone"): (410, "gone_410.json"),
    ("main", "main_503"): (503, "error_503.txt"),
    ("main", "main_malformed"): (200, "main_malformed.txt"),
    ("sub", "ok"): (404, "main_404.json"),
    ("sub", "subunit"): (200, "subunit_200.json"),
    ("roles", "ok"): (200, "roles_200.json"),
    ("accounts", "ok"): (200, "accounts_200.json"),
    ("accounts", "no_accounts"): (404, "accounts_404.json"),
    ("accounts", "accounts_503"): (503, "error_503.txt"),
    ("accounts", "accounts_malformed"): (200, "accounts_malformed.txt"),
}


class FakeBrreg:
    def __init__(self, scenarios=None):
        self.scenarios = scenarios or {}
        self.calls: list[tuple[str, str]] = []
        self.transport = httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        parts = request.url.path.strip("/").split("/")
        if parts[0] == "regnskapsregisteret":
            kind, orgnr = "accounts", parts[2]
        elif parts[2] == "underenheter":
            kind, orgnr = "sub", parts[3]
        elif len(parts) > 4:
            kind, orgnr = "roles", parts[3]
        else:
            kind, orgnr = "main", parts[3]
        self.calls.append((kind, orgnr))
        scenario = self.scenarios.get(orgnr, "ok")
        status, name = RESPONSES.get((kind, scenario)) or RESPONSES[(kind, "ok")]
        body = (FIXTURES / name).read_text(encoding="utf-8").replace(FIXTURE_ORGNR, orgnr)
        return httpx.Response(status, content=body.encode("utf-8"))

    def count(self, orgnr: str | None = None) -> int:
        return sum(1 for _, number in self.calls if orgnr is None or number == orgnr)


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


async def no_sleep(_seconds):
    return None


@asynccontextmanager
async def registry(scenarios=None, ledger=None):
    brreg = FakeBrreg(scenarios)
    ledger = ledger or BudgetLedger()
    async with httpx.AsyncClient(transport=brreg.transport) as http:
        yield RegistryClient(http, ledger, sleep=no_sleep, jitter=lambda: 0), brreg, ledger


def make_orgnrs(count: int, start: int = 10000) -> list[str]:
    numbers = []
    n = start
    while len(numbers) < count:
        prefix = f"{n:08d}"
        n += 1
        check = 11 - sum(int(d) * w for d, w in zip(prefix, WEIGHTS)) % 11
        check = 0 if check == 11 else check
        if check != 10:
            numbers.append(prefix + str(check))
    return numbers


def make_fact(orgnr: str):
    from agent_engine.schemas import PublishedFact

    now = datetime.now(timezone.utc)
    return PublishedFact(
        fact_id=uuid4(), orgnr=orgnr, key="products", value="Consulting", value_no="Rådgivning",
        quote="We offer consulting.", method="llm_verified", source_id=uuid4(),
        source_url="https://example.no/", retrieved_at=now, sha256="a" * 64, as_of=now,
        identity_score="0.9", q="1", v="1", g="1", s="1", f="1", confidence="0.9",
        validation_id=uuid4(), created_at=now,
    )
