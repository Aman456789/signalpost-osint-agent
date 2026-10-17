import json

from agent_engine.cli import run_job
from agent_engine.config import load_settings
from agent_engine.input_processor import parse_input
from tests.helpers import FakeBrreg, make_orgnrs


async def test_happy_path_uses_at_most_three_requests_per_company(tmp_path):
    orgs = make_orgnrs(10)
    brreg = FakeBrreg()
    settings = load_settings(output_dir=tmp_path / "out", workers=4)
    orch = await run_job(settings, orgs, pass1_only=True, transport=brreg.transport)
    for orgnr in orgs:
        assert brreg.count(orgnr) == 3
        assert orch.ledger.company_requests(orgnr) == 3
    assert orch.ledger.total == 30


async def test_invalid_numbers_cause_no_requests_and_valid_ones_get_one_result(tmp_path):
    valid = make_orgnrs(3)
    text = "\n".join([valid[0], "123456789", "12345", "abcdefghi", valid[1], valid[1], valid[2]])
    parsed = parse_input(text)
    assert parsed.accepted == valid
    assert len(parsed.rejected) == 3

    brreg = FakeBrreg({valid[2]: "not_found"})
    settings = load_settings(output_dir=tmp_path / "out", workers=2)
    await run_job(settings, parsed.accepted, pass1_only=True, transport=brreg.transport)

    asked = {orgnr for _, orgnr in brreg.calls}
    assert asked == set(valid)
    rows = [json.loads(line) for line in (tmp_path / "out" / "registry_only_results.jsonl").read_text().splitlines()]
    assert sorted(row["orgnr"] for row in rows) == sorted(valid)
    by_orgnr = {row["orgnr"]: row for row in rows}
    assert by_orgnr[valid[0]]["status"] == "pass1_complete"
    assert by_orgnr[valid[0]]["revenue_nok"] == "12345678.5"
    assert by_orgnr[valid[2]]["status"] == "not_found"
