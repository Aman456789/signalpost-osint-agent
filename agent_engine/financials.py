from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from agent_engine.errors import SourceUnavailable
from agent_engine.registry_client import AccountsResult, dig
from agent_engine.schemas import FinancialRecord, Flag

# Brreg reports whole NOK, so the scale is 1. Check against the P0-05 fixtures.
UNIT_SCALE = 1

# JSON paths into one accounts entry; verify against the official Brreg documentation (task P0-05).
METRIC_PATHS = {
    "revenue": ("resultatregnskapResultat", "driftsresultat", "driftsinntekter", "sumDriftsinntekter"),
    "operating_result": ("resultatregnskapResultat", "driftsresultat", "driftsresultat"),
    "net_result": ("resultatregnskapResultat", "aarsresultat"),
    "total_assets": ("eiendeler", "sumEiendeler"),
    "equity": ("egenkapitalGjeld", "egenkapital", "sumEgenkapital"),
}


class PlanBDisabled(SourceUnavailable):
    pass


@dataclass
class FinancialResult:
    records: list[FinancialRecord]
    flags: list[Flag]
    reason: str | None = None


def plan_b_financials(orgnr: str, enabled: bool):
    raise PlanBDisabled("disabled" if not enabled else "plan B reader is not built")


def build_financials(orgnr: str, accounts: AccountsResult, plan_b_enabled: bool = False) -> FinancialResult:
    if accounts.kind == "outage" and accounts.reason == "plan_a_outage":
        try:
            plan_b_financials(orgnr, plan_b_enabled)
        except PlanBDisabled:
            return unavailable(orgnr, "plan_b_not_permitted", accounts)
    if accounts.kind != "ok":
        return unavailable(orgnr, accounts.reason or "no_accounts_filed", accounts)

    latest = max(accounts.entries, key=lambda entry: entry["regnskapsperiode"]["tilDato"])
    if dig(latest, ("virksomhet", "organisasjonsnummer")) != orgnr:
        return unavailable(orgnr, "org_mismatch", accounts)
    currency = latest.get("valuta")
    if not (isinstance(currency, str) and len(currency) == 3 and currency.isupper()):
        return unavailable(orgnr, "currency_unknown", accounts)

    period = latest["regnskapsperiode"]
    index = accounts.entries.index(latest)
    records = []
    for metric, path in METRIC_PATHS.items():
        value = dig(latest, path)
        if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
            continue
        amount = Decimal(value)
        records.append(FinancialRecord(
            financial_id=uuid4(),
            orgnr=orgnr,
            metric=metric,
            fiscal_year=int(period["tilDato"][:4]),
            period_start=period.get("fraDato"),
            period_end=period["tilDato"],
            amount=amount,
            currency=currency,
            unit_scale=UNIT_SCALE,
            amount_as_printed=str(value),
            amount_base=amount * UNIT_SCALE,
            method="registry",
            source_url=accounts.url,
            source_ref=f"$[{index}]." + ".".join(path),
            org_match=True,
            unit_verified=True,
            retrieved_at=accounts.retrieved_at,
            sha256=accounts.sha256,
            verification_status="verified",
        ))
    if not records:
        return unavailable(orgnr, "no_metrics", accounts)
    return FinancialResult(records, [])


def unavailable(orgnr: str, reason: str, accounts: AccountsResult) -> FinancialResult:
    # the schema wants a year on every record, so these rows carry the retrieval year
    when = accounts.retrieved_at or datetime.now(timezone.utc)
    records = [
        FinancialRecord(
            financial_id=uuid4(),
            orgnr=orgnr,
            metric=metric,
            fiscal_year=when.year,
            method="unavailable",
            source_url=accounts.url,
            source_ref="n/a",
            org_match=False,
            unit_verified=False,
            retrieved_at=when,
            unavailable_reason=reason,
            verification_status="unavailable",
        )
        for metric in METRIC_PATHS
    ]
    return FinancialResult(records, [Flag.FINANCIALS_UNAVAILABLE], reason)
