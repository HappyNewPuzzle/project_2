# 7단계: 운영 준비와 Docker

## 목표

개발 PC의 Python과 PostgreSQL 설치 상태에 덜 의존하도록 컨테이너 실행 환경을
만들고, 장애 판단과 요청 추적, 기본적인 과도 요청 방어 기능을 추가합니다.

## Docker 이미지

`Dockerfile`은 다음 원칙을 사용합니다.

- 공식 `python:3.12-slim` 기반 이미지
- requirements를 먼저 복사해 dependency layer cache 활용
- `.dockerignore`로 테스트·문서·비밀 `.env` 제외
- 비루트 `app` 사용자로 uvicorn 실행
- exec 형식 CMD로 종료 신호 전달
- Python 표준 라이브러리 기반 liveness HEALTHCHECK

`docker/entrypoint.sh`는 migration 성공 후에만 API를 시작합니다. `.gitattributes`는
Windows Git에서도 이 파일을 LF로 유지해 Linux의 `^M` 실행 오류를 방지합니다.

## Compose 시작 순서

단순 `depends_on`은 컨테이너 프로세스 시작만 기다리고 PostgreSQL이 쿼리를 받을
준비까지 기다리지 않습니다. 따라서 DB에 `pg_isready` healthcheck를 두고 API가
`service_healthy` 조건을 기다립니다.

```text
db running → db healthy → api migration → api serving
```

로컬 단일 API에는 entrypoint migration이 적합합니다. 여러 replica가 동시에 뜨는
운영 환경에서는 migration race를 피하도록 별도 release job에서 한 번만 실행합니다.

## Liveness와 readiness

- `/health/live`: 이벤트 루프와 HTTP 서버가 살아 있는지 확인
- `/health/ready`: PostgreSQL `SELECT 1`이 성공하는지 확인

liveness에 DB를 포함하면 DB 장애 시 모든 API 컨테이너가 재시작되는 악순환이 생길
수 있습니다. 의존성 장애는 readiness로 트래픽에서 제외하는 편이 안전합니다.

## 구조화 로그

`RequestContextMiddleware`는 순수 ASGI middleware라 SSE 스트림을 버퍼링하지 않습니다.

1. `X-Request-ID`를 읽거나 UUID 생성
2. context variable에 저장
3. 응답 헤더에 같은 ID 추가
4. 상태 코드와 처리 시간 기록
5. JSON formatter가 한 줄 로그 출력

같은 request ID로 라우터·서비스·접근 로그를 검색할 수 있습니다.

## Rate limit

sliding-window 제한기는 키별 최근 요청 시각을 deque에 보관합니다.

- auth 키: 클라이언트 IP
- chat 키: 인증된 사용자 UUID
- 초과: 429 + `Retry-After`

이 구현은 학습과 단일 프로세스 보호용입니다. worker 또는 replica가 여러 개면 각자
별도 카운터를 가지므로 Redis 같은 공유 저장소와 원자적 연산이 필요합니다.

## 직접 확인할 코드

1. `Dockerfile`, `compose.yaml`, `docker/entrypoint.sh`
2. `app/api/routes/health.py`
3. `app/core/logging.py`
4. `app/core/middleware.py`
5. `app/core/rate_limit.py`
6. `tests/test_health.py`, `tests/test_rate_limit.py`

## 이후 운영 개선

- CI에서 테스트·migration·Docker build 자동화
- Redis 기반 분산 rate limit
- OpenTelemetry trace/metrics
- secret manager와 배포 환경별 설정
- PostgreSQL backup과 migration rollback 절차
