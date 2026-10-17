import asyncio
import hashlib
import json
import re
import threading
import time
from collections import deque
from contextlib import ExitStack
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from agent_engine.config import load_settings
from agent_engine.orchestrator import EnrichResult
from api.main import create_app
from tests.helpers import FakeBrreg, make_orgnrs
from tests.helpers_run import PAGE, mock_enrich


def make_settings(tmp_path, **overrides):
    values = {"output_dir": tmp_path / "out", "data_dir": tmp_path / "data", "workers": 2,
              "llm_base_url": None, "llm_model": None, "llm_api_key": None}
    return load_settings(**{**values, **overrides})


@pytest.fixture
def build(tmp_path):
    stack = ExitStack()

    def make(enrich=None, settings=None, **options):
        brreg = FakeBrreg()
        app = create_app(settings or make_settings(tmp_path), transport=brreg.transport, enrich=enrich,
                         poll_s=0.01, **options)
        client = stack.enter_context(TestClient(app))
        client.brreg = brreg
        return client

    yield make
    stack.close()


@pytest.fixture
def api(build):
    return build()


@pytest.fixture
def api_with_facts(build, tmp_path):
    return build(enrich=mock_enrich(tmp_path / "data" / "snapshots"))


def assert_problem(response, status, path=None):
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert isinstance(body, dict)
    assert body["status"] == status
    assert body["type"].startswith("https://signalpost.local/problems/")
    assert body["title"] and body["detail"]
    if path:
        assert body["instance"] == path
    return body


def break_checksum(orgnr):
    return orgnr[:-1] + str((int(orgnr[-1]) + 1) % 10)


def finish(client, job_id, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}/report")
        if response.status_code == 200:
            return response.json()
        assert response.status_code == 409, response.text
        time.sleep(0.02)
    raise AssertionError("the job did not finish")


def run_job(client, count=3, **extra):
    orgnrs = make_orgnrs(count)
    response = client.post("/api/jobs", json={"orgnrs": orgnrs, **extra})
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    finish(client, job_id)
    return job_id, orgnrs


def parse_sse(text):
    events = []
    for block in text.split("\n\n"):
        lines = [line for line in block.split("\n") if line and not line.startswith(":")]
        if lines:
            fields = dict(line.split(": ", 1) for line in lines)
            events.append({"id": int(fields["id"]), "type": fields["event"], "data": json.loads(fields["data"])})
    return events


def read_until_disconnect(app, path, stop):
    """Call the ASGI app directly and hang up as soon as stop(body) is true, like a closed browser tab."""

    async def drive():
        hang_up = asyncio.Event()
        asked = False
        chunks = []

        async def receive():
            nonlocal asked
            if not asked:
                asked = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await hang_up.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            if message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
                if stop(b"".join(chunks)):
                    hang_up.set()

        scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1",
                 "method": "GET", "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
                 "scheme": "http", "headers": [(b"host", b"testserver")], "client": ("127.0.0.1", 50000),
                 "server": ("testserver", 80), "state": {}}
        await app(scope, receive, send)
        return b"".join(chunks).decode()

    return asyncio.run(drive())


def hold_pass_two():
    gate = threading.Event()

    async def enrich(company, ledger):
        while not gate.is_set():
            await asyncio.sleep(0.01)
        return EnrichResult()

    return gate, enrich


