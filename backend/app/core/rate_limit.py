"""단일 프로세스용 sliding-window rate limiter."""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache

import redis.asyncio as redis

from app.core.config import get_settings


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

    async def acheck(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int = 60,
    ) -> RateLimitResult:
        """FastAPI async dependency에서 같은 메모리 제한기를 사용할 수 있게 감싼다."""

        return self.check(key, limit=limit, window_seconds=window_seconds)

    def _remove_expired_keys(self, cutoff: float) -> None:
        expired = [
            key
            for key, timestamps in self._requests.items()
            if not timestamps or timestamps[-1] <= cutoff
        ]
        for key in expired:
            self._requests.pop(key, None)


class RedisRateLimiter:
    """여러 API 프로세스가 공유할 수 있는 Redis 기반 sliding-window 제한기."""

    def __init__(self, redis_url: str) -> None:
        # Redis 공식 권장처럼 프로세스 안에서 하나의 async client를 공유한다.
        self._redis = redis.from_url(redis_url, decode_responses=True)

    async def acheck(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int = 60,
    ) -> RateLimitResult:
        """Redis sorted set으로 현재 window 안의 요청 수를 원자적으로 확인한다."""

        now = time.time()
        cutoff = now - window_seconds
        redis_key = f"rate-limit:{key}"
        member = f"{now}:{time.monotonic_ns()}"

        async with self._redis.pipeline(transaction=True) as pipe:
            # 오래된 요청 기록을 지운다.
            pipe.zremrangebyscore(redis_key, 0, cutoff)
            # 현재 요청을 후보로 추가한다.
            pipe.zadd(redis_key, {member: now})
            # 현재 window 안의 요청 수를 센다.
            pipe.zcard(redis_key)
            # 키 만료를 걸어 Redis에 오래된 키가 남지 않게 한다.
            pipe.expire(redis_key, window_seconds)
            results: Sequence[object] = await pipe.execute()

        request_count = int(results[2])
        if request_count <= limit:
            return RateLimitResult(allowed=True)

        # 한도를 넘은 요청은 다시 제거해 초과 요청이 window를 계속 밀지 않게 한다.
        await self._redis.zrem(redis_key, member)
        oldest = await self._redis.zrange(redis_key, 0, 0, withscores=True)
        if not oldest:
            return RateLimitResult(allowed=False, retry_after_seconds=1)
        retry_after = math.ceil(float(oldest[0][1]) + window_seconds - now)
        return RateLimitResult(
            allowed=False,
            retry_after_seconds=max(1, retry_after),
        )

    async def aclose(self) -> None:
        """애플리케이션 종료 시 Redis 연결 풀을 닫는다."""

        await self._redis.aclose()


@lru_cache
def get_rate_limiter() -> InMemoryRateLimiter | RedisRateLimiter:
    """설정에 따라 Redis 또는 메모리 제한기를 하나만 만들어 공유한다."""

    redis_url = get_settings().redis_url
    if redis_url:
        return RedisRateLimiter(redis_url)
    return InMemoryRateLimiter()


async def close_rate_limiter() -> None:
    """애플리케이션 종료 시 외부 연결이 있는 limiter를 정리한다."""

    limiter = get_rate_limiter()
    if isinstance(limiter, RedisRateLimiter):
        await limiter.aclose()
    get_rate_limiter.cache_clear()
