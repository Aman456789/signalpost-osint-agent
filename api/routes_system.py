from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api.problems import ProblemError
from api.state import find_job, get_state

router = APIRouter()


@router.get("/budget")
async def get_budget(request: Request, job_id: UUID | None = None):
    state = get_state(request)
    state.require_settings()
    record = find_job(state, str(job_id)) if job_id else state.latest_job()
    return state.budget(record)


@router.get("/health")
async def get_health(request: Request):
    state = get_state(request)
    settings = state.settings
    errors = []
    if state.config_error:
        errors = [line.strip() for line in state.config_error.splitlines()[1:]] or [state.config_error]

    store_ready = False
    if settings:
        try:
            state.store()
            store_ready = True
        except ProblemError as exc:
            errors.append(exc.detail)

    llm = {"configured": False}
    if settings:
        present = {
            "LLM_BASE_URL": bool(settings.llm_base_url),
            "LLM_MODEL": bool(settings.llm_model),
            "LLM_API_KEY": bool(settings.llm_api_key and settings.llm_api_key.get_secret_value()),
        }
        llm = {"configured": all(present.values()),
               **{name: "set" if ok else "missing" for name, ok in present.items()}}

    healthy = not errors
    body = {
        "status": "ok" if healthy else "error",
        "mode": settings.mode if settings else "lite",
        "version": state.version,
        "config": {"valid": healthy, "errors": errors},
        "dependencies": {
            "store": {"mode": settings.store_mode if settings else None, "ready": store_ready},
            "llm": llm,
            "redis": "not_used",
            "mongo": "not_used",
        },
    }
    return JSONResponse(body, status_code=200 if healthy else 503)
