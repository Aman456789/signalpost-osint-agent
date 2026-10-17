from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import routes_dossiers, routes_inputs, routes_jobs, routes_records, routes_stream, routes_system
from api.problems import add_problem_handlers
from api.state import AppState

DASHBOARD_ORIGIN = "http://localhost:3000"


def create_app(settings=None, *, transport=None, enrich=None, heartbeat_s=15.0, poll_s=0.25) -> FastAPI:
    state = AppState(settings, transport=transport, enrich=enrich, heartbeat_s=heartbeat_s, poll_s=poll_s)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        await state.stop()

    app = FastAPI(title="Signalpost OSINT Agent", lifespan=lifespan)
    app.state.signalpost = state
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[DASHBOARD_ORIGIN],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key", "Last-Event-ID"],
        expose_headers=["Location"],
    )
    add_problem_handlers(app)
    for module in (routes_inputs, routes_jobs, routes_stream, routes_dossiers, routes_records, routes_system):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
