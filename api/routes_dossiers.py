from typing import Literal

from fastapi import APIRouter, Query, Request

from agent_engine.input_processor import rejection_reason
from agent_engine.schemas import ProcessingStatus
from api import records
from api.problems import ProblemError
from api.state import get_state
from storage.evidence_vault import EvidenceVault

router = APIRouter()

SORTS = {
    "name": lambda d: ((d["legal_name"] or "").casefold(), d["orgnr"]),
    "orgnr": lambda d: (d["orgnr"],),
    "facts": lambda d: (d["verified_fact_count"], d["orgnr"]),
    "updated_at": lambda d: (records.timestamp(d["updated_at"]), d["orgnr"]),
}
FACT_FIELDS = ("confidence", "identity_score", "q", "v", "g", "s", "f")


def summary(dossier: dict) -> dict:
    return {
        "orgnr": dossier["orgnr"],
        "legal_name": dossier["legal_name"],
        "org_form": dossier["org_form"],
        "registry_status": dossier["registry_status"],
        "processing_status": dossier["processing_status"],
        "verified_fact_count": dossier["verified_fact_count"],
        "financials_available": any(r["verification_status"] == "verified" for r in dossier["financial_summary"]),
        "flags": dossier["flags"],
        "data_freshness": dossier["data_freshness"],  # the Retrieval Date
    }


@router.get("/dossiers")
async def list_dossiers(
    request: Request,
    q: str | None = Query(None, max_length=100),
    status: ProcessingStatus | None = None,
    sort: Literal["name", "orgnr", "facts", "updated_at"] = "updated_at",
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
):
    items = records.dossiers(get_state(request).output_dir())
    if status:
        items = [d for d in items if d["processing_status"] == status.value]
    if q:
        needle = q.casefold()
        items = [d for d in items if d["orgnr"].startswith(q) or needle in (d["legal_name"] or "").casefold()]
    scope = f"dossiers:{sort}:{order}:{status.value if status else ''}:{q or ''}"
    page, next_cursor = records.paginate(items, SORTS[sort], descending=order == "desc",
                                         limit=limit, cursor=cursor, scope=scope)
    return {"items": [summary(d) for d in page], "next_cursor": next_cursor}


def published_facts(output_dir, dossier: dict) -> list[dict]:
    facts = records.facts_by_id(output_dir)
    found = []
    for fact_id in dossier["published_fact_ids"]:
        if fact_id in facts:
            fact = dict(facts[fact_id])
            fact["evidence_url"] = f"/api/dossiers/{dossier['orgnr']}/facts/{fact_id}/evidence"
            found.append(fact)
    return found


@router.get("/dossiers/{orgnr}")
async def get_dossier(orgnr: str, request: Request):
    reason = rejection_reason(orgnr)
    if reason:
        raise ProblemError(422, "validation-error", "Validation failed",
                           f"{orgnr[:64]!r} is not a valid organisation number.",
                           rejected=[{"line": 1, "value": orgnr[:64], "reason": reason}])
    output_dir = get_state(request).output_dir()
    dossier = records.find_dossier(output_dir, orgnr)
    if dossier is None:
        raise ProblemError(404, "not-found", "Dossier not found", f"There is no dossier for {orgnr}.")
    return {**dossier, "facts": published_facts(output_dir, dossier)}


@router.get("/dossiers/{orgnr}/facts/{fact_id}/evidence")
async def get_evidence(orgnr: str, fact_id: str, request: Request):
    state = get_state(request)
    output_dir = state.output_dir()
    dossier = records.find_dossier(output_dir, orgnr)
    fact = next((f for f in published_facts(output_dir, dossier) if f["fact_id"] == fact_id), None) if dossier else None
    if fact is None:
        raise ProblemError(404, "not-found", "Fact not found", f"{orgnr} has no published fact {fact_id[:64]}.")

    source = records.sources_by_id(output_dir).get(fact["source_id"])
    snapshot = None
    if fact["method"] == "llm_verified":
        vault = EvidenceVault(state.settings.data_dir / "snapshots")
        try:
            text = vault.load_text(fact["sha256"])
        except FileNotFoundError:
            raise ProblemError(404, "snapshot-missing", "Saved page text not found",
                               "The saved page text for this fact is not on disk.") from None
        except ValueError:
            raise ProblemError(500, "snapshot-changed", "Saved page text was changed",
                               "The saved page text no longer matches its SHA-256.") from None
        start = text.find(fact["quote"])
        snapshot = {
            "sha256": fact["sha256"],
            "text": text,
            "highlight": {"start": start, "end": start + len(fact["quote"])} if start >= 0 else None,
            "offset_unit": "unicode_code_points",
        }
    return {
        "fact": fact,
        "quote": fact["quote"],
        "snapshot": snapshot,
        "source": source,
        "source_url": fact["source_url"],
        "final_url": source["final_url"] if source else None,
        "retrieved_at": fact["retrieved_at"],
        "sha256": fact["sha256"],
        "validation": {"validation_id": fact["validation_id"], "publication_status": fact["publication_status"]},
        "confidence": {name: fact[name] for name in FACT_FIELDS},
    }
