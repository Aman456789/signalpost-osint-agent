import time
from collections import deque

CHECK_AFTER = 10
TRIP_MINUTES = 38
HARD_STOP_S = 40 * 60


class TimeKillSwitch:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._started = clock()
        self._window: deque[float] = deque(maxlen=CHECK_AFTER + 1)
        self._total = 0
        self.finished = 0
        self.tripped = False

    def start(self) -> None:
        self._started = self._clock()

    def begin_phase(self, total: int) -> None:
        self._total = total
        self.finished = 0
        self._window.clear()
        self._window.append(self._clock())

    def company_finished(self) -> None:
        self.finished += 1
        self._window.append(self._clock())

    def elapsed_s(self) -> float:
        return self._clock() - self._started

    def projected_minutes(self) -> float | None:
        if self.finished < CHECK_AFTER:
            return None
        elapsed_min = self.elapsed_s() / 60
        span_min = (self._window[-1] - self._window[0]) / 60
        if span_min <= 0:
            return elapsed_min
        speed = (len(self._window) - 1) / span_min
        return elapsed_min + (self._total - self.finished) / speed

    def check(self) -> str:
        if self.elapsed_s() >= HARD_STOP_S:
            return "hard_stop"
        if self.tripped:
            return "trip"
        projected = self.projected_minutes()
        if projected is not None and projected > TRIP_MINUTES:
            self.tripped = True
            return "trip"
        return "ok"
