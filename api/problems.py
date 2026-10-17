from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_BASE = "https://signalpost.local/problems/"


class ProblemError(Exception):
    """Raise this anywhere in a route; the handler turns it into an RFC 9457 response."""

    def __init__(self, status: int, slug: str, title: str, detail: str, **extra):
        super().__init__(detail)
        self.status = status
        self.slug = slug
        self.title = title
        self.detail = detail
        self.extra = extra


def problem_response(request: Request, status: int, slug: str, title: str, detail: str, **extra) -> JSONResponse:
    body = {
        "type": PROBLEM_BASE + slug,
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        **extra,
    }
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def add_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def on_problem(request: Request, exc: ProblemError):
        return problem_response(request, exc.status, exc.slug, exc.title, exc.detail, **exc.extra)

    @app.exception_handler(RequestValidationError)
    async def on_invalid_request(request: Request, exc: RequestValidationError):
        errors = [{"where": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
                  for error in exc.errors()]
        return problem_response(request, 400, "malformed-request", "Malformed request",
                                "The request could not be understood.", errors=errors)

    @app.exception_handler(StarletteHTTPException)
    async def on_http_error(request: Request, exc: StarletteHTTPException):
        return problem_response(request, exc.status_code, "http-error", str(exc.detail), str(exc.detail))
