import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from agent_engine.errors import ConfigError
from storage import store as store_module
from storage.store import ChangeRecord, DuplicateRecord, JsonlStore, StoreError, open_store
from tests.helpers import make_fact, make_orgnrs
from tests.helpers_run import (
    Crash, dossier_for, make_rejection, make_source, mock_enrich, read_jsonl, run_job,
)


def complete(store, orgnr, job_id, with_fact=True, with_rejection=True):
    facts = [make_fact(orgnr)] if with_fact else []
    rejections = [make_rejection(orgnr, job_id)] if with_rejection else []
    store.complete_company(dossier_for(orgnr, job_id, facts), facts, rejections, [make_source(orgnr)])


def orgnrs_in(path):
    return sorted(row["orgnr"] for row in read_jsonl(path))


def test_a_completion_unit_writes_every_file_and_the_marker(tmp_path):
    store, job = JsonlStore(tmp_path), uuid4()
    org = make_orgnrs(1)[0]
    complete(store, org, job)
    assert orgnrs_in(store.dossiers_path) == [org]
    assert len(read_jsonl(store.facts_path)) == 1
    assert len(read_jsonl(store.rejections_path)) == 1
    assert len(read_jsonl(store.sources_path)) == 1
    assert store.is_complete(job, org)
    assert store.completed(job)[org].published_fact_ids == [read_jsonl(store.facts_path)[0]["fact_id"]]
    assert store.rejection_counts(job) == {"quote_not_found": 1}


def test_a_company_can_complete_only_once_per_job(tmp_path):
    store, job = JsonlStore(tmp_path), uuid4()
    org = make_orgnrs(1)[0]
    complete(store, org, job)
    with pytest.raises(DuplicateRecord):
        complete(store, org, job)
    assert len(read_jsonl(store.facts_path)) == 1

    complete(store, org, uuid4())  # a later job replaces the dossier, never adds a second one
    assert orgnrs_in(store.dossiers_path) == [org]


def test_the_same_page_is_stored_once(tmp_path):
    store = JsonlStore(tmp_path)
    org = make_orgnrs(1)[0]
    complete(store, org, uuid4())
    complete(store, org, uuid4())
    assert len(read_jsonl(store.sources_path)) == 1


def test_a_unit_that_does_not_add_up_is_refused(tmp_path):
    store, job = JsonlStore(tmp_path), uuid4()
    first, second = make_orgnrs(2)
    fact = make_fact(first)
    with pytest.raises(ValueError):
        store.complete_company(dossier_for(first, job), [fact])  # dossier does not list the fact
    with pytest.raises(ValueError):
        store.complete_company(dossier_for(second, job, [fact]), [fact])  # fact of another company
    assert read_jsonl(store.facts_path) == []


def test_a_crash_before_the_dossier_swap_leaves_the_old_file_whole(tmp_path, monkeypatch):
    store, job = JsonlStore(tmp_path), uuid4()
    first, second = make_orgnrs(2)
    complete(store, first, job)
    before = store.dossiers_path.read_bytes()

    def killed(source, target):
        raise Crash()

    with monkeypatch.context() as patch:
        patch.setattr(store_module.os, "replace", killed)
        with pytest.raises(Crash):
            complete(store, second, job)
    assert store.dossiers_path.read_bytes() == before

    reopened = JsonlStore(tmp_path)  # the half-written company is dropped, the finished one is kept
    assert not reopened.is_complete(job, second)
    assert len(read_jsonl(reopened.facts_path)) == 1
    assert len(read_jsonl(reopened.rejections_path)) == 1
    assert not list(tmp_path.glob("*.tmp"))

    complete(reopened, second, job)
    assert orgnrs_in(reopened.dossiers_path) == sorted([first, second])
    assert len(read_jsonl(reopened.facts_path)) == 2


def test_a_crash_before_the_marker_means_the_company_is_redone(tmp_path, monkeypatch):
    store, job = JsonlStore(tmp_path), uuid4()
    first, second = make_orgnrs(2)
    complete(store, first, job)

    def killed(self, marker):
        raise Crash()

    with monkeypatch.context() as patch:
        patch.setattr(JsonlStore, "_write_marker", killed)
        with pytest.raises(Crash):
            complete(store, second, job)
    assert second in orgnrs_in(store.dossiers_path)  # written, but not marked

    reopened = JsonlStore(tmp_path)
    assert orgnrs_in(reopened.dossiers_path) == [first]
    complete(reopened, second, job)
    assert orgnrs_in(reopened.dossiers_path) == sorted([first, second])
    assert len(read_jsonl(reopened.facts_path)) == 2
    assert len(read_jsonl(reopened.rejections_path)) == 2


def test_a_half_written_last_line_is_dropped_on_startup(tmp_path):
    store, job = JsonlStore(tmp_path), uuid4()
    first, second = make_orgnrs(2)
    complete(store, first, job)
    with open(store.rejections_path, "a") as handle:
        handle.write('{"rejection_id": "half')

    reopened = JsonlStore(tmp_path)
    assert len(read_jsonl(reopened.rejections_path)) == 1
    complete(reopened, second, job)
    assert len(read_jsonl(reopened.rejections_path)) == 2


def test_two_dossiers_for_one_company_stop_the_startup(tmp_path):
    store, job = JsonlStore(tmp_path), uuid4()
    org = make_orgnrs(1)[0]
    complete(store, org, job)
    line = store.dossiers_path.read_text()
    store.dossiers_path.write_text(line + line)
    with pytest.raises(StoreError, match="two dossiers"):
        JsonlStore(tmp_path)


def test_the_change_writer_appends_a_valid_record(tmp_path):
    store = JsonlStore(tmp_path)
    org = make_orgnrs(1)[0]
    store.write_change(ChangeRecord(
        change_id=uuid4(), orgnr=org, job_id=uuid4(), field="website_url", previous_value="a.no",
        new_value="b.no", source_id=uuid4(), detected_at=datetime.now(timezone.utc), kind="modified",
    ))
    assert read_jsonl(store.changes_path)[0]["field"] == "website_url"


def test_mongo_is_rejected_with_a_clear_message(tmp_path):
    with pytest.raises(ConfigError, match="Full mode is not built"):
        open_store("mongo", tmp_path)
    with pytest.raises(ConfigError, match="must be jsonl"):
        open_store("sqlite", tmp_path)
    assert isinstance(open_store("jsonl", tmp_path), JsonlStore)


async def test_resume_does_not_write_a_company_twice(tmp_path):
    orgs = make_orgnrs(6)
    snapshots = tmp_path / "snap"
    good = mock_enrich(snapshots)

    async def crashing(company, ledger):
        if company.orgnr == orgs[3]:
            raise Crash()
        return await good(company, ledger)

    with pytest.raises(Crash):
        await run_job(tmp_path, orgs, enrich=crashing)
    out = tmp_path / "out"
    assert orgnrs_in(out / "dossiers.jsonl") == sorted(orgs[:3])

    orch = await run_job(tmp_path, orgs, enrich=good, resume=True)
    assert orgnrs_in(out / "dossiers.jsonl") == sorted(orgs)
    assert len(read_jsonl(out / "facts.jsonl")) == 6
    assert len(read_jsonl(out / "rejections.jsonl")) == 6
    assert len(read_jsonl(out / "completed.jsonl")) == 6
    assert orch.store.rejection_counts(orch.job_id) == {"quote_not_found": 6}
    assert {run.status.value for run in orch.companies.values()} == {"published"}
    assert json.loads((out / "run_report.json").read_text())["outcomes"] == {"published": 6}
