import logging
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import UUID

from agent_engine.errors import SourceUnavailable
from agent_engine.financials import build_financials
from agent_engine.registry_client import AccountsResult, RegistryClient, RegistryRecord, dig
from agent_engine.schemas import Dossier, ProcessingStatus, latest_retrieval

log = logging.getLogger("signalpost.profile")

FIELD_PATHS = (
    "navn",
    "organisasjonsform.kode",
    "hjemmeside",
    "forretningsadresse.poststed",
    "registreringsdatoEnhetsregisteret",
    "antallAnsatte",
    "naeringskode1.beskrivelse",
)


def website_parts(raw: str | None) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    url = raw.strip()
    if "://" not in url:
        url = "https://" + url
    host = urlsplit(url).hostname
    if not host:
        return None, None
    return url, host.removeprefix("www.")


def registry_fields(record: RegistryRecord) -> dict:
    fields = {}
    for path in FIELD_PATHS:
        value = dig(record.raw, path.split("."))
        if value is not None:
            fields["$." + path] = value
    fields["_source"] = {
        "url": record.url,
        "sha256": record.sha256,
        "retrieved_at": record.retrieved_at.isoformat(),
    }
    return fields


async def build_profile(orgnr: str, registry: RegistryClient, job_id: UUID, plan_b_enabled: bool = False) -> Dossier | None:
    record = await registry.fetch_company(orgnr)
    if record is None:
        return None

    roles = []
    if not record.is_subunit:
        try:
            roles = await registry.fetch_roles(orgnr)
        except SourceUnavailable as exc:
            log.warning("roles unavailable", extra={"fields": {"orgnr": orgnr, "reason": str(exc)}})

    if record.is_subunit:
        accounts = AccountsResult("none", "subunit_has_no_accounts")
    else:
        accounts = await registry.fetch_accounts(orgnr)
    financials = build_financials(orgnr, accounts, plan_b_enabled)

    now = datetime.now(timezone.utc)
    website_url, domain = website_parts(record.website)
    retrieved = [record.retrieved_at] + ([accounts.retrieved_at] if accounts.retrieved_at else [])
    return Dossier(
        dossier_id=orgnr,
        orgnr=orgnr,
        legal_name=record.legal_name,
        org_form=record.org_form,
        registry_status=record.status,
        website_url=website_url,
        website_official_domain=domain,
        processing_status=ProcessingStatus.PASS1_COMPLETE,
        flags=financials.flags,
        registry_fields=registry_fields(record),
        roles=roles,
        financial_summary=financials.records,
        data_freshness=latest_retrieval(retrieved),
        created_at=now,
        updated_at=now,
        job_id=job_id,
    )


def empty_dossier(orgnr: str, status: ProcessingStatus, job_id: UUID, flags=()) -> Dossier:
    now = datetime.now(timezone.utc)
    return Dossier(
        dossier_id=orgnr,
        orgnr=orgnr,
        registry_status="unknown",
        processing_status=status,
        flags=list(flags),
        data_freshness=now,
        created_at=now,
        updated_at=now,
        job_id=job_id,
    )
