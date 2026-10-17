import asyncio

import pytest

from agent_engine.errors import BudgetDenied
from governor.budget_ledger import BudgetLedger
from governor.rate_limiter import SlidingWindowLimiter
from tests.helpers import FakeClock


def ledger_at(total: int, **kwargs) -> BudgetLedger:
    ledger = BudgetLedger(**kwargs)
    ledger.restore({"total_outbound_requests": total})
    return ledger


async def test_brake_allows_up_to_1950():
    ledger = ledger_at(1949)
    await ledger.reserve("c1", "registry")
    assert ledger.total == 1950
    assert not ledger.brake.tripped


@pytest.mark.parametrize("start", [1950, 1951])
async def test_brake_denies_past_1950(start):
    ledger = ledger_at(start)
    with pytest.raises(BudgetDenied) as denied:
        await ledger.reserve("c1", "registry")
    assert denied.value.reason == "request_brake"
    assert ledger.total == start
    assert ledger.brake.tripped


async def test_brake_stays_tripped_even_for_small_requests():
    ledger = BudgetLedger(brake=10)
    await ledger.reserve("c1", "registry", weight=8)
    with pytest.raises(BudgetDenied):
        await ledger.reserve("c1", "registry", weight=3)
    with pytest.raises(BudgetDenied):
        await ledger.reserve("c2", "registry")
    assert ledger.total == 8


async def test_soft_cap_denies_only_optional_requests():
    ledger = ledger_at(1699)
    await ledger.reserve("c1", "website", optional=True)
    with pytest.raises(BudgetDenied) as denied:
        await ledger.reserve("c1", "website", optional=True)
    assert denied.value.reason == "soft_cap"
    with pytest.raises(BudgetDenied):
        await ledger.reserve("c1", "plan_b")
    await ledger.reserve("c1", "website")
    await ledger.reserve("c1", "registry")
    assert ledger.total == 1702
    assert ledger.soft_cap_reached


async def test_per_company_cap_is_14():
    ledger = BudgetLedger()
    for _ in range(14):
        await ledger.reserve("c1", "website")
    with pytest.raises(BudgetDenied) as denied:
        await ledger.reserve("c1", "retry")
    assert denied.value.reason == "per_company_cap"
    await ledger.reserve("c2", "website")
    assert ledger.company_requests("c1") == 14


async def test_200_parallel_reservations_lose_no_update():
    ledger = BudgetLedger()
    await asyncio.gather(*(ledger.reserve(f"c{i % 20}", "registry") for i in range(200)))
    snapshot = ledger.snapshot()
    assert ledger.total == 200
    assert sum(snapshot["per_company_requests"].values()) == 200
    assert snapshot["requests_by_kind"] == {"registry": 200}


async def test_parallel_reservations_stop_exactly_at_the_brake():
    ledger = BudgetLedger(brake=100)
    results = await asyncio.gather(
        *(ledger.reserve(f"c{i}", "registry") for i in range(200)), return_exceptions=True
    )
    granted = [r for r in results if not isinstance(r, Exception)]
    assert len(granted) == 100
    assert ledger.total == 100


async def test_kinds_and_weights_are_counted():
    ledger = BudgetLedger()
    await ledger.reserve("c1", "registry")
    await ledger.reserve("c1", "retry")
    await ledger.reserve("c1", "redirect_hop")
    await ledger.reserve("c1", "website", weight=3)
    snapshot = ledger.snapshot()
    assert ledger.total == 6
    assert ledger.company_requests("c1") == 6
    assert snapshot["requests_by_kind"] == {"registry": 1, "retry": 1, "redirect_hop": 1, "website": 3}


async def test_weight_over_the_company_cap_is_denied_whole():
    ledger = BudgetLedger()
    await ledger.reserve("c1", "website", weight=12)
    with pytest.raises(BudgetDenied):
        await ledger.reserve("c1", "website", weight=3)
    assert ledger.company_requests("c1") == 12


async def test_checks_run_in_order_brake_before_company_cap():
    ledger = ledger_at(1950)
    with pytest.raises(BudgetDenied) as denied:
        await ledger.reserve("c1", "website", weight=20)
    assert denied.value.reason == "request_brake"


async def test_kill_switch_blocks_plan_b_only():
    ledger = BudgetLedger()
    ledger.trip_kill_switch()
    with pytest.raises(BudgetDenied) as denied:
        await ledger.reserve("c1", "plan_b")
    assert denied.value.reason == "kill_switch"
    await ledger.reserve("c1", "website")


async def test_llm_window_denies_the_31st_call_in_a_minute():
    clock = FakeClock()
    ledger = BudgetLedger(limiter=SlidingWindowLimiter(30, 60, clock))
    for i in range(30):
        await ledger.reserve(f"c{i}", "llm")
    with pytest.raises(BudgetDenied) as denied:
        await ledger.reserve("c31", "llm")
    assert denied.value.reason == "llm_window"
    assert ledger.total == 30
    clock.advance(61)
    await ledger.reserve("c31", "llm")
    assert ledger.llm_calls == 31


async def test_snapshot_and_restore_round_trip():
    ledger = BudgetLedger(brake=5)
    await ledger.reserve("c1", "registry", weight=3)
    await ledger.add_usage(100, 20)
    with pytest.raises(BudgetDenied):
        await ledger.reserve("c1", "registry", weight=5)
    copy = BudgetLedger(brake=5)
    copy.restore(ledger.snapshot())
    assert copy.snapshot() == ledger.snapshot()
    assert copy.brake.tripped
