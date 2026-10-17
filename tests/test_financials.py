from decimal import Decimal

import pytest

from agent_engine.errors import SourceUnavailable
from agent_engine.financials import PlanBDisabled, build_financials, plan_b_financials
from agent_engine.schemas import Flag
from tests.helpers import FIXTURE_ORGNR, registry

ORG = FIXTURE_ORGNR


async def test_latest_year_and_exact_decimal_amounts():
    async with registry() as (client, _, _):
        accounts = await client.fetch_accounts(ORG)
    result = build_financials(ORG, accounts)
    by_metric = {r.metric: r for r in result.records}
    assert result.flags == []
    assert set(by_metric) == {"revenue", "operating_result", "net_result", "total_assets", "equity"}
    revenue = by_metric["revenue"]
    assert revenue.fiscal_year == 2024
    assert revenue.amount == Decimal("12345678.5")
    assert revenue.amount_base == revenue.amount * revenue.unit_scale
    assert revenue.amount_as_printed == "12345678.5"
    assert revenue.method == "registry" and revenue.sha256


async def test_no_accounts_filed_gives_unavailable_with_reason():
    async with registry({ORG: "no_accounts"}) as (client, _, _):
        accounts = await client.fetch_accounts(ORG)
    result = build_financials(ORG, accounts)
    assert result.reason == "no_accounts_filed"
    assert result.flags == [Flag.FINANCIALS_UNAVAILABLE]
    assert all(r.amount is None and r.unavailable_reason == "no_accounts_filed" for r in result.records)


async def test_plan_c_during_an_outage_when_plan_b_is_off():
    orgs = ["923456783", "984851006", "923609016", "982463718"]
    async with registry({o: "accounts_malformed" for o in orgs}) as (client, _, _):
        for org in orgs[:3]:
            await client.fetch_accounts(org)
        accounts = await client.fetch_accounts(orgs[3])
    result = build_financials(orgs[3], accounts, plan_b_enabled=False)
    assert result.reason == "plan_b_not_permitted"
    assert result.flags == [Flag.FINANCIALS_UNAVAILABLE]


async def test_other_organisation_in_the_accounts_is_refused():
    async with registry() as (client, _, _):
        accounts = await client.fetch_accounts(ORG)
    result = build_financials("984851006", accounts)
    assert result.reason == "org_mismatch"


def test_plan_b_raises_disabled():
    with pytest.raises(PlanBDisabled, match="disabled"):
        plan_b_financials(ORG, enabled=False)
    assert issubclass(PlanBDisabled, SourceUnavailable)
