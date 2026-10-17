import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile

from agent_engine.report import COST_LIMIT_USD, DAILY_TIME_LIMIT_MIN
from api.problems import ProblemError
from api.request_body import (
    MAX_LINES, MAX_TEXT_BYTES, json_object, malformed, nothing_valid, parse_numbers, rejected_items, too_large,
)
from api.state import IDEMPOTENCY_HOURS, MAX_REQUESTS, JobRecord, find_job, get_state, iso

router = APIRouter()

MODE = "daily_test"
UPLOAD_OVERHEAD = 64 * 1024  # multipart framing around the file
UPLOAD_TYPES = {"application/csv", "application/vnd.ms-excel", "application/octet-stream"}


async def read_job_request(request: Request):
    content_type = request.headers.get("content-type", "").lower()
    if content_type.startswith("multipart/form-data"):
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > MAX_TEXT_BYTES + UPLOAD_OVERHEAD:
            raise too_large("The upload is larger than 1 MB.")
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise malformed("Send the numbers as a .txt or .csv file in the 'file' field.")
        name = (upload.filename or "").lower()
        mime = (upload.content_type or "").lower()
        if not name.endswith((".txt", ".csv")) or not (mime.startswith("text/") or mime in UPLOAD_TYPES):
            raise malformed("Only .txt and .csv files can be uploaded.")
        result = parse_numbers(await upload.read(MAX_TEXT_BYTES + 1))
        return result, form.get("mode", MODE), form.get("label")

    body = await json_object(request)
    orgnrs = body.get("orgnrs")
    if not isinstance(orgnrs, list) or not all(isinstance(item, str) for item in orgnrs):
        raise malformed("'orgnrs' must be a list of strings.")
    if len(orgnrs) > MAX_LINES:
        raise too_large(f"A job takes at most {MAX_LINES:,} organisation numbers.")
    return parse_numbers("\n".join(orgnrs)), body.get("mode", MODE), body.get("label")


@router.post("/jobs", status_code=202)
async def create_job(request: Request):
    state = get_state(request)
    settings = state.require_settings()
    result, mode, label = await read_job_request(request)

    if mode != MODE:
        raise ProblemError(400, "unsupported-mode", "Unsupported mode",
                           "Only mode daily_test can be started now. Baseline and pilot runs are configured in a later phase.")
    if label is not None and (not isinstance(label, str) or len(label) > 128):
        raise malformed("'label' must be text of at most 128 characters.")
    key = request.headers.get("idempotency-key")
    if key is not None and not 1 <= len(key.strip()) <= 128:
        raise malformed("Idempotency-Key must have 1 to 128 characters.")
    key = key.strip() if key else None
    if not result.accepted:
        raise nothing_valid(result)

    request_hash = hashlib.sha256(
        json.dumps({"orgnrs": result.accepted, "mode": mode, "label": label}, sort_keys=True).encode()
    ).hexdigest()
    earlier = state.keys.get(key) if key else None
    if earlier and datetime.now(timezone.utc) - earlier.submitted_at < timedelta(hours=IDEMPOTENCY_HOURS):
        if earlier.request_hash != request_hash:
            raise ProblemError(409, "idempotency-conflict", "Idempotency conflict",
                               "This Idempotency-Key was already used with a different request.")
        return JSONResponse({**earlier.response, "status": earlier.status, "replayed": True}, status_code=200)

    state.store()  # a store that cannot open is a 503 now, not a failed job later
    job_id = uuid4()
    response = {
        "job_id": str(job_id),
        "status": "queued",
        "accepted_count": len(result.accepted),
        "rejected": rejected_items(result),
        "duplicates_removed": result.duplicates_merged,
        "limits": {
            "max_requests": MAX_REQUESTS,
            "soft_cap": settings.soft_cap_requests,
            "brake": settings.brake_requests,
            "max_cost_usd": int(COST_LIMIT_USD),
            "max_elapsed_minutes": DAILY_TIME_LIMIT_MIN,
        },
        "events_url": f"/api/jobs/{job_id}/events",
    }
    state.submit(JobRecord(
        job_id=job_id, orgnrs=result.accepted, mode=mode, label=label, idempotency_key=key,
        request_hash=request_hash, submitted_at=datetime.now(timezone.utc),
        rejected_count=len(result.rejected), response=response,
    ))
    return JSONResponse(response, status_code=202, headers={"Location": f"/api/jobs/{job_id}"})


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request):
    state = get_state(request)
    record = find_job(state, job_id)
    orchestrator = record.orchestrator
    outcomes = Counter(c.status.value for c in orchestrator.companies.values()) if orchestrator else Counter()
    stop_reason = orchestrator.stop_reason if orchestrator else "none"
    budget = state.budget(record)
    status = record.status
    return {
        "job_id": str(record.job_id),
        "mode": record.mode,
        "label": record.label,
        "status": status,
        "current_pass": {"queued": 0, "pass1_running": 1, "pass1_complete": 1}.get(status, 2),
        "submitted_at": iso(record.submitted_at),
        "started_at": iso(orchestrator.started_at) if orchestrator and orchestrator.started_at else None,
        "ended_at": iso(orchestrator.ended_at) if orchestrator and orchestrator.ended_at else None,
        "input_count": len(record.orgnrs),
        "rejected_input_count": record.rejected_count,
        "completed_count": outcomes["published"],
        "registry_only_count": outcomes["registry_only"],
        "failed_count": outcomes["failed"] + outcomes["registry_unavailable"],
        "outcomes": dict(outcomes),
        "stop_reason": None if stop_reason == "none" else stop_reason,
        "budget": {key: budget[key] for key in (
            "total_outbound_requests", "soft_cap", "brake", "estimated_cost_usd", "llm_calls_last_minute")},
    }


@router.get("/jobs/{job_id}/report")
async def get_report(job_id: str, request: Request):
    record = find_job(get_state(request), job_id)
    if record.report is not None:
        return record.report
    if not record.finished.is_set():
        raise ProblemError(409, "job-not-finished", "Job not finished", "The run report exists once the job has finished.")
    raise ProblemError(404, "not-found", "Report not found", "This job ended without a run report.")
