import fcntl
import json
import os
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import Field

from agent_engine.errors import ConfigError
from agent_engine.schemas import Dossier, Orgnr, PublishedFact, RejectionRecord, Sha256, Strict


class StoreError(Exception):
    pass


class DuplicateRecord(StoreError):
    pass


class SourceRecord(Strict):
    source_id: UUID
    orgnr: Orgnr
    url: str
    final_url: str
    http_status: int
    retrieved_at: datetime
    sha256: Sha256
    language: str | None = None
    domain_on_official_list: bool
    identity_score: Decimal


class ChangeRecord(Strict):
    change_id: UUID
    orgnr: Orgnr
    job_id: UUID
    field: str
    previous_value: Any = None
    new_value: Any = None
    previous_fact_id: UUID | None = None
    new_fact_id: UUID | None = None
    source_id: UUID
    detected_at: datetime
    evidence_refs: list[str] = Field(default_factory=list)
    kind: Literal["added", "removed", "modified"]


class Store(Protocol):
    def complete_company(self, dossier: Dossier, facts: Iterable[PublishedFact] = (),
                         rejections: Iterable[RejectionRecord] = (),
                         sources: Iterable[SourceRecord] = ()) -> None: ...

    def is_complete(self, job_id: UUID | str, orgnr: str) -> bool: ...

    def completed(self, job_id: UUID | str) -> dict[str, Dossier]: ...

    def rejection_counts(self, job_id: UUID | str) -> dict[str, int]: ...

    def write_change(self, change: ChangeRecord) -> None: ...


def read_lines(path: Path) -> tuple[list[str], bool]:
    """Valid JSON lines of a file. The flag is true when a half-written last line was dropped."""
    if not path.exists():
        return [], False
    text = path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    for number, line in enumerate(lines, 1):
        try:
            json.loads(line)
        except ValueError:
            if number == len(lines):
                return lines[:-1], True
            raise StoreError(f"{path.name} line {number} is not valid JSON") from None
    return lines, bool(text) and not text.endswith("\n")


def source_key(source: dict) -> tuple[str, str, str]:
    return source["orgnr"], source["url"], source["sha256"]


