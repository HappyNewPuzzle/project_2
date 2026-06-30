"""단일 프로세스용 sliding-window rate limiter."""

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """요청 허용 여부와 거부 시 재시도 가능 시간."""

    allowed: bool
    retry_after_seconds: int = 0


class InMemoryRateLimiter:
    """키별 최근 요청 시각을 메모리에 보관하는 sliding-window 제한기."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._requests: dict[str, deque[float]] = {}
        # sync/async 요청과 여러 스레드가 같은 dict를 안전하게 공유한다.
        self._lock = threading.Lock()
        self._checks = 0

    def check(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int = 60,
    ) -> RateLimitResult:
        """현재 요청을 기록하거나, 한도 초과 시 Retry-After를 계산한다."""

        now = self._clock()
        cutoff = now - window_seconds
        with self._lock:
            timestamps = self._requests.setdefault(key, deque())
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= limit:
                retry_after = math.ceil(
                    timestamps[0] + window_seconds - now
                )
                return RateLimitResult(
                    allowed=False,
                    retry_after_seconds=max(1, retry_after),
                )

            timestamps.append(now)
            self._checks += 1
            # 사용이 끝난 키가 무한히 쌓이지 않도록 가끔 전체를 청소한다.
            if self._checks % 1000 == 0:
                self._remove_expired_keys(cutoff)
            return RateLimitResult(allowed=True)

    def _remove_expired_keys(self, cutoff: float) -> None:
        expired = [
            key
            for key, timestamps in self._requests.items()
            if not timestamps or timestamps[-1] <= cutoff
        ]
        for key in expired:
            self._requests.pop(key, None)


@lru_cache
def get_rate_limiter() -> InMemoryRateLimiter:
    """애플리케이션 프로세스에서 하나의 제한 상태를 공유한다."""

    return InMemoryRateLimiter()