def wait_for_status(client, job_id, status, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if client.get(f"/api/jobs/{job_id}").json()["status"] == status:
            return
        time.sleep(0.02)
    raise AssertionError(f"the job never reached {status}")


def walk(client, url, **params):
    items, cursor = [], None
    for _ in range(20):
        query = {**params, "limit": 2, **({"cursor": cursor} if cursor else {})}
        body = client.get(url, params=query).json()
        items += body["items"]
        cursor = body["next_cursor"]
        if not cursor:
            return items
    raise AssertionError("the cursor never ended")


# E1

def test_validate_lists_accepted_and_rejected_lines(api):
    good = make_orgnrs(2)
    text = "\n".join([good[0], break_checksum(good[1]), "12345", good[0]])
    response = api.post("/api/inputs/validate", json={"text": text, "source_label": "pasted"})

    assert response.status_code == 200
    assert response.json() == {
        "accepted": [good[0]],
        "rejected": [{"line": 2, "value": break_checksum(good[1]), "reason": "mod11_checksum_failed"},
                     {"line": 3, "value": "12345", "reason": "length_not_9"}],
        "duplicates_removed": 1,
    }


def test_validate_422_is_problem_json_with_rejected_as_an_extension(api):
    bad = break_checksum(make_orgnrs(1)[0])
    response = api.post("/api/inputs/validate", json={"text": f"{bad}\n12345\n92345678A"})

    body = assert_problem(response, 422, "/api/inputs/validate")
    assert body["type"] == "https://signalpost.local/problems/validation-error"
    assert body["detail"] == "3 of 3 inputs were rejected. No valid organisation numbers remain."
    assert body["rejected"] == [{"line": 1, "value": bad, "reason": "mod11_checksum_failed"},
                                {"line": 2, "value": "12345", "reason": "length_not_9"},
                                {"line": 3, "value": "92345678A", "reason": "non_digit"}]


def test_validate_has_no_side_effects(api, tmp_path):
    api.post("/api/inputs/validate", json={"text": "\n".join(make_orgnrs(3))})
    api.post("/api/inputs/validate", json={"text": "12345"})

    assert api.brreg.calls == []
    assert not (tmp_path / "out" / "dossiers.jsonl").exists()
    assert api.get("/api/budget").json()["job_id"] is None


def test_validate_input_limits_and_malformed_bodies(api):
    url = "/api/inputs/validate"
    assert_problem(api.post(url, json={"text": "1" * 1_000_001}), 413)
    assert_problem(api.post(url, json={"text": "\n".join(["1"] * 10_001)}), 413)
    assert_problem(api.post(url, content=b" " * 2_000_001, headers={"content-type": "application/json"}), 413)
    assert_problem(api.post(url, content=b"{not json", headers={"content-type": "application/json"}), 400)
    assert_problem(api.post(url, json=["923456783"]), 400)
    assert_problem(api.post(url, json={"text": 5}), 400)
    assert_problem(api.post(url, json={}), 400)
    assert_problem(api.post(url, json={"text": ""}), 422)


# E2, E3, E10

def test_a_job_is_accepted_with_202_and_runs_to_the_end(api):
    orgnrs = make_orgnrs(3)
    bad = break_checksum(orgnrs[0])
    response = api.post("/api/jobs", json={"orgnrs": [*orgnrs, bad], "label": "daily-test"})

    assert response.status_code == 202
    body = response.json()
    assert response.headers["location"] == f"/api/jobs/{body['job_id']}"
    assert body["status"] == "queued"
    assert body["accepted_count"] == 3
    assert body["rejected"] == [{"line": 4, "value": bad, "reason": "mod11_checksum_failed"}]
    assert body["limits"] == {"max_requests": 2000, "soft_cap": 1700, "brake": 1950,
                              "max_cost_usd": 10, "max_elapsed_minutes": 45}
    assert body["events_url"] == f"/api/jobs/{body['job_id']}/events"

    report = finish(api, body["job_id"])
    job = api.get(f"/api/jobs/{body['job_id']}").json()
    assert job["status"] == "completed" and job["stop_reason"] == "completed" and job["current_pass"] == 2
    assert job["label"] == "daily-test"
    assert (job["input_count"], job["rejected_input_count"]) == (3, 1)
    assert job["outcomes"] == {"registry_only": 3}
    assert (job["completed_count"], job["registry_only_count"], job["failed_count"]) == (0, 3, 0)
    assert job["submitted_at"].endswith("Z") and job["started_at"].endswith("Z") and job["ended_at"].endswith("Z")
    assert job["budget"]["total_outbound_requests"] == report["requests"]["total"] > 0
    assert report["job_id"] == body["job_id"]


def test_the_report_is_409_while_the_job_runs(build):
    gate, enrich = hold_pass_two()
    client = build(enrich=enrich)
    try:
        job_id = client.post("/api/jobs", json={"orgnrs": make_orgnrs(2)}).json()["job_id"]
        wait_for_status(client, job_id, "pass2_running")
        assert_problem(client.get(f"/api/jobs/{job_id}/report"), 409, f"/api/jobs/{job_id}/report")
        assert client.get(f"/api/jobs/{job_id}").json()["ended_at"] is None
    finally:
        gate.set()
    assert finish(client, job_id)["stop_reason"] == "completed"


def test_unknown_jobs_are_404(api):
    for suffix in ("", "/events", "/report"):
        for job_id in (str(uuid4()), "not-a-uuid"):
            assert_problem(api.get(f"/api/jobs/{job_id}{suffix}"), 404)
    assert_problem(api.get("/api/budget", params={"job_id": str(uuid4())}), 404)


def test_job_requests_that_are_not_valid(api):
    url = "/api/jobs"
    body = assert_problem(api.post(url, json={"orgnrs": ["12345", "92345678A"]}), 422, url)
    assert [item["reason"] for item in body["rejected"]] == ["length_not_9", "non_digit"]
    assert_problem(api.post(url, json={"orgnrs": []}), 422)
    assert_problem(api.post(url, json={"orgnrs": "923456783"}), 400)
    assert_problem(api.post(url, json={"orgnrs": [923456783]}), 400)
    assert_problem(api.post(url, json={"orgnrs": ["1"] * 10_001}), 413)
    assert_problem(api.post(url, json={"orgnrs": make_orgnrs(1), "mode": "baseline_batch"}), 400)
    assert_problem(api.post(url, json={"orgnrs": make_orgnrs(1), "label": "x" * 129}), 400)
    assert_problem(api.post(url, json={"orgnrs": make_orgnrs(1)}, headers={"Idempotency-Key": "k" * 129}), 400)
    assert api.get("/api/budget").json()["job_id"] is None  # no job was created


def test_idempotency_key_replays_or_conflicts(api):
    orgnrs = make_orgnrs(2)
    headers = {"Idempotency-Key": "daily-2026-10-16-a"}
    first = api.post("/api/jobs", json={"orgnrs": orgnrs}, headers=headers)
    again = api.post("/api/jobs", json={"orgnrs": orgnrs}, headers=headers)

    assert first.status_code == 202 and "replayed" not in first.json()
    assert again.status_code == 200
    assert again.json()["replayed"] is True and again.json()["job_id"] == first.json()["job_id"]
    assert_problem(api.post("/api/jobs", json={"orgnrs": make_orgnrs(3)}, headers=headers), 409)

    other = api.post("/api/jobs", json={"orgnrs": orgnrs})  # no key: a new job
    assert other.status_code == 202 and other.json()["job_id"] != first.json()["job_id"]


def test_multipart_upload_and_its_limits(api):
    orgnrs = make_orgnrs(3)
    text = "\n".join(orgnrs)
    ok = api.post("/api/jobs", files={"file": ("numbers.txt", text, "text/plain")}, data={"label": "upload"})
    assert ok.status_code == 202 and ok.json()["accepted_count"] == 3
    csv = api.post("/api/jobs", files={"file": ("numbers.csv", text.replace("\n", ","), "text/csv")})
    assert csv.status_code == 202 and csv.json()["accepted_count"] == 3

    assert_problem(api.post("/api/jobs", files={"file": ("photo.png", b"1", "image/png")}), 400)
    assert_problem(api.post("/api/jobs", files={"other": ("numbers.txt", text, "text/plain")}), 400)
    assert_problem(api.post("/api/jobs", files={"file": ("numbers.txt", b"1" * 1_000_001, "text/plain")}), 413)
    assert_problem(api.post("/api/jobs", files={"file": ("numbers.txt", b"1" * 1_200_000, "text/plain")}), 413)
    assert_problem(api.post("/api/jobs", files={"file": ("numbers.txt", b"\xff\xfe", "text/plain")}), 400)
    body = assert_problem(api.post("/api/jobs", files={"file": ("numbers.txt", "12345\n92345678A", "text/plain")}), 422)
    assert len(body["rejected"]) == 2


# E4

def test_events_are_a_numbered_server_sent_stream(api):
    job_id, _ = run_job(api, 3)
    response = api.get(f"/api/jobs/{job_id}/events")
    events = parse_sse(response.text)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert [e["id"] for e in events] == list(range(1, len(events) + 1))
    assert events[0]["type"] == "job.started" and events[-1]["type"] == "job.finished"
    assert {e["data"]["job_id"] for e in events} == {job_id}
    assert all(e["data"]["ts"].endswith("Z") and e["data"]["message"] for e in events)
    finished = [e for e in events if e["type"] == "company.finished"]
    assert len(finished) == 3 and all(e["data"]["orgnr"] for e in finished)


def test_events_resume_after_a_forced_disconnect_without_gaps(api):
    job_id, _ = run_job(api, 3)
    path = f"/api/jobs/{job_id}/events"
    all_ids = [e["id"] for e in parse_sse(api.get(path).text)]
    assert len(all_ids) > 6

    cut_off = read_until_disconnect(api.app, path, stop=lambda body: len(re.findall(rb"(?m)^id: ", body)) >= 4)
    seen = [e["id"] for e in parse_sse(cut_off)]
    assert 0 < len(seen) < len(all_ids)
    assert seen == all_ids[:len(seen)]

    resumed = [e["id"] for e in parse_sse(api.get(path, headers={"Last-Event-ID": str(seen[-1])}).text)]
    assert seen + resumed == all_ids
    assert api.get(path, headers={"Last-Event-ID": str(all_ids[-1])}).text == ""
    assert_problem(api.get(path, headers={"Last-Event-ID": "abc"}), 400)


def test_events_the_ring_buffer_dropped_are_replayed_from_the_file(api):
    job_id, _ = run_job(api, 3)
    path = f"/api/jobs/{job_id}/events"
    all_ids = [e["id"] for e in parse_sse(api.get(path).text)]

    orchestrator = api.app.state.signalpost.jobs[job_id].orchestrator
    orchestrator.events = deque(list(orchestrator.events)[-3:], maxlen=3)

    assert [e["id"] for e in parse_sse(api.get(path).text)] == all_ids
    assert [e["id"] for e in parse_sse(api.get(path, headers={"Last-Event-ID": "5"}).text)] == all_ids[5:]


def test_a_quiet_stream_sends_a_heartbeat(build):
    gate, enrich = hold_pass_two()
    client = build(enrich=enrich, heartbeat_s=0.1)
    try:
        job_id = client.post("/api/jobs", json={"orgnrs": make_orgnrs(2)}).json()["job_id"]
        wait_for_status(client, job_id, "pass2_running")
        body = read_until_disconnect(client.app, f"/api/jobs/{job_id}/events", stop=lambda body: b": heartbeat" in body)
        assert body.rstrip().endswith(": heartbeat")
        assert "job.status" in body
    finally:
        gate.set()
    finish(client, job_id)


# E5, E6, E7

def test_dossier_list_filters_sorts_and_pages_with_a_cursor(api_with_facts):
    job_id, orgnrs = run_job(api_with_facts, 5)
    url = "/api/dossiers"

    everything = api_with_facts.get(url, params={"limit": 200}).json()
    assert everything["next_cursor"] is None and len(everything["items"]) == 5
    item = everything["items"][0]
    assert set(item) >= {"orgnr", "legal_name", "org_form", "registry_status", "processing_status",
                         "verified_fact_count", "financials_available", "data_freshness"}
    assert item["processing_status"] == "published" and item["verified_fact_count"] == 1
    assert isinstance(item["financials_available"], bool)
    datetime.fromisoformat(item["data_freshness"])

    ascending = [d["orgnr"] for d in walk(api_with_facts, url, sort="orgnr", order="asc")]
    assert ascending == sorted(orgnrs)
    assert [d["orgnr"] for d in walk(api_with_facts, url, sort="orgnr", order="desc")] == sorted(orgnrs, reverse=True)
    for sort in ("name", "facts", "updated_at"):
        assert sorted(d["orgnr"] for d in walk(api_with_facts, url, sort=sort)) == sorted(orgnrs)

    assert len(walk(api_with_facts, url, status="published")) == 5
    assert walk(api_with_facts, url, status="failed") == []
    assert len(walk(api_with_facts, url, q="eksempel")) == 5
    assert [d["orgnr"] for d in walk(api_with_facts, url, q=orgnrs[0])] == [orgnrs[0]]
    assert walk(api_with_facts, url, q="zzz") == []


def test_dossier_list_rejects_bad_queries(api_with_facts):
    run_job(api_with_facts, 3)
    url = "/api/dossiers"
    cursor = api_with_facts.get(url, params={"limit": 1, "sort": "orgnr"}).json()["next_cursor"]
    assert cursor

    for params in ({"limit": 201}, {"limit": 0}, {"sort": "colour"}, {"order": "sideways"},
                   {"status": "nonsense"}, {"cursor": "garbage"}, {"cursor": cursor, "sort": "name"}):
        assert_problem(api_with_facts.get(url, params=params), 400, url)


def test_dossier_detail_has_both_dates_on_every_fact(api_with_facts):
    _, orgnrs = run_job(api_with_facts, 2)
    response = api_with_facts.get(f"/api/dossiers/{orgnrs[0]}")

    assert response.status_code == 200
    body = response.json()
    assert body["orgnr"] == orgnrs[0] and body["processing_status"] == "published"
    assert body["data_freshness"]
    assert len(body["facts"]) == 1
    fact = body["facts"][0]
    assert fact["as_of"] and fact["retrieved_at"] and fact["sha256"] and fact["quote"]
    assert fact["evidence_url"] == f"/api/dossiers/{orgnrs[0]}/facts/{fact['fact_id']}/evidence"
    assert [fact["fact_id"]] == body["published_fact_ids"]


def test_dossier_detail_errors(api_with_facts):
    run_job(api_with_facts, 1)
    unknown = make_orgnrs(1, start=90000)[0]
    assert_problem(api_with_facts.get(f"/api/dossiers/{unknown}"), 404)
    body = assert_problem(api_with_facts.get("/api/dossiers/12345"), 422, "/api/dossiers/12345")
    assert body["rejected"] == [{"line": 1, "value": "12345", "reason": "length_not_9"}]
    bad = break_checksum(unknown)
    assert assert_problem(api_with_facts.get(f"/api/dossiers/{bad}"), 422)["rejected"][0]["reason"] == "mod11_checksum_failed"


def test_evidence_has_the_quote_the_page_and_matching_hashes(api_with_facts):
    _, orgnrs = run_job(api_with_facts, 2)
    fact = api_with_facts.get(f"/api/dossiers/{orgnrs[0]}").json()["facts"][0]
    response = api_with_facts.get(fact["evidence_url"])

    assert response.status_code == 200
    body = response.json()
    snapshot = body["snapshot"]
    assert body["quote"] == fact["quote"] == "radgivning til norske bedrifter"
    assert snapshot["text"] == PAGE
    assert (snapshot["highlight"]["start"], snapshot["highlight"]["end"]) == (PAGE.find(fact["quote"]), PAGE.find(fact["quote"]) + len(fact["quote"]))
    assert snapshot["text"][snapshot["highlight"]["start"]:snapshot["highlight"]["end"]] == fact["quote"]
    assert snapshot["offset_unit"] == "unicode_code_points"
    assert body["sha256"] == snapshot["sha256"] == hashlib.sha256(snapshot["text"].encode()).hexdigest()
    assert body["final_url"] == body["source_url"] == "https://example.no/"
    assert body["retrieved_at"] == fact["retrieved_at"]
    assert body["source"]["sha256"] == body["sha256"]
    assert set(body["confidence"]) == {"confidence", "identity_score", "q", "v", "g", "s", "f"}
    assert body["validation"]["validation_id"] == fact["validation_id"]


def test_evidence_404s(api_with_facts):
    _, orgnrs = run_job(api_with_facts, 2)
    first = api_with_facts.get(f"/api/dossiers/{orgnrs[0]}").json()["facts"][0]
    second = api_with_facts.get(f"/api/dossiers/{orgnrs[1]}").json()["facts"][0]

    for orgnr, fact_id in ((orgnrs[0], str(uuid4())), (orgnrs[0], "not-a-uuid"),
                           (orgnrs[0], second["fact_id"]), ("12345", first["fact_id"]),
                           (make_orgnrs(1, start=90000)[0], first["fact_id"])):
        assert_problem(api_with_facts.get(f"/api/dossiers/{orgnr}/facts/{fact_id}/evidence"), 404)


# E8, E9

def test_rejection_log_filters_and_pages(api_with_facts):
    job_id, orgnrs = run_job(api_with_facts, 5)
    url = "/api/rejections"

    items = walk(api_with_facts, url)
    assert len(items) == 5 and len({r["rejection_id"] for r in items}) == 5
    assert set(items[0]) >= {"orgnr", "source_url", "rejected_value", "validation_stage", "reason_code",
                             "diagnostic", "rejected_at", "job_id"}
    assert {r["reason_code"] for r in items} == {"quote_not_found"}

    only = api_with_facts.get(url, params={"orgnr": orgnrs[2]}).json()["items"]
    assert [r["orgnr"] for r in only] == [orgnrs[2]]
    assert len(api_with_facts.get(url, params={"job_id": job_id, "stage": "quote"}).json()["items"]) == 5
    assert api_with_facts.get(url, params={"stage": "schema"}).json()["items"] == []
    assert api_with_facts.get(url, params={"reason": "identity_failed"}).json()["items"] == []
    assert api_with_facts.get(url, params={"job_id": str(uuid4())}).json()["items"] == []

    for params in ({"stage": "nonsense"}, {"reason": "nonsense"}, {"job_id": "x"}, {"orgnr": "12"},
                   {"limit": 500}, {"cursor": "garbage"}):
        assert_problem(api_with_facts.get(url, params=params), 400, url)


def test_change_feed_is_empty_and_checks_its_filters(api):
    response = api.get("/api/changes", params={"since": "2026-10-16", "orgnr": make_orgnrs(1)[0], "field": "name"})
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}
    assert api.get("/api/changes", params={"since": "2026-10-16T08:30:00Z"}).status_code == 200
    assert_problem(api.get("/api/changes", params={"since": "yesterday"}), 400)
    assert_problem(api.get("/api/changes", params={"orgnr": "abc"}), 400)


