import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import Request

from agent_engine.config import load_settings
from agent_engine.errors import ConfigError
from agent_engine.orchestrator import Orchestrator
from agent_engine.registry_client import REGISTRY_TIMEOUT_S, RegistryClient
from agent_engine.report import COST_LIMIT_USD, DAILY_TIME_LIMIT_MIN, code_version
from api.problems import ProblemError
from governor.budget_ledger import BudgetLedger
from governor.rate_limiter import SlidingWindowLimiter
from governor.time_kill_switch import TimeKillSwitch
from storage.store import StoreError, open_store

log = logging.getLogger("signalpost.api")

MAX_REQUESTS = 2000
IDEMPOTENCY_HOURS = 24


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class JobRecord:
    job_id: UUID
    orgnrs: list[str]
    mode: str
    label: str | None
    idempotency_key: str | None
    request_hash: str
    submitted_at: datetime
    rejected_count: int
    response: dict  # the body of the original 202
    orchestrator: Orchestrator | None = None
    report: dict | None = None
    error: str | None = None
    finished: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def status(self) -> str:
        if self.error:
            return "failed"
        return self.orchestrator.status if self.orchestrator else "queued"


class AppState:
    def __init__(self, settings=None, *, transport=None, enrich=None, heartbeat_s=15.0, poll_s=0.25):
        self.settings = settings
        self.config_error: str | None = None
        if settings is None:
            try:
                self.settings = load_settings()
            except ConfigError as exc:
                self.config_error = str(exc)
        self.transport = transport
        self.enrich = enrich
        self.heartbeat_s = heartbeat_s
        self.poll_s = poll_s
        self.version = code_version()
        self.jobs: dict[str, JobRecord] = {}
        self.keys: dict[str, JobRecord] = {}
        self._store = None
        self._queue: asyncio.Queue | None = None
        self._runner: asyncio.Task | None = None

    def require_settings(self):
        if self.settings is None:
            raise ProblemError(503, "service-unavailable", "Service unavailable",
                               "The configuration is invalid. See /api/health for the details.")
        return self.settings

    def output_dir(self) -> Path:
        return Path(self.require_settings().output_dir)

    def store(self):
        # One store for every job: it keeps the in-memory index that protects dossiers.jsonl.
        if self._store is None:
            settings = self.require_settings()
            try:
                self._store = open_store(settings.store_mode, settings.output_dir)
            except (ConfigError, StoreError, OSError) as exc:
                raise ProblemError(503, "service-unavailable", "Service unavailable",
                                   f"The store cannot be opened: {exc}") from None
        return self._store

    def submit(self, record: JobRecord) -> None:
        self.jobs[str(record.job_id)] = record
        if record.idempotency_key:
            self.keys[record.idempotency_key] = record
        if self._queue is None:
            self._queue = asyncio.Queue()
        if self._runner is None or self._runner.done():
            self._runner = asyncio.create_task(self._work())
        self._queue.put_nowait(record)

    async def _work(self) -> None:
        # Jobs run one at a time: they share output/ and the 8 workers.
        while True:
            record = await self._queue.get()
            try:
                await self._run(record)
            except Exception as exc:
                log.exception("job failed", extra={"fields": {"job_id": str(record.job_id)}})
                record.error = type(exc).__name__
                if record.orchestrator:
                    record.orchestrator.emit("error", error=record.error)
            finally:
                record.finished.set()

    async def _run(self, record: JobRecord) -> None:
        settings = self.settings
        ledger = BudgetLedger(
            soft_cap=settings.soft_cap_requests,
            brake=settings.brake_requests,
            per_company_cap=settings.per_company_cap,
            limiter=SlidingWindowLimiter(settings.llm_rpm),
        )
        hooks = {"enrich": self.enrich} if self.enrich else {}
        async with httpx.AsyncClient(transport=self.transport, timeout=REGISTRY_TIMEOUT_S) as http:
            orchestrator = Orchestrator(settings, RegistryClient(http, ledger), ledger, TimeKillSwitch(),
                                        job_id=record.job_id, store=self.store(), job_mode=record.mode, **hooks)
            record.orchestrator = orchestrator
            await orchestrator.run(record.orgnrs)
            report_path = Path(settings.output_dir) / "run_report.json"
            record.report = json.loads(report_path.read_text(encoding="utf-8"))

    async def stop(self) -> None:
        if self._runner:
            self._runner.cancel()
            await asyncio.gather(self._runner, return_exceptions=True)

    def latest_job(self) -> JobRecord | None:
        started = [record for record in self.jobs.values() if record.orchestrator]
        return max(started, key=lambda record: record.submitted_at, default=None)

    def budget(self, record: JobRecord | None) -> dict:
        settings = self.require_settings()
        orchestrator = record.orchestrator if record else None
        ledger = orchestrator.ledger if orchestrator else BudgetLedger(
            soft_cap=settings.soft_cap_requests, brake=settings.brake_requests,
            per_company_cap=settings.per_company_cap)
        snapshot = ledger.snapshot()
        total = snapshot["total_outbound_requests"]

        elapsed, projected = 0, None
        if orchestrator and orchestrator.started_at:
            end = orchestrator.ended_at or datetime.now(timezone.utc)
            elapsed = int((end - orchestrator.started_at).total_seconds())
            if not orchestrator.ended_at:
                projected = orchestrator.kill.projected_minutes()
        return {
            "job_id": str(record.job_id) if record else None,
            "total_outbound_requests": total,
            "requests_by_kind": snapshot["requests_by_kind"],
            "max_requests": MAX_REQUESTS,
            "soft_cap": ledger.soft_cap,
            "brake": ledger.brake_limit,
            "remaining_to_soft_cap": max(0, ledger.soft_cap - total),
            "remaining_to_brake": max(0, ledger.brake_limit - total),
            "per_company_cap": ledger.per_company_cap,
            "soft_cap_reached": snapshot["soft_cap_reached"],
            "brake_tripped": snapshot["brake_tripped"],
            "kill_switch_tripped": snapshot["kill_switch_tripped"],
            "plan_b_used_count": snapshot["requests_by_kind"].get("plan_b", 0),
            "llm_calls": snapshot["llm_calls"],
            "llm_calls_last_minute": ledger.limiter.used(),
            "llm_rpm": settings.llm_rpm,
            "input_tokens": snapshot["input_tokens"],
            "output_tokens": snapshot["output_tokens"],
            "tokens_estimated": False,
            "estimated_cost_usd": float(snapshot["estimated_cost_usd"]),
            "cost_limit_usd": float(COST_LIMIT_USD),
            "max_elapsed_minutes": DAILY_TIME_LIMIT_MIN,
            "elapsed_seconds": elapsed,
            "projected_minutes": round(projected, 1) if projected is not None else None,
        }


def get_state(request: Request) -> AppState:
    return request.app.state.signalpost


def find_job(state: AppState, job_id: str) -> JobRecord:
    try:
        key = str(UUID(job_id))
    except ValueError:
        key = job_id
    record = state.jobs.get(key)
    if record is None:
        raise ProblemError(404, "not-found", "Job not found", f"There is no job with id {job_id[:64]}.")
    return record
