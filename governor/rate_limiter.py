import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self, limit: int = 30, window_s: float = 60.0, clock=time.monotonic):
        self._limit = limit
        self._window_s = window_s
        self._clock = clock
        self._calls: deque[float] = deque()

    def _drop_old(self) -> None:
        cutoff = self._clock() - self._window_s
        while self._calls and self._calls[0] <= cutoff:
            self._calls.popleft()

    def try_acquire(self, count: int = 1) -> bool:
        self._drop_old()
        if len(self._calls) + count > self._limit:
            return False
        now = self._clock()
        self._calls.extend([now] * count)
        return True

    def wait_seconds(self) -> float:
        self._drop_old()
        if len(self._calls) < self._limit:
            return 0.0
        return self._calls[0] + self._window_s - self._clock()