# E11, E12

def test_budget_numbers_equal_the_ledger(api_with_facts):
    empty = api_with_facts.get("/api/budget").json()
    assert empty["job_id"] is None and empty["total_outbound_requests"] == 0
    assert (empty["soft_cap"], empty["brake"], empty["max_requests"]) == (1700, 1950, 2000)

    job_id, _ = run_job(api_with_facts, 5)
    ledger = api_with_facts.app.state.signalpost.jobs[job_id].orchestrator.ledger
    snapshot = ledger.snapshot()
    body = api_with_facts.get("/api/budget").json()

    assert body["job_id"] == job_id
    assert body["total_outbound_requests"] == snapshot["total_outbound_requests"] == ledger.total > 0
    assert body["requests_by_kind"] == snapshot["requests_by_kind"]
    assert body["llm_calls"] == snapshot["llm_calls"] == 5
    assert body["llm_calls_last_minute"] == ledger.limiter.used() == 5
    assert (body["input_tokens"], body["output_tokens"]) == (6000, 750)
    assert body["estimated_cost_usd"] == float(snapshot["estimated_cost_usd"]) == 0.0105
    assert body["remaining_to_brake"] == 1950 - ledger.total
    assert body["remaining_to_soft_cap"] == 1700 - ledger.total
    assert (body["soft_cap_reached"], body["brake_tripped"], body["kill_switch_tripped"]) == (False, False, False)
    assert api_with_facts.get("/api/budget", params={"job_id": job_id}).json() == body
    assert finish(api_with_facts, job_id)["requests"]["total"] == body["total_outbound_requests"]


