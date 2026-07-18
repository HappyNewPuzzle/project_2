"""인메모리 sliding-window rate limiter의 경계 동작을 검증한다."""

from app.core.config import get_settings
from app.core.rate_limit import InMemoryRateLimiter, RedisRateLimiter, get_rate_limiter


class FakeClock:
    """테스트가 실제 시간을 기다리지 않도록 제어 가능한 시계를 제공한다."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_rate_limit_blocks_and_recovers_after_window() -> None:
    """허용량 초과 시 차단되고 window가 지나면 다시 허용되는지 확인한다."""

    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)

    assert limiter.check("user:1", limit=2).allowed
    assert limiter.check("user:1", limit=2).allowed

    blocked = limiter.check("user:1", limit=2)
    assert not blocked.allowed
    assert blocked.retry_after_seconds == 60

    clock.now = 61.0
    assert limiter.check("user:1", limit=2).allowed


def test_rate_limits_are_isolated_by_key() -> None:
    """한 사용자의 초과가 다른 사용자의 요청을 막지 않는지 확인한다."""

    limiter = InMemoryRateLimiter(clock=lambda: 0.0)

    assert limiter.check("user:1", limit=1).allowed
    assert not limiter.check("user:1", limit=1).allowed
    assert limiter.check("user:2", limit=1).allowed


def test_rate_limiter_uses_memory_without_redis_url(monkeypatch) -> None:
    """REDIS_URL이 없으면 기존 단일 프로세스 limiter를 선택한다."""

    get_settings.cache_clear()
    get_rate_limiter.cache_clear()
    monkeypatch.delenv("REDIS_URL", raising=False)

    assert isinstance(get_rate_limiter(), InMemoryRateLimiter)

    get_settings.cache_clear()
    get_rate_limiter.cache_clear()


def test_rate_limiter_uses_redis_when_url_is_configured(monkeypatch) -> None:
    """REDIS_URL이 있으면 Redis 기반 limiter를 선택한다."""

    get_settings.cache_clear()
    get_rate_limiter.cache_clear()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    limiter = get_rate_limiter()
    assert isinstance(limiter, RedisRateLimiter)

    get_settings.cache_clear()
    get_rate_limiter.cache_clear()
