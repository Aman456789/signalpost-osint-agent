import re
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agent_engine.schemas import FinancialRecord

ROOT = Path(__file__).resolve().parents[1]
FINANCIAL_FILES = [ROOT / "agent_engine" / "schemas.py", ROOT / "agent_engine" / "financials.py"]


def test_financial_code_never_uses_the_word_float():
    for path in FINANCIAL_FILES:
        if path.exists():
            assert not re.search(r"\bfloat\b", path.read_text(encoding="utf-8"), re.I), path.name


def record(**override):
    data = dict(financial_id=uuid4(), orgnr="923456783", metric="revenue", fiscal_year=2025,
                amount=Decimal("1504.112"), currency="NOK", unit_scale=1000, amount_as_printed="1 504,112",
                amount_base=Decimal("1504112"), method="registry", source_url="https://data.brreg.no/x",
                source_ref="registry-record", org_match=True, unit_verified=True,
                retrieved_at="2026-10-17T09:00:00Z", verification_status="verified")
    return FinancialRecord(**{**data, **override})


def test_amounts_are_decimals():
    item = record(amount="1504.112")
    assert isinstance(item.amount, Decimal)
    assert item.amount_base == item.amount * item.unit_scale


def test_binary_numbers_are_rejected():
    with pytest.raises(ValidationError):
        record(amount=1504.112)


def test_amount_base_must_match_the_scale():
    with pytest.raises(ValidationError):
        record(amount_base=Decimal("1504"))
