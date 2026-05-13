from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict


@dataclass
class RateLimitDecision:
    allowed: bool
    error_code: str | None = None
    message: str | None = None


class AIEnhanceRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._request_windows: Dict[str, Deque[float]] = defaultdict(deque)
        self._inflight: Dict[str, int] = defaultdict(int)

    @staticmethod
    def enabled() -> bool:
        value = os.getenv("AI_ENHANCE_RATE_LIMIT_ENABLED", "1").strip().lower()
        return value not in {"0", "false", "off", "no"}

    @staticmethod
    def window_seconds() -> int:
        return max(1, int(os.getenv("AI_ENHANCE_RATE_LIMIT_WINDOW_SECONDS", "300")))

    @staticmethod
    def max_requests() -> int:
        return max(1, int(os.getenv("AI_ENHANCE_RATE_LIMIT_MAX_REQUESTS", "10")))

    @staticmethod
    def max_concurrent_requests() -> int:
        return max(1, int(os.getenv("AI_ENHANCE_MAX_CONCURRENT_REQUESTS", "2")))

    @staticmethod
    def build_key(provider: str, mode: str, client_id: str | None) -> str:
        normalized_client = (client_id or "global").strip() or "global"
        return f"{provider}:{mode}:{normalized_client}"

    def acquire(self, key: str) -> RateLimitDecision:
        if not self.enabled():
            return RateLimitDecision(allowed=True)

        now = time.time()
        window_seconds = self.window_seconds()
        max_requests = self.max_requests()
        max_concurrent = self.max_concurrent_requests()

        with self._lock:
            inflight = self._inflight[key]
            if inflight >= max_concurrent:
                return RateLimitDecision(
                    allowed=False,
                    error_code="TOO_MANY_CONCURRENT_REQUESTS",
                    message="AI enhancement is busy. Please wait for the current request to finish before retrying.",
                )

            request_window = self._request_windows[key]
            cutoff = now - window_seconds
            while request_window and request_window[0] < cutoff:
                request_window.popleft()

            if len(request_window) >= max_requests:
                return RateLimitDecision(
                    allowed=False,
                    error_code="RATE_LIMITED",
                    message="AI enhancement request limit reached. Please wait a moment before trying again.",
                )

            request_window.append(now)
            self._inflight[key] += 1
            return RateLimitDecision(allowed=True)

    def release(self, key: str) -> None:
        if not self.enabled():
            return

        with self._lock:
            inflight = self._inflight.get(key, 0)
            if inflight <= 1:
                self._inflight.pop(key, None)
            else:
                self._inflight[key] = inflight - 1


RATE_LIMITER = AIEnhanceRateLimiter()