def test_budget_follows_a_running_job(build):
    gate, enrich = hold_pass_two()
    client = build(enrich=enrich)
    try:
        job_id = client.post("/api/jobs", json={"orgnrs": make_orgnrs(2)}).json()["job_id"]
        wait_for_status(client, job_id, "pass2_running")
        ledger = client.app.state.signalpost.jobs[job_id].orchestrator.ledger
        body = client.get("/api/budget").json()
        assert body["job_id"] == job_id
        assert body["total_outbound_requests"] == ledger.total > 0
        assert body["projected_minutes"] is None
    finally:
        gate.set()
    finish(client, job_id)


def test_health_has_mode_version_and_config_result(api):
    response = api.get("/api/health")
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "ok" and body["mode"] == "lite" and body["version"]
    assert body["config"] == {"valid": True, "errors": []}
    assert body["dependencies"]["store"] == {"mode": "jsonl", "ready": True}
    assert body["dependencies"]["llm"] == {"configured": False, "LLM_BASE_URL": "missing",
                                           "LLM_MODEL": "missing", "LLM_API_KEY": "missing"}


def test_health_shows_names_and_presence_never_values(build, tmp_path):
    secrets = {"llm_api_key": "sk-test-very-secret-value", "llm_base_url": "https://llm.private.example/v1",
               "llm_model": "private-model-name"}
    client = build(settings=make_settings(tmp_path, **secrets))
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["dependencies"]["llm"] == {"configured": True, "LLM_BASE_URL": "set",
                                                      "LLM_MODEL": "set", "LLM_API_KEY": "set"}
    for value in secrets.values():
        assert value not in response.text


