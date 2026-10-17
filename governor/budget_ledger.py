import asyncio
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from agent_engine.errors import BudgetDenied
from governor.rate_limiter import SlidingWindowLimiter
from governor.request_brake import RequestBrake

KINDS = ("registry", "website", "redirect_hop", "retry", "plan_b", "llm")


@dataclass(frozen=True)
class Grant:
    company_id: str
    kind: str
    weight: int


class BudgetLedger:
    def __init__(self, soft_cap=1700, brake=1950, per_company_cap=14, limiter=None):
        self.soft_cap = soft_cap
        self.brake_limit = brake
        self.per_company_cap = per_company_cap
        self.limiter = limiter or SlidingWindowLimiter()
        self.brake = RequestBrake()
        self.soft_cap_reached = False
        self.kill_switch_tripped = False
        self.halted = False
        self.llm_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = Decimal("0")
        self._total = 0
        self._by_kind: Counter = Counter()
        self._by_company: Counter = Counter()
        self._lock = asyncio.Lock()

    @property
    def total(self) -> int:
        return self._total

    def company_requests(self, company_id: str) -> int:
        return self._by_company[company_id]

    async def reserve(self, company_id: str, kind: str, weight: int = 1, optional: bool = False) -> Grant:
        if kind not in KINDS or weight < 1:
            raise ValueError(f"bad reservation: kind={kind!r} weight={weight}")
        async with self._lock:
            self._check(company_id, kind, weight, optional)
            self._total += weight
            self._by_kind[kind] += weight
            self._by_company[company_id] += weight
            if kind == "llm":
                self.llm_calls += weight
            if self._total >= self.soft_cap:
                self.soft_cap_reached = True
        return Grant(company_id, kind, weight)

    def _check(self, company_id: str, kind: str, weight: int, optional: bool) -> None:
        if self.halted:
            raise BudgetDenied("halted")
        # no browser kind exists (Playwright is not built), so the kill switch blocks plan_b here
        if self.kill_switch_tripped and kind == "plan_b":
            raise BudgetDenied("kill_switch")
        if self.brake.tripped or self._total + weight > self.brake_limit:
            self.brake.trip()
            raise BudgetDenied("request_brake")
        if (optional or kind == "plan_b") and self._total + weight > self.soft_cap:
            self.soft_cap_reached = True
            raise BudgetDenied("soft_cap")
        if self._by_company[company_id] + weight > self.per_company_cap:
            raise BudgetDenied("per_company_cap")
        if kind == "llm" and not self.limiter.try_acquire(weight):
            raise BudgetDenied("llm_window")

    async def add_usage(self, input_tokens: int, output_tokens: int, cost_usd: Decimal = Decimal("0")) -> None:
        async with self._lock:
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens
            self.cost_usd += cost_usd

    def trip_kill_switch(self) -> None:
        self.kill_switch_tripped = True

    def halt(self) -> None:
        self.halted = True

    def snapshot(self) -> dict:
        return {
            "total_outbound_requests": self._total,
            "requests_by_kind": dict(self._by_kind),
            "per_company_requests": dict(self._by_company),
            "brake_tripped": self.brake.tripped,
            "soft_cap_reached": self.soft_cap_reached,
            "kill_switch_tripped": self.kill_switch_tripped,
            "llm_calls": self.llm_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": str(self.cost_usd),
        }

    def restore(self, data: dict) -> None:
        self._total = data.get("total_outbound_requests", 0)
        self._by_kind = Counter(data.get("requests_by_kind", {}))
        self._by_company = Counter(data.get("per_company_requests", {}))
        self.soft_cap_reached = data.get("soft_cap_reached", False)
        self.kill_switch_tripped = data.get("kill_switch_tripped", False)
        self.llm_calls = data.get("llm_calls", 0)
        self.input_tokens = data.get("input_tokens", 0)
        self.output_tokens = data.get("output_tokens", 0)
        self.cost_usd = Decimal(data.get("estimated_cost_usd", "0"))
        if data.get("brake_tripped"):
            self.brake.trip()
