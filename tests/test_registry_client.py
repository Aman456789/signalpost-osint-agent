import pytest

from agent_engine.errors import SourceUnavailable
from tests.helpers import FIXTURE_ORGNR, registry

ORG = FIXTURE_ORGNR


async def test_main_record_is_parsed():
    async with registry() as (client, brreg, ledger):
        record = await client.fetch_company(ORG)
    assert record.legal_name == "EKSEMPEL KONSULT AS"
    assert record.org_form == "AS"
    assert record.status == "active"
    assert record.website == "www.eksempelkonsult.no"
    assert not record.is_subunit
    assert len(record.sha256) == 64
    assert brreg.calls == [("main", ORG)]


async def test_404_falls_back_to_subunit_as_one_more_request():
    async with registry({ORG: "subunit"}) as (client, brreg, ledger):
        record = await client.fetch_company(ORG)
    assert record.is_subunit
    assert record.parent_orgnr == "984851006"
    assert brreg.calls == [("main", ORG), ("sub", ORG)]
    assert ledger.total == 2


async def test_unknown_company_returns_none_after_two_requests():
    async with registry({ORG: "not_found"}) as (client, brreg, ledger):
        assert await client.fetch_company(ORG) is None
    assert ledger.total == 2


async def test_deleted_company_is_a_valid_status():
    async with registry({ORG: "gone"}) as (client, _, _):
        record = await client.fetch_company(ORG)
    assert record.status == "deleted"


async def test_5xx_is_retried_with_reserved_retries_then_fails():
    async with registry({ORG: "main_503"}) as (client, brreg, ledger):
        with pytest.raises(SourceUnavailable):
            await client.fetch_company(ORG)
    assert brreg.count(ORG) == 3
    assert ledger.snapshot()["requests_by_kind"] == {"registry": 1, "retry": 2}


async def test_malformed_body_is_a_format_change_and_not_retried():
    async with registry({ORG: "main_malformed"}) as (client, brreg, ledger):
        with pytest.raises(SourceUnavailable, match="format_change"):
            await client.fetch_company(ORG)
    assert ledger.total == 1


async def test_roles_keep_names_and_roles_only():
    async with registry() as (client, _, _):
        roles = await client.fetch_roles(ORG)
    assert [(r.name, r.role) for r in roles] == [
        ("Kari Nordmann", "chair"),
        ("Ola Per Hansen", "board_member"),
        ("Siri Berg", "ceo"),
        ("REVISJON ØST AS", "other"),
    ]
    dumped = str([r.model_dump() for r in roles])
    assert "fodselsdato" not in dumped and "1970" not in dumped


async def test_accounts_200_returns_all_filed_years():
    async with registry() as (client, _, _):
        result = await client.fetch_accounts(ORG)
    assert result.kind == "ok"
    assert len(result.entries) == 2
    assert result.sha256 and result.retrieved_at


async def test_no_accounts_filed_is_not_an_outage():
    orgs = [f"{n}" for n in ("923456783", "984851006", "923609016", "982463718", "984661185")]
    async with registry({o: "no_accounts" for o in orgs}) as (client, _, _):
        results = [await client.fetch_accounts(o) for o in orgs]
    assert all(r.kind == "none" and r.reason == "no_accounts_filed" for r in results)
    assert not client.plan_c


async def test_three_outage_signals_in_a_row_switch_to_plan_c():
    orgs = ["923456783", "984851006", "923609016", "982463718"]
    async with registry({o: "accounts_malformed" for o in orgs}) as (client, brreg, ledger):
        first = [await client.fetch_accounts(o) for o in orgs[:3]]
        assert [r.reason for r in first] == ["format_change"] * 3
        assert client.plan_c
        before = ledger.total
        fourth = await client.fetch_accounts(orgs[3])
    assert fourth.kind == "outage" and fourth.reason == "plan_a_outage"
    assert ledger.total == before


async def test_a_good_answer_resets_the_outage_count():
    bad = ["923456783", "984851006", "923609016", "982463718"]
    async with registry({o: "accounts_malformed" for o in bad}) as (client, _, _):
        await client.fetch_accounts(bad[0])
        await client.fetch_accounts(bad[1])
        assert (await client.fetch_accounts("984661185")).kind == "ok"
        await client.fetch_accounts(bad[2])
        await client.fetch_accounts(bad[3])
        assert not client.plan_c


async def test_5xx_on_accounts_is_an_outage_signal_after_retries():
    async with registry({ORG: "accounts_503"}) as (client, brreg, ledger):
        result = await client.fetch_accounts(ORG)
    assert result.kind == "outage" and result.reason == "accounts_unreachable"
    assert ledger.total == 3
