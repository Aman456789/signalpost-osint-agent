import asyncio
import json
import logging
import os
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from agent_engine.errors import BudgetDenied, SourceUnavailable
from agent_engine.profile import build_profile, empty_dossier
from agent_engine.schemas import Dossier, Flag, ProcessingStatus, PublishedFact, count_verified_facts

log = logging.getLogger("signalpost.orchestrator")

RING_SIZE = 1000
TERMINAL = {
    ProcessingStatus.PUBLISHED,
    ProcessingStatus.REGISTRY_ONLY,
    ProcessingStatus.NOT_FOUND,
    ProcessingStatus.REGISTRY_UNAVAILABLE,
    ProcessingStatus.NOT_PROCESSED_BUDGET,
    ProcessingStatus.FAILED,
}


@dataclass
class CompanyRun:
    orgnr: str
    status: ProcessingStatus = ProcessingStatus.PENDING
    flags: list[Flag] = field(default_factory=list)
    dossier: Dossier | None = None
    # Pass 2 appends every AI fact it has fetched here, so the brake can tell the cases apart
    fetched_facts: list = field(default_factory=list)


@dataclass
class EnrichResult:
    facts: list[PublishedFact] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)


async def enrich_company(company: CompanyRun, ledger) -> EnrichResult:
    return EnrichResult()


async def finalize_partial(company: CompanyRun) -> list[PublishedFact]:
    return []


