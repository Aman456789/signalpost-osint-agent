import json

from agent_engine import cli
from agent_engine.config import load_settings
from tests.helpers import FakeBrreg, make_orgnrs
from tests.helpers_run import mock_enrich, read_jsonl


async def test_fixture_run_with_a_mock_llm_writes_the_three_output_files(tmp_path):
    orgs = make_orgnrs(5)
    settings = load_settings(output_dir=tmp_path / "out", workers=3)
    orch = await cli.run_job(settings, orgs, transport=FakeBrreg().transport,
                             enrich=mock_enrich(tmp_path / "snap"))
    out = tmp_path / "out"

    for name in ("dossiers.jsonl", "rejections.jsonl", "run_report.json"):
        assert (out / name).is_file(), name
    assert (out / "checkpoints" / "latest.json").is_file()

    dossiers = read_jsonl(out / "dossiers.jsonl")
    assert sorted(d["orgnr"] for d in dossiers) == sorted(orgs)
    assert all(d["processing_status"] == "published" and d["verified_fact_count"] == 1 for d in dossiers)
    assert {r["reason_code"] for r in read_jsonl(out / "rejections.jsonl")} == {"quote_not_found"}

    report = json.loads((out / "run_report.json").read_text())
    assert report["outcomes"] == {"published": 5}
    assert report["requests"]["total"] == orch.ledger.total
    assert report["stop_reason"] == "completed"


def test_mongo_store_mode_stops_the_command_before_any_work(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("STORE_MODE", "mongo")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    numbers = tmp_path / "companies.txt"
    numbers.write_text("\n".join(make_orgnrs(2)))

    assert cli.main(["run", "--input", str(numbers)]) == 2
    assert "Full mode is not built" in capsys.readouterr().err
    assert not (tmp_path / "out" / "dossiers.jsonl").exists()
