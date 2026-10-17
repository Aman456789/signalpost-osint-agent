from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agent_engine.schemas import (
    BudgetLedger,
    Company,
    Dossier,
    Extraction,
    Fact,
    FactKey,
    JobCompany,
    PublishedFact,
    RejectionReason,
    RunReport,
    ValidationResult,
    count_verified_facts,
    latest_retrieval,
)

NOW = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)


def fact(**override):
    data = dict(key="products", value="Sells fish feed", value_no="Selger fôr",
                quote="Vi selger fôr til lakseoppdrett.", source_url="https://example.no/om-oss")
    return Fact(**{**data, **override})


def published_fact(**override):
    data = dict(fact_id=uuid4(), orgnr="923456783", key="products", value="Sells fish feed",
                value_no="Selger fôr", quote="Vi selger fôr til lakseoppdrett.", method="llm_verified",
                source_id=uuid4(), source_url="https://example.no/om-oss", retrieved_at=NOW,
                sha256="a" * 64, as_of=NOW, identity_score=Decimal("1.0"), q=Decimal("1"),
                v=Decimal("1"), g=Decimal("1"), s=Decimal("0.8"), f=Decimal("1"),
                confidence=Decimal("0.88"), validation_id=uuid4(), created_at=NOW)
    return PublishedFact(**{**data, **override})


def validation_result(**override):
    data = dict(validation_id=uuid4(), candidate_id=uuid4(), schema_ok=True, g_identity_ok=True,
                q_raw=Decimal("1.00"), q=Decimal("1"), quote_start=10, quote_end=40, v=Decimal("1"),
                v_checks=dict(key_words_ok=True, digits_ok=True, names_ok=True), money_filter="not_money",
                confidence=Decimal("0.88"), decision="publish", decided_at=NOW)
    return ValidationResult(**{**data, **override})


def budget_ledger(**override):
    return BudgetLedger(**{**dict(job_id=uuid4(), updated_at=NOW), **override})


def run_report(**override):
    data = dict(job_id=uuid4(), mode="daily_test", started_at=NOW, ended_at=NOW, duration_seconds=0,
                company_count=0, outcomes={}, requests=dict(total=0, by_kind={}), llm_calls=0,
                input_tokens=0, output_tokens=0, tokens_estimated=False,
                estimated_cost_usd=Decimal("0.00"), cost_limit_usd=Decimal("10"), time_limit_min=45,
                stop_reason="completed",
                flags=dict(soft_cap_reached=False, brake_tripped=False, kill_switch_tripped=False,
                           plan_a_outage_detected=False),
                plan_b_used_count=0, config_hash="0" * 64, code_version="abc1234")
    return RunReport(**{**data, **override})


def test_fact_key_menu_has_eight_keys():
    assert len(FactKey) == 8
    for key in FactKey:
        assert fact(key=key.value).key is key


def test_fact_rejects_unknown_key_and_extra_fields():
    with pytest.raises(ValidationError):
        fact(key="revenue")
    with pytest.raises(ValidationError):
        fact(confidence=1)


def test_extraction_may_be_empty_but_not_longer_than_20():
    assert Extraction(facts=[]).facts == []
    with pytest.raises(ValidationError):
        Extraction(facts=[fact()] * 21)


def test_orgnr_must_have_nine_digits():
    Company(orgnr="923456783", first_seen_at=NOW, last_seen_at=NOW)
    for bad in ("12345", "92345678a", "9234567831"):
        with pytest.raises(ValidationError):
            Company(orgnr=bad, first_seen_at=NOW, last_seen_at=NOW)


def test_confidence_below_080_is_not_publishable():
    assert published_fact(confidence=Decimal("0.80")).confidence == Decimal("0.80")
    with pytest.raises(ValidationError):
        published_fact(confidence=Decimal("0.79"))


def test_registry_facts_have_a_path_and_no_quote():
    registry = published_fact(method="registry", quote=None, registry_json_path="$.navn")
    assert registry.method == "registry"
    with pytest.raises(ValidationError):
        published_fact(method="registry", quote="text", registry_json_path="$.navn")
    with pytest.raises(ValidationError):
        published_fact(quote=None)


def test_retrieved_at_and_as_of_stay_separate():
    as_of = NOW - timedelta(days=365)
    item = published_fact(as_of=as_of)
    assert item.retrieved_at == NOW
    assert item.as_of == as_of


def test_rejection_reason_has_exactly_the_twelve_codes():
    expected = {
        "schema_invalid", "identity_failed", "quote_not_found", "quote_translated",
        "value_unsupported", "digit_unsupported", "name_unsupported", "money_blocked",
        "below_threshold", "llm_invalid_json", "fetch_failed", "conflicts_with_registry",
    }
    assert {reason.value for reason in RejectionReason} == expected
    assert len(RejectionReason) == 12


def test_quote_offsets_come_as_a_pair():
    assert validation_result().quote_end == 40
    assert validation_result(q=Decimal("0"), q_raw=Decimal("0.40"), quote_start=None, quote_end=None).q == 0
    with pytest.raises(ValidationError):
        validation_result(quote_end=None)
    with pytest.raises(ValidationError):
        validation_result(quote_start=40, quote_end=40)
    with pytest.raises(ValidationError):
        validation_result(q=Decimal("0"))
    with pytest.raises(ValidationError):
        validation_result(quote_start=None, quote_end=None)


def test_rejected_result_needs_stage_and_reason():
    with pytest.raises(ValidationError):
        validation_result(decision="reject")
    result = validation_result(decision="reject", first_failed_stage="quote", reason_code="quote_not_found")
    assert result.reason_code is RejectionReason.QUOTE_NOT_FOUND


def test_plan_b_used_count_exists_on_ledger_and_report():
    assert "plan_b_used_count" in BudgetLedger.model_fields
    assert "plan_b_used_count" in RunReport.model_fields
    assert budget_ledger().plan_b_used_count == 0
    assert run_report(plan_b_used_count=3).plan_b_used_count == 3
    with pytest.raises(ValidationError):
        budget_ledger(plan_b_used_count=-1)


def test_run_report_accepts_any_time_limit_or_none():
    for limit in (45, 40, 150, None):
        assert run_report(time_limit_min=limit).time_limit_min == limit


def test_ledger_enforces_the_per_company_cap():
    budget_ledger(per_company_requests={"923456783": 14})
    with pytest.raises(ValidationError):
        budget_ledger(per_company_requests={"923456783": 15})
    with pytest.raises(ValidationError):
        JobCompany(job_id=uuid4(), orgnr="923456783", requests_used=15)


def test_verified_fact_count_counts_published_ai_facts_only():
    registry = published_fact(method="registry", quote=None, registry_json_path="$.navn")
    ai = published_fact()
    old = published_fact(publication_status="superseded")
    assert count_verified_facts([registry, ai, old]) == 1


def test_data_freshness_is_the_latest_retrieval_time():
    earlier = NOW - timedelta(hours=3)
    assert latest_retrieval([earlier, NOW, earlier]) == NOW


def test_dossier_id_equals_orgnr():
    data = dict(dossier_id="923456783", orgnr="923456783", registry_status="active",
                processing_status="registry_only", data_freshness=NOW, created_at=NOW,
                updated_at=NOW, job_id=uuid4())
    assert Dossier(**data).verified_fact_count == 0
    with pytest.raises(ValidationError):
        Dossier(**{**data, "dossier_id": "984851006"})
