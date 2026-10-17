import httpx
import pytest

from agent_engine.errors import BudgetDenied, SourceUnavailable
from governor.backoff import CircuitBreaker, call_with_retries, retry_delay
from governor.budget_ledger import BudgetLedger
from tests.helpers import FakeClock


def test_delays_double_and_then_stay_at_16():
    assert [retry_delay(i, jitter=lambda: 0) for i in range(6)] == [2, 4, 8, 16, 16, 16]


def test_retry_after_wins_when_longer():
    assert retry_delay(0, retry_after=30, jitter=lambda: 0) == 30
    assert retry_delay(3, retry_after=5, jitter=lambda: 0.5) == 16.5


def test_circuit_opens_after_five_failures_and_allows_one_probe():
    clock = FakeClock()
    breaker = CircuitBreaker(clock=clock)
    for _ in range(5):
        assert breaker.allow()
        breaker.record_failure()
    assert not breaker.allow()
    clock.advance(31)
    assert breaker.allow()
    assert not breaker.allow()  # only one probe at a time
    breaker.record_success()
    assert breaker.allow()


def test_failed_probe_reopens_the_circuit():
    clock = FakeClock()
    breaker = CircuitBreaker(clock=clock)
    for _ in range(5):
        breaker.record_failure()
    clock.advance(31)
    assert breaker.allow()
    breaker.record_failure()
    assert not breaker.allow()
    clock.advance(31)
    assert breaker.allow()


async def test_five_tries_each_reserved_with_growing_delays():
    ledger = BudgetLedger()
    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)

    async def send():
        return httpx.Response(503)

    with pytest.raises(SourceUnavailable):
        await call_with_retries(send, ledger, "c1", "website", sleep=sleep, jitter=lambda: 0)
    assert sleeps == [2, 4, 8, 16]
    assert ledger.snapshot()["requests_by_kind"] == {"website": 1, "retry": 4}


async def test_stops_retrying_once_a_try_succeeds():
    ledger = BudgetLedger()
    answers = iter([httpx.Response(500), httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200)])
    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)

    async def send():
        return next(answers)

    response = await call_with_retries(send, ledger, "c1", "registry", sleep=sleep, jitter=lambda: 0)
    assert response.status_code == 200
    assert sleeps == [2, 7]
    assert ledger.total == 3


async def test_transport_errors_count_as_failures():
    ledger = BudgetLedger()

    async def send():
        raise httpx.ConnectError("boom")

    async def sleep(_):
        return None

    with pytest.raises(SourceUnavailable, match="ConnectError"):
        await call_with_retries(send, ledger, "c1", "registry", max_tries=2, sleep=sleep)
    assert ledger.total == 2


async def test_denied_reservation_sends_nothing():
    ledger = BudgetLedger(brake=1)
    await ledger.reserve("c1", "registry")
    sent = []

    async def send():
        sent.append(1)
        return httpx.Response(200)

    with pytest.raises(BudgetDenied):
        await call_with_retries(send, ledger, "c1", "registry")
    assert sent == []
