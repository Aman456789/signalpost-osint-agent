import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import httpx

from agent_engine.config import load_settings
from agent_engine.orchestrator import EnrichResult, Orchestrator
from agent_engine.profile import empty_dossier
from agent_engine.registry_client import RegistryClient
from agent_engine.schemas import FactKey, ProcessingStatus, RejectionReason, RejectionRecord
from governor.budget_ledger import BudgetLedger
from governor.time_kill_switch import TimeKillSwitch
from storage.evidence_vault import EvidenceVault
from storage.store import SourceRecord
from tests.helpers import FakeBrreg, FakeClock, make_fact, no_sleep

PAGE = "Eksempel Konsult AS tilbyr radgivning til norske bedrifter. Vi har kontor i Oslo."


class Crash(BaseException):
    """Stands in for a killed process; it is not an Exception so no handler swallows it."""


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def make_rejection(orgnr, job_id, reason=RejectionReason.QUOTE_NOT_FOUND):
    return RejectionRecord(
        rejection_id=uuid4(), job_id=job_id, orgnr=orgnr, validation_stage="quote", reason_code=reason,
        rejected_value="We are the biggest in Norway", rejected_at=datetime.now(timezone.utc),
    )


def make_source(orgnr, url="https://example.no/", sha256="b" * 64):
    return SourceRecord(
        source_id=uuid4(), orgnr=orgnr, url=url, final_url=url, http_status=200,
        retrieved_at=datetime.now(timezone.utc), sha256=sha256, language="no",
        domain_on_official_list=True, identity_score=Decimal("0.9"),
    )


def dossier_for(orgnr, job_id, facts=()):
    dossier = empty_dossier(orgnr, ProcessingStatus.PUBLISHED if facts else ProcessingStatus.REGISTRY_ONLY, job_id)
    return dossier.model_copy(update={
        "published_fact_ids": [str(fact.fact_id) for fact in facts],
        "verified_fact_count": len(facts),
    })


def mock_enrich(snapshot_dir):
    """Pass 2 with a mock model: one answer whose quote is on the page, one that is not."""
    vault = EvidenceVault(snapshot_dir)

    async def enrich(company, ledger):
        await ledger.reserve(company.orgnr, "website")
        await ledger.reserve(company.orgnr, "llm")
        await ledger.add_usage(1200, 150, Decimal("0.0021"))
        snapshot = vault.save(PAGE, url="https://example.no/", final_url="https://example.no/",
                              status=200, language="no")
        source = make_source(company.orgnr, snapshot.url, snapshot.sha256)
        answers = [("products", "radgivning til norske bedrifter"), ("scale", "We are the biggest in Norway")]
        result = EnrichResult(sources=[source])
        for key, quote in answers:
            if quote in snapshot.text:
                fact = make_fact(company.orgnr).model_copy(update={
                    "key": FactKey(key), "quote": quote, "sha256": snapshot.sha256, "source_id": source.source_id,
                    "source_url": snapshot.url, "retrieved_at": snapshot.retrieved_at,
                })
                result.facts.append(fact)
            else:
                result.rejections.append(make_rejection(company.orgnr, company.dossier.job_id))
        return result

    return enrich


async def run_job(tmp_path, orgnrs, *, scenarios=None, workers=1, enrich=None, ledger=None,
                  resume=False, pass1_only=False):
    brreg = FakeBrreg(scenarios)
    ledger = ledger or BudgetLedger()
    settings = load_settings(output_dir=tmp_path / "out", workers=workers)
    kwargs = {"enrich": enrich} if enrich else {}
    async with httpx.AsyncClient(transport=brreg.transport) as http:
        registry = RegistryClient(http, ledger, sleep=no_sleep, jitter=lambda: 0)
        orch = Orchestrator(settings, registry, ledger, TimeKillSwitch(FakeClock()), **kwargs)
        await orch.run(orgnrs, pass1_only=pass1_only, resume=resume)
    return orch