def test_health_is_503_and_names_the_bad_setting_when_the_config_is_invalid(monkeypatch):
    monkeypatch.setenv("SOFT_CAP_REQUESTS", "1990")
    monkeypatch.setenv("BRAKE_REQUESTS", "1950")
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "error" and body["config"]["valid"] is False
        assert any("SOFT_CAP_REQUESTS" in line for line in body["config"]["errors"])
        assert_problem(client.post("/api/jobs", json={"orgnrs": make_orgnrs(1)}), 503)
        assert_problem(client.get("/api/dossiers"), 503)
        assert client.post("/api/inputs/validate", json={"text": make_orgnrs(1)[0]}).status_code == 200


def test_health_is_503_when_the_store_mode_is_not_built(build, tmp_path):
    client = build(settings=make_settings(tmp_path, store_mode="mongo"))
    response = client.get("/api/health")

    assert response.status_code == 503
    assert "Full mode is not built" in " ".join(response.json()["config"]["errors"])
    assert_problem(client.post("/api/jobs", json={"orgnrs": make_orgnrs(1)}), 503)


# shared behaviour

def test_cors_allows_only_the_dashboard_origin(api):
    allowed = api.options("/api/jobs", headers={"Origin": "http://localhost:3000",
                                               "Access-Control-Request-Method": "POST",
                                               "Access-Control-Request-Headers": "Idempotency-Key"})
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "idempotency-key" in allowed.headers["access-control-allow-headers"].lower()

    other = api.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_unknown_routes_and_methods_use_problem_json_too(api):
    assert_problem(api.get("/api/nothing-here"), 404, "/api/nothing-here")
    assert_problem(api.post("/api/health"), 405)
    assert_problem(api.get("/api/dossiers", params={"limit": "many"}), 400)