class JsonlStore:
    def __init__(self, output_dir: Path):
        self.dir = Path(output_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.dossiers_path = self.dir / "dossiers.jsonl"
        self.facts_path = self.dir / "facts.jsonl"
        self.rejections_path = self.dir / "rejections.jsonl"
        self.sources_path = self.dir / "sources.jsonl"
        self.completed_path = self.dir / "completed.jsonl"
        self.changes_path = self.dir / "changes.jsonl"
        self._done: dict[tuple[str, str], dict] = {}  # (job_id, orgnr) -> completion marker
        self._dossiers: dict[str, str] = {}  # orgnr -> JSON line
        self._sources: set[tuple[str, str, str]] = set()
        self._rejected: dict[str, Counter] = defaultdict(Counter)
        for path in (self.dossiers_path, self.facts_path, self.rejections_path,
                     self.sources_path, self.completed_path):
            path.touch()
        self._load()

    @contextmanager
    def _locked(self):
        with open(self.dir / ".store.lock", "a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def _load(self) -> None:
        with self._locked():
            for temp in self.dir.glob("*.jsonl.tmp"):
                temp.unlink()
            markers = [json.loads(line) for line in self._filter(self.completed_path, lambda row: True)]
            for marker in markers:
                key = (marker["job_id"], marker["orgnr"])
                if key in self._done:
                    raise StoreError(f"two completion markers for {key[1]} in job {key[0]}")
                self._done[key] = marker

            # Lines without a marker belong to a company that did not finish: drop them, the resume redoes it.
            fact_ids = {i for marker in markers for i in marker["fact_ids"]}
            rejection_ids = {i for marker in markers for i in marker["rejection_ids"]}
            self._filter(self.facts_path, lambda row: row["fact_id"] in fact_ids)
            for line in self._filter(self.rejections_path, lambda row: row["rejection_id"] in rejection_ids):
                self._count(json.loads(line))
            for line in self._filter(self.sources_path, lambda row: True):
                self._sources.add(source_key(json.loads(line)))
            for line in self._filter(self.dossiers_path, lambda row: (row["job_id"], row["orgnr"]) in self._done):
                orgnr = json.loads(line)["orgnr"]
                if orgnr in self._dossiers:
                    raise StoreError(f"dossiers.jsonl has two dossiers for {orgnr}")
                self._dossiers[orgnr] = line

    def _filter(self, path: Path, keep: Callable[[dict], bool]) -> list[str]:
        lines, torn = read_lines(path)
        kept = [line for line in lines if keep(json.loads(line))]
        if torn or len(kept) != len(lines):
            self._rewrite(path, kept)
        return kept

    def _count(self, rejection: dict) -> None:
        self._rejected[rejection["job_id"]][rejection["reason_code"]] += 1

    def complete_company(self, dossier, facts=(), rejections=(), sources=()) -> None:
        facts, rejections, sources = list(facts), list(rejections), list(sources)
        check_unit(dossier, facts, rejections)
        key = (str(dossier.job_id), dossier.orgnr)
        with self._locked():
            if key in self._done:
                raise DuplicateRecord(f"company {dossier.orgnr} is already complete in job {key[0]}")
            # The same page text fetched again is stored once.
            new_sources = {source_key(s.model_dump(mode="json")): s for s in sources}
            new_sources = [s for k, s in new_sources.items() if k not in self._sources]

            self._append(self.facts_path, [fact.model_dump_json() for fact in facts])
            self._append(self.rejections_path, [item.model_dump_json() for item in rejections])
            self._append(self.sources_path, [source.model_dump_json() for source in new_sources])
            dossiers = {**self._dossiers, dossier.orgnr: dossier.model_dump_json()}
            self._rewrite(self.dossiers_path, dossiers.values())
            marker = {
                "job_id": key[0],
                "orgnr": dossier.orgnr,
                "fact_ids": [str(fact.fact_id) for fact in facts],
                "rejection_ids": [str(item.rejection_id) for item in rejections],
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            self._write_marker(marker)

            self._dossiers = dossiers
            self._done[key] = marker
            self._sources.update(source_key(s.model_dump(mode="json")) for s in new_sources)
            for item in rejections:
                self._rejected[key[0]][item.reason_code.value] += 1

    def _write_marker(self, marker: dict) -> None:
        self._append(self.completed_path, [json.dumps(marker, ensure_ascii=False)])

    def is_complete(self, job_id, orgnr: str) -> bool:
        return (str(job_id), orgnr) in self._done

    def completed(self, job_id) -> dict[str, Dossier]:
        found = {}
        for job, orgnr in self._done:
            if job != str(job_id) or orgnr not in self._dossiers:
                continue
            dossier = Dossier.model_validate_json(self._dossiers[orgnr])
            if str(dossier.job_id) == job:  # a later job may have replaced it
                found[orgnr] = dossier
        return found

    def rejection_counts(self, job_id) -> dict[str, int]:
        return dict(self._rejected[str(job_id)])

    def write_change(self, change: ChangeRecord) -> None:
        with self._locked():
            self._append(self.changes_path, [change.model_dump_json()])

    def _append(self, path: Path, lines: list[str]) -> None:
        if not lines:
            return
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("".join(line + "\n" for line in lines))
            handle.flush()
            os.fsync(handle.fileno())

    def _rewrite(self, path: Path, lines: Iterable[str]) -> None:
        temp = path.with_name(path.name + ".tmp")
        with open(temp, "w", encoding="utf-8") as handle:
            handle.write("".join(line + "\n" for line in lines))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)


def check_unit(dossier: Dossier, facts: list[PublishedFact], rejections: list[RejectionRecord]) -> None:
    if {str(fact.fact_id) for fact in facts} != set(dossier.published_fact_ids):
        raise ValueError("the dossier's published_fact_ids do not match the facts")
    if any(fact.orgnr != dossier.orgnr for fact in facts):
        raise ValueError("a fact belongs to another company")
    if any(item.orgnr != dossier.orgnr or item.job_id != dossier.job_id for item in rejections):
        raise ValueError("a rejection belongs to another company or job")


def open_store(mode: str, output_dir: Path) -> Store:
    if mode == "jsonl":
        return JsonlStore(output_dir)
    if mode == "mongo":
        raise ConfigError("STORE_MODE=mongo is not available because Full mode is not built. Use STORE_MODE=jsonl.")
    raise ConfigError(f"STORE_MODE must be jsonl, not {mode!r}")
