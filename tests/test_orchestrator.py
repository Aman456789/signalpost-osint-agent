import json
import httpx
import pytest

from agent_engine.config import load_settings
from agent_engine.orchestrator import EnrichResult, Orchestrator
from agent_engine.registry_client import RegistryClient
from agent_engine.schemas import Flag
from governor.budget_ledger import BudgetLedger
from governor.time_kill_switch import TimeKillSwitch
from tests.helpers import FakeBrreg, FakeClock, make_fact, make_orgnrs, no_sleep


class Crash(BaseException):
    """Stands in for a killed process; it is not an Exception so no handler swallows it."""


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


async def run_job(tmp_path, orgnrs, scenarios=None, *, brake=1950, soft_cap=1700, workers=1,
                  enrich=None, finalize=None, clock=None, ledger=None, resume=False, pass1_only=False):
    brreg = FakeBrreg(scenarios)
    ledger = ledger or BudgetLedger(soft_cap=soft_cap, brake=brake)
    settings = load_settings(output_dir=tmp_path / "out", workers=workers)
    kwargs = {}
    if enrich:
        kwargs["enrich"] = enrich
    if finalize:
        kwargs["finalize"] = finalize
    async with httpx.AsyncClient(transport=brreg.transport) as http:
        registry = RegistryClient(http, ledger, sleep=no_sleep, jitter=lambda: 0)
        orch = Orchestrator(settings, registry, ledger, TimeKillSwitch(clock or FakeClock()), **kwargs)
        try:
            await orch.run(orgnrs, pass1_only=pass1_only, resume=resume)
        finally:
            orch.brreg = brreg
    return orch


def statuses(orch):
    return {orgnr: company.status.value for orgnr, company in orch.companies.items()}


async def test_one_outcome_per_valid_number(tmp_path):
    orgs = make_orgnrs(6)
    scenarios = {orgs[1]: "not_found", orgs[2]: "subunit", orgs[3]: "main_503", orgs[4]: "gone"}
    orch = await run_job(tmp_path, orgs, scenarios, workers=3)
    assert statuses(orch) == {
        orgs[0]: "registry_only",
        orgs[1]: "not_found",
        orgs[2]: "registry_only",
        orgs[3]: "registry_unavailable",
        orgs[4]: "registry_only",
        orgs[5]: "registry_only",
    }
    lines = read_lines(tmp_path / "out" / "dossiers.jsonl")
    assert sorted(line["orgnr"] for line in lines) == sorted(orgs)
    assert orch.stop_reason == "completed" and orch.status == "completed"
    deleted = next(l for l in lines if l["orgnr"] == orgs[4])
    assert deleted["registry_status"] == "deleted"


async def test_events_are_numbered_in_order_and_mirrored_to_disk(tmp_path):
    orch = await run_job(tmp_path, make_orgnrs(4), workers=4)
    sequence = [event["seq"] for event in orch.events]
    assert sequence == list(range(1, len(sequence) + 1))
    on_disk = read_lines(tmp_path / "out" / "events.jsonl")
    assert [event["seq"] for event in on_disk] == sequence
    assert orch.events_since(sequence[-3]) == list(orch.events)[-2:]
    assert on_disk[-1]["type"] == "job.finished"


async def test_resume_skips_finished_companies_and_keeps_counters(tmp_path):
    orgs = make_orgnrs(6)
    seen = []

    async def crashing_enrich(company, ledger):
        seen.append(company.orgnr)
        if company.orgnr == orgs[3]:
            raise Crash()
        return EnrichResult()

    first_ledger = BudgetLedger()
    with pytest.raises(Crash):
        await run_job(tmp_path, orgs, enrich=crashing_enrich, ledger=first_ledger)
    finished = orgs[:3]
    checkpoint = json.loads((tmp_path / "out" / "checkpoints" / "latest.json").read_text())
    assert sorted(checkpoint["done"]) == sorted(finished)

    second_ledger = BudgetLedger()
    orch = await run_job(tmp_path, orgs, ledger=second_ledger, resume=True)
    assert all(orch.brreg.count(orgnr) == 0 for orgnr in finished)
    assert all(orch.brreg.count(orgnr) == 3 for orgnr in orgs[3:])
    assert second_ledger.total == checkpoint["ledger"]["total_outbound_requests"] + 9
    assert statuses(orch) == {orgnr: "registry_only" for orgnr in orgs}
    lines = read_lines(tmp_path / "out" / "dossiers.jsonl")
    assert sorted(line["orgnr"] for line in lines) == sorted(orgs)


async def test_stopping_pass2_leaves_pass1_results_unchanged(tmp_path):
    orgs = make_orgnrs(15)
    clock = FakeClock()
    snapshots = {}
    holder = {}

    async def slow_enrich(company, ledger):
        if not snapshots:
            for orgnr, run in holder["orch"].companies.items():
                snapshots[orgnr] = json.loads(run.dossier.model_dump_json(
                    include={"legal_name", "registry_status", "registry_fields", "roles", "financial_summary"}
                ))
        clock.advance(200)
        return EnrichResult()

    class Spy(Orchestrator):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            holder["orch"] = self

    brreg = FakeBrreg()
    ledger = BudgetLedger()
    settings = load_settings(output_dir=tmp_path / "out", workers=1)
    async with httpx.AsyncClient(transport=brreg.transport) as http:
        registry = RegistryClient(http, ledger, sleep=no_sleep, jitter=lambda: 0)
        orch = Spy(settings, registry, ledger, TimeKillSwitch(clock), enrich=slow_enrich)
        await orch.run(orgs)

    assert orch.stop_reason == "kill_switch" and orch.status == "stopped_time"
    flagged = [o for o in orgs if Flag.TIME_LIMIT_REGISTRY_ONLY in orch.companies[o].flags]
    assert flagged == orgs[10:]
    assert all(orch.companies[o].status.value == "registry_only" for o in orgs)
    for line in read_lines(tmp_path / "out" / "dossiers.jsonl"):
        before = snapshots[line["orgnr"]]
        assert {key: line[key] for key in before} == before
    assert ledger.kill_switch_tripped


