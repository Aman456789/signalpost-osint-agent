import json
import re
from decimal import Decimal

from agent_engine.orchestrator import EnrichResult
from agent_engine.schemas import RunReport
from governor.budget_ledger import BudgetLedger
from tests.helpers import make_orgnrs
from tests.helpers_run import mock_enrich, read_jsonl, run_job


def load_report(tmp_path):
    return json.loads((tmp_path / "out" / "run_report.json").read_text())


async def test_report_totals_equal_ledger_totals(tmp_path):
    orgs = make_orgnrs(8)
    ledger = BudgetLedger()
    orch = await run_job(tmp_path, orgs, enrich=mock_enrich(tmp_path / "snap"), ledger=ledger, workers=4)
    report, snapshot = load_report(tmp_path), ledger.snapshot()

    assert report["requests"] == {"total": ledger.total, "by_kind": snapshot["requests_by_kind"]}
    assert sum(report["requests"]["by_kind"].values()) == report["requests"]["total"]
    assert report["llm_calls"] == ledger.llm_calls == 8
    assert (report["input_tokens"], report["output_tokens"]) == (ledger.input_tokens, ledger.output_tokens)
    assert report["estimated_cost_usd"] == f"{ledger.cost_usd:.4f}" == "0.0168"
    assert report["stop_reason"] == orch.stop_reason == "completed"
    assert report["flags"] == {"soft_cap_reached": False, "brake_tripped": False,
                               "kill_switch_tripped": False, "plan_a_outage_detected": False}


async def test_report_outcomes_and_rejections_match_the_files(tmp_path):
    orgs = make_orgnrs(5)
    await run_job(tmp_path, orgs, scenarios={orgs[1]: "not_found"}, enrich=mock_enrich(tmp_path / "snap"))
    report = load_report(tmp_path)
    dossiers = read_jsonl(tmp_path / "out" / "dossiers.jsonl")
    rejections = read_jsonl(tmp_path / "out" / "rejections.jsonl")

    assert report["outcomes"] == {"published": 4, "not_found": 1}
    assert sum(report["outcomes"].values()) == report["company_count"] == len(dossiers) == 5
    assert report["rejections_by_reason"] == {"quote_not_found": len(rejections)} == {"quote_not_found": 4}
    assert re.fullmatch(r"[0-9]+\.[0-9]{2,4}", report["estimated_cost_usd"])
    RunReport.model_validate(report)


async def test_brake_run_reports_the_flags_and_the_same_totals(tmp_path):
    ledger = BudgetLedger(soft_cap=5, brake=9)

    async def hungry(company, ledger):
        await ledger.reserve(company.orgnr, "website")
        return EnrichResult()

    orch = await run_job(tmp_path, make_orgnrs(3), enrich=hungry, ledger=ledger)
    report = load_report(tmp_path)
    assert report["stop_reason"] == orch.stop_reason == "request_brake"
    assert report["flags"]["brake_tripped"] and report["flags"]["soft_cap_reached"]
    assert report["requests"]["total"] == ledger.total == 9
    assert report["requests"]["by_kind"] == ledger.snapshot()["requests_by_kind"]
    assert Decimal(report["estimated_cost_usd"]) == ledger.cost_usd
