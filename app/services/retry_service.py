from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class RetryService:
    def __init__(self, *, max_attempts: int = 3, base_delay_seconds: float = 1.0, jitter_seconds: float = 0.25) -> None:
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds
        self.jitter_seconds = jitter_seconds

    def run(self, func: Callable[[], T], *, should_retry: Callable[[Exception], bool], on_retry: Callable[[int, Exception, float], None] | None = None) -> T:
        attempt = 1
        while True:
            try:
                return func()
            except Exception as exc:  # noqa: BLE001
                if attempt >= self.max_attempts or not should_retry(exc):
                    raise
                delay = (self.base_delay_seconds * (2 ** (attempt - 1))) + random.uniform(0, self.jitter_seconds)
                if on_retry:
                    on_retry(attempt, exc, delay)
                time.sleep(delay)
                attempt += 1
