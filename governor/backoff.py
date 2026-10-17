import asyncio
import random
import time

import httpx

from agent_engine.errors import BudgetDenied, SourceUnavailable

RETRY_DELAYS = (2, 4, 8, 16)
MAX_TRIES = 5
MAX_RETRY_AFTER_S = 60  # a hostile Retry-After must not eat the 45-minute budget


def retry_delay(retry_index: int, retry_after: float | None = None, jitter=random.random) -> float:
    base = RETRY_DELAYS[min(retry_index, len(RETRY_DELAYS) - 1)] + jitter()
    return max(base, retry_after or 0)


def parse_retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After", "").strip()
    if not value.isdigit():
        return None
    return min(float(value), MAX_RETRY_AFTER_S)


class CircuitBreaker:
    def __init__(self, failure_limit: int = 5, pause_s: float = 30.0, clock=time.monotonic):
        self._failure_limit = failure_limit
        self._pause_s = pause_s
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._probing = False

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if self._probing or self._clock() - self._opened_at < self._pause_s:
            return False
        self._probing = True  # pause is over: let exactly one request through
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._probing = False

    def record_failure(self) -> None:
        self._failures += 1
        if self._probing or self._failures >= self._failure_limit:
            self._opened_at = self._clock()
            self._probing = False

    def cancel_probe(self) -> None:
        self._probing = False


async def call_with_retries(
    send,
    ledger,
    company_id: str,
    kind: str,
    *,
    breaker: CircuitBreaker | None = None,
    max_tries: int = MAX_TRIES,
    optional: bool = False,
    sleep=asyncio.sleep,
    jitter=random.random,
) -> httpx.Response:
    """Every try is reserved first. 429 and 5xx count as failures; anything else is returned."""
    last_error = "no_attempt"
    for attempt in range(max_tries):
        if breaker and not breaker.allow():
            raise SourceUnavailable("circuit_open")
        try:
            await ledger.reserve(company_id, kind if attempt == 0 else "retry", optional=optional)
        except BudgetDenied:
            if breaker:
                breaker.cancel_probe()
            raise

        retry_after = None
        try:
            response = await send()
        except httpx.TransportError as exc:
            last_error = type(exc).__name__
        else:
            if response.status_code != 429 and response.status_code < 500:
                if breaker:
                    breaker.record_success()
                return response
            last_error = f"http_{response.status_code}"
            retry_after = parse_retry_after(response)

        if breaker:
            breaker.record_failure()
        if attempt + 1 < max_tries:
            await sleep(retry_delay(attempt, retry_after, jitter))
    raise SourceUnavailable(last_error)
