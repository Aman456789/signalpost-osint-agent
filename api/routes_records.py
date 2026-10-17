from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query, Request

from agent_engine.schemas import RejectionReason, ValidationStage
from api import records
from api.request_body import malformed
from api.state import get_state

router = APIRouter()


@router.get("/rejections")
async def list_rejections(
    request: Request,
    job_id: UUID | None = None,
    orgnr: str | None = Query(None, pattern=r"^[0-9]{9}$"),
    stage: ValidationStage | None = None,
    reason: RejectionReason | None = None,
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
):
    items = records.rejections(get_state(request).output_dir())
    if job_id:
        items = [r for r in items if r["job_id"] == str(job_id)]
    if orgnr:
        items = [r for r in items if r["orgnr"] == orgnr]
    if stage:
        items = [r for r in items if r["validation_stage"] == stage]
    if reason:
        items = [r for r in items if r["reason_code"] == reason.value]
    scope = f"rejections:{job_id}:{orgnr}:{stage}:{reason}"
    page, next_cursor = records.paginate(
        items, lambda r: (records.timestamp(r["rejected_at"]), r["rejection_id"]),
        descending=True, limit=limit, cursor=cursor, scope=scope)
    return {"items": page, "next_cursor": next_cursor}


@router.get("/changes")
async def list_changes(
    since: str | None = None,
    orgnr: str | None = Query(None, pattern=r"^[0-9]{9}$"),
    field: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
):
    # Nothing writes change records yet, so the feed is empty. The filters are still checked.
    if since:
        try:
            datetime.fromisoformat(since)
        except ValueError:
            raise malformed("'since' must be an ISO 8601 date or time.") from None
    return {"items": [], "next_cursor": None}