class Orchestrator:
    def __init__(self, settings, registry, ledger, kill_switch, *, job_id: UUID | None = None,
                 enrich=enrich_company, finalize=finalize_partial):
        self.settings = settings
        self.registry = registry
        self.ledger = ledger
        self.kill = kill_switch
        self.job_id = job_id or uuid4()
        self.enrich = enrich
        self.finalize = finalize
        self.companies: dict[str, CompanyRun] = {}
        self.status = "queued"
        self.stop_reason = "none"
        self.sequence = 0
        self.events: deque = deque(maxlen=RING_SIZE)
        self.output_dir = Path(settings.output_dir)
        self.dossier_path = self.output_dir / "dossiers.jsonl"
        self.events_path = self.output_dir / "events.jsonl"
        self.checkpoint_path = self.output_dir / "checkpoints" / "latest.json"
        self._stopped = False
        self._brake_handled = False
        self._pass1_only = False
        self._plan_c_reported = False

    async def run(self, orgnrs: list[str], *, pass1_only: bool = False, resume: bool = False) -> dict:
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self._pass1_only = pass1_only
        done = self._load_checkpoint() if resume else {}
        for orgnr in orgnrs:
            company = CompanyRun(orgnr)
            if orgnr in done:
                company.status = ProcessingStatus(done[orgnr]["status"])
                company.flags = [Flag(flag) for flag in done[orgnr]["flags"]]
            self.companies[orgnr] = company

        self.kill.start()
        self.emit("job.started", companies=len(orgnrs), resumed=len(done), pass1_only=pass1_only)
        self._set_status("pass1_running")
        pending = [c for c in self.companies.values() if c.status == ProcessingStatus.PENDING]
        await self._run_phase(pending, self._pass1)

        if not self._stopped:
            self._set_status("pass1_complete")
            if not pass1_only:
                waiting = [c for c in self.companies.values() if c.status == ProcessingStatus.PASS1_COMPLETE]
                self.kill.begin_phase(len(waiting))
                self._set_status("pass2_running")
                await self._run_phase(waiting, self._pass2)
        self._conclude()
        return self.summary()

    async def _run_phase(self, companies, handler) -> None:
        queue: asyncio.Queue = asyncio.Queue()
        for company in companies:
            queue.put_nowait(company)

        async def worker():
            while not self._stopped:
                try:
                    company = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                state = self.kill.check()
                if state != "ok":
                    await self._time_stop(state)
                    return
                await handler(company)
                if self.ledger.brake.tripped:
                    await self._on_brake()

        await asyncio.gather(*(worker() for _ in range(self.settings.workers)))

    async def _pass1(self, company: CompanyRun) -> None:
        if company.status in TERMINAL:
            return
        company.status = ProcessingStatus.PASS1_RUNNING
        try:
            dossier = await build_profile(company.orgnr, self.registry, self.job_id, self.settings.plan_b_enabled)
        except BudgetDenied as exc:
            if not self.ledger.brake.tripped:
                self._finish_empty(company, ProcessingStatus.FAILED, error=f"budget:{exc.reason}")
            return
        except SourceUnavailable as exc:
            self._finish_empty(company, ProcessingStatus.REGISTRY_UNAVAILABLE, error=str(exc))
            return
        except Exception:
            log.exception("pass 1 failed", extra={"fields": {"orgnr": company.orgnr}})
            self._finish_empty(company, ProcessingStatus.FAILED, error="unexpected")
            return

        if company.status in TERMINAL:  # the brake or a time stop closed it while we waited
            return
        if self.registry.plan_c and not self._plan_c_reported:
            self._plan_c_reported = True
            self.emit("registry.plan_c")
        if dossier is None:
            self._finish_empty(company, ProcessingStatus.NOT_FOUND)
            return
        company.dossier = dossier
        company.status = ProcessingStatus.PASS1_COMPLETE
        self.emit("company.pass1_complete", orgnr=company.orgnr, registry_status=dossier.registry_status)

    async def _pass2(self, company: CompanyRun) -> None:
        if company.status in TERMINAL:
            return
        company.status = ProcessingStatus.PASS2_RUNNING
        try:
            result = await self.enrich(company, self.ledger)
        except BudgetDenied as exc:
            if not self.ledger.brake.tripped:
                log.warning("pass 2 denied", extra={"fields": {"orgnr": company.orgnr, "reason": exc.reason}})
                self._finish(company)
                self.kill.company_finished()
            return
        except Exception:
            log.exception("pass 2 failed", extra={"fields": {"orgnr": company.orgnr}})
            result = EnrichResult()

        if company.status in TERMINAL:
            return
        self._finish(company, result.facts, result.flags)
        self.kill.company_finished()

    async def _on_brake(self) -> None:
        if self._brake_handled:
            return
        self._brake_handled = True
        self._stopped = True
        await self._wind_down(Flag.REQUEST_BRAKE, include_running=True, partial=True)
        self.emit("budget.brake", total=self.ledger.total, limit=self.ledger.brake_limit)
        self.stop_reason = "request_brake"

    async def _time_stop(self, state: str) -> None:
        if self.stop_reason != "none" or self._brake_handled:
            return
        if state == "trip":
            self.ledger.trip_kill_switch()
            self._stopped = True
            self.stop_reason = "kill_switch"
            self.emit("budget.kill_switch", projected_minutes=self.kill.projected_minutes())
            await self._wind_down(Flag.TIME_LIMIT_REGISTRY_ONLY, include_running=False, partial=False)
        else:
            self.ledger.halt()
            self._stopped = True
            self.stop_reason = "time_hard_stop"
            self.emit("time.hard_stop", elapsed_s=self.kill.elapsed_s())
            await self._wind_down(Flag.TIME_LIMIT_REGISTRY_ONLY, include_running=True, partial=False)

    async def _wind_down(self, flag: Flag, *, include_running: bool, partial: bool) -> None:
        for company in list(self.companies.values()):
            if company.status in TERMINAL:
                continue
            if company.dossier is None:
                self._finish_empty(company, ProcessingStatus.NOT_PROCESSED_BUDGET, [Flag.NOT_PROCESSED_BUDGET])
                continue
            running = company.status == ProcessingStatus.PASS2_RUNNING
            if running and not include_running:
                continue
            facts = []
            if partial and running and company.fetched_facts:
                facts = await self.finalize(company)
                if company.status in TERMINAL:
                    continue
            self._finish(company, facts, [flag])

    def _finish(self, company: CompanyRun, facts=(), flags=()) -> None:
        company.status = ProcessingStatus.PUBLISHED if facts else ProcessingStatus.REGISTRY_ONLY
        company.flags = list(dict.fromkeys([*company.flags, *flags]))
        company.dossier = company.dossier.model_copy(update={
            "processing_status": company.status,
            "flags": company.flags,
            "verified_fact_count": count_verified_facts(facts),
            "published_fact_ids": [str(fact.fact_id) for fact in facts],
            "updated_at": datetime.now(timezone.utc),
        })
        self._record(company)

    def _finish_empty(self, company: CompanyRun, status: ProcessingStatus, flags=(), error: str | None = None) -> None:
        company.status = status
        company.flags = list(flags)
        company.dossier = empty_dossier(company.orgnr, status, self.job_id, flags)
        self._record(company, error)

    def _record(self, company: CompanyRun, error: str | None = None) -> None:
        if not self._pass1_only:
            self._append_line(self.dossier_path, company.dossier.model_dump_json(), sync=True)
        self.emit("company.finished", orgnr=company.orgnr, status=company.status.value,
                  flags=[flag.value for flag in company.flags], error=error)
        self._write_checkpoint()

    def _conclude(self) -> None:
        if self.stop_reason == "none":
            self.stop_reason = "completed"
        final = {"request_brake": "stopped_budget", "kill_switch": "stopped_time",
                 "time_hard_stop": "stopped_time"}.get(self.stop_reason, "completed")
        if final == "completed" and self._pass1_only:
            final = "pass1_complete"
        self._set_status(final)
        self.emit("job.finished", stop_reason=self.stop_reason)
        self._write_checkpoint()

    def _set_status(self, status: str) -> None:
        self.status = status
        self.emit("job.status", status=status)

    def summary(self) -> dict:
        outcomes = Counter(company.status.value for company in self.companies.values())
        return {
            "job_id": str(self.job_id),
            "status": self.status,
            "stop_reason": self.stop_reason,
            "outcomes": dict(outcomes),
            "requests": self.ledger.total,
        }

    def emit(self, kind: str, **data) -> None:
        self.sequence += 1
        event = {
            "seq": self.sequence,
            "time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "job_id": str(self.job_id),
            "type": kind,
            "data": data,
        }
        self.events.append(event)
        self._append_line(self.events_path, json.dumps(event, default=str))

    def events_since(self, seq: int) -> list[dict]:
        return [event for event in self.events if event["seq"] > seq]

    def _append_line(self, path: Path, line: str, sync: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            if sync:
                handle.flush()
                os.fsync(handle.fileno())

    def _write_checkpoint(self) -> None:
        state = {
            "job_id": str(self.job_id),
            "status": self.status,
            "stop_reason": self.stop_reason,
            "sequence": self.sequence,
            "ledger": self.ledger.snapshot(),
            "done": {
                company.orgnr: {"status": company.status.value, "flags": [f.value for f in company.flags]}
                for company in self.companies.values()
                if company.status in TERMINAL
            },
        }
        temp = self.checkpoint_path.with_name("latest.json.tmp")
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, self.checkpoint_path)

    def _load_checkpoint(self) -> dict:
        if not self.checkpoint_path.exists():
            return {}
        state = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        self.job_id = UUID(state["job_id"])
        self.sequence = state["sequence"]
        self.ledger.restore(state["ledger"])
        return state["done"]