async def test_brake_case_a_no_profile_is_not_processed_budget(tmp_path):
    orgs = make_orgnrs(3)
    orch = await run_job(tmp_path, orgs, brake=4)
    assert orch.stop_reason == "request_brake" and orch.status == "stopped_budget"
    assert statuses(orch)[orgs[1]] == "not_processed_budget"
    assert statuses(orch)[orgs[2]] == "not_processed_budget"
    assert Flag.NOT_PROCESSED_BUDGET in orch.companies[orgs[1]].flags
    assert orch.ledger.total <= 4


async def test_brake_case_b_profile_but_no_ai_facts_is_registry_only(tmp_path):
    orgs = make_orgnrs(3)

    async def hungry_enrich(company, ledger):
        await ledger.reserve(company.orgnr, "website")
        return EnrichResult()

    orch = await run_job(tmp_path, orgs, brake=9, enrich=hungry_enrich)
    assert orch.stop_reason == "request_brake"
    for orgnr in orgs:
        company = orch.companies[orgnr]
        assert company.status.value == "registry_only"
        assert company.flags == [Flag.REQUEST_BRAKE]
        assert company.dossier.registry_fields  # pass 1 profile kept
    brake_events = [e for e in orch.events if e["type"] == "budget.brake"]
    assert len(brake_events) == 1
    assert orch.ledger.total == 9


async def test_brake_case_c_fetched_facts_are_finalized_and_published(tmp_path):
    orgs = make_orgnrs(3)
    finalized = []

    async def enrich(company, ledger):
        if company.orgnr == orgs[0]:
            company.fetched_facts.append("raw fact")
        await ledger.reserve(company.orgnr, "website")
        return EnrichResult()

    async def finalize(company):
        finalized.append(company.orgnr)
        return [make_fact(company.orgnr)]

    orch = await run_job(tmp_path, orgs, brake=9, enrich=enrich, finalize=finalize)
    first = orch.companies[orgs[0]]
    assert finalized == [orgs[0]]
    assert first.status.value == "published"
    assert first.flags == [Flag.REQUEST_BRAKE]
    assert first.dossier.verified_fact_count == 1 and len(first.dossier.published_fact_ids) == 1
    assert statuses(orch)[orgs[1]] == "registry_only"
    assert orch.stop_reason == "request_brake"


async def test_brake_case_c_without_a_passing_fact_is_registry_only(tmp_path):
    orgs = make_orgnrs(2)

    async def enrich(company, ledger):
        company.fetched_facts.append("raw fact")
        await ledger.reserve(company.orgnr, "website")
        return EnrichResult()

    orch = await run_job(tmp_path, orgs, brake=6, enrich=enrich)  # default finalize saves nothing
    first = orch.companies[orgs[0]]
    assert first.status.value == "registry_only"
    assert first.flags == [Flag.REQUEST_BRAKE]
    assert first.dossier.verified_fact_count == 0


async def test_hundred_company_run_stays_under_the_brake(tmp_path):
    orgs = make_orgnrs(100)

    async def full_enrich(company, ledger):
        for _ in range(11):
            await ledger.reserve(company.orgnr, "website")
        return EnrichResult()

    orch = await run_job(tmp_path, orgs, workers=8, enrich=full_enrich)
    assert orch.ledger.total == 1400
    assert orch.stop_reason == "completed"
    assert all(orch.ledger.company_requests(o) == 14 for o in orgs)


async def test_brake_holds_at_1950_when_demand_is_higher(tmp_path):
    orgs = make_orgnrs(200)

    async def full_enrich(company, ledger):
        for _ in range(11):
            await ledger.reserve(company.orgnr, "website")
        return EnrichResult()

    orch = await run_job(tmp_path, orgs, workers=8, enrich=full_enrich)
    assert orch.ledger.total <= 1950
    assert orch.stop_reason == "request_brake"
    assert all(run.status.value in {"registry_only", "published", "not_processed_budget"}
               for run in orch.companies.values())
    assert len(read_lines(tmp_path / "out" / "dossiers.jsonl")) == 200
    assert max(orch.ledger.snapshot()["per_company_requests"].values()) <= 14


async def test_pass1_only_stops_before_pass2(tmp_path):
    orgs = make_orgnrs(3)
    called = []

    async def enrich(company, ledger):
        called.append(company.orgnr)
        return EnrichResult()

    orch = await run_job(tmp_path, orgs, enrich=enrich, pass1_only=True)
    assert called == []
    assert statuses(orch) == {o: "pass1_complete" for o in orgs}
    assert orch.status == "pass1_complete"
