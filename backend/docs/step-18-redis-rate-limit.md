# 18단계: Redis 기반 rate limit 준비

이번 단계의 목표는 단일 프로세스 메모리 rate limit을 Redis 기반으로 확장할 수 있게 만드는
것입니다.

## 추가·수정한 파일

- [backend/app/core/rate_limit.py](../app/core/rate_limit.py)
  - 기존 `InMemoryRateLimiter`를 유지했습니다.
  - `RedisRateLimiter`를 추가했습니다.
  - `REDIS_URL`이 있으면 Redis limiter, 없으면 memory limiter를 선택합니다.

- [backend/app/api/dependencies.py](../app/api/dependencies.py)
  - rate limit dependency를 async로 바꿨습니다.

- [backend/compose.yaml](../compose.yaml)
  - Redis service를 추가했습니다.

- [backend/requirements.txt](../requirements.txt)
  - `redis` 패키지를 추가했습니다.

## 왜 Redis가 필요한가?

메모리 limiter는 API 프로세스 하나 안에서만 상태를 공유합니다. API 컨테이너가 여러 개가
되면 각 컨테이너가 서로 다른 요청 카운터를 갖게 됩니다.

```text
API container A: user 요청 30회
API container B: user 요청 30회
실제 전체 요청: 60회
```

Redis를 사용하면 모든 API 프로세스가 같은 카운터를 공유할 수 있습니다.

## 동작 방식

```text
REDIS_URL 있음
  → RedisRateLimiter

REDIS_URL 없음
  → InMemoryRateLimiter
```

Redis limiter는 sorted set을 사용합니다.

```text
오래된 timestamp 삭제
현재 요청 timestamp 추가
현재 window 요청 수 계산
limit 초과 시 방금 추가한 요청 제거
Retry-After 계산
```

## 참고

Redis 공식 문서 기준으로 async 애플리케이션에서는 `redis.asyncio` client를 공유하고,
애플리케이션 종료 시 `aclose()`로 닫는 방식을 사용했습니다.

출처: https://redis.io/docs/latest/develop/clients/redis-py/async/

## 한계

- Redis 장애 시 memory fallback을 자동으로 수행하지는 않습니다.
- Redis 통합 테스트는 아직 CI에 추가하지 않았습니다.
- 더 엄격한 원자성이 필요하면 Lua script 방식으로 개선할 수 있습니다.
