import asyncio
import json
import time
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from agent_engine.schemas import truncate_message
from api.request_body import malformed
from api.state import JobRecord, find_job, get_state

router = APIRouter()

MESSAGES = {
    "job.started": "Job started",
    "job.status": "Job is now {status}",
    "company.pass1_complete": "Registry profile built",
    "company.finished": "Finished as {status}",
    "registry.plan_c": "Registry outage detected",
    "budget.brake": "Request brake tripped",
    "budget.kill_switch": "Time kill switch tripped",
    "time.hard_stop": "Time limit reached",
    "job.storage_failed": "Storage failed",
    "job.finished": "Job finished ({stop_reason})",
    "error": "The job failed ({error})",
}


def public_event(event: dict) -> dict:
    data = event["data"]
    template = MESSAGES.get(event["type"], event["type"])
    try:
        message = template.format(**data)
    except KeyError:
        message = template
    return {
        "id": event["seq"],
        "ts": event["time"].replace("+00:00", "Z"),
        "job_id": event["job_id"],
        "type": event["type"],
        "orgnr": data.get("orgnr"),
        "message": truncate_message(message),
        "data": data,
    }


def frame(event: dict) -> str:
    return f"id: {event['id']}\nevent: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"


def events_from_file(path: Path, job_id, after: int) -> list[dict]:
    found = []
    if not path.exists():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:  # half-written last line
            continue
        if event["job_id"] == str(job_id) and event["seq"] > after:
            found.append(event)
    return found


def events_after(record: JobRecord, last: int) -> list[dict]:
    orchestrator = record.orchestrator
    if orchestrator is None:
        return []
    ring = orchestrator.events
    first_in_ring = ring[0]["seq"] if ring else orchestrator.sequence + 1
    if first_in_ring > last + 1 and orchestrator.sequence > last:
        # the ring buffer no longer holds what this client missed
        return events_from_file(orchestrator.events_path, record.job_id, last)
    return orchestrator.events_since(last)


async def event_stream(request: Request, record: JobRecord, last: int, heartbeat_s: float, poll_s: float):
    last_sent = time.monotonic()
    while True:
        finished = record.finished.is_set()  # read before the events: nothing is emitted after it is set
        events = events_after(record, last)
        for event in events:
            if await request.is_disconnected():
                return
            last = event["seq"]
            yield frame(public_event(event))
            last_sent = time.monotonic()
        if finished and not events:
            return
        if not events:
            if await request.is_disconnected():
                return
            await asyncio.sleep(poll_s)
            if time.monotonic() - last_sent >= heartbeat_s:
                yield ": heartbeat\n\n"
                last_sent = time.monotonic()


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    state = get_state(request)
    record = find_job(state, job_id)
    header = request.headers.get("last-event-id", "").strip()
    if header and not (header.isascii() and header.isdigit()):
        raise malformed("Last-Event-ID must be a whole number.")
    stream = event_stream(request, record, int(header or 0), state.heartbeat_s, state.poll_s)
    return StreamingResponse(stream, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
