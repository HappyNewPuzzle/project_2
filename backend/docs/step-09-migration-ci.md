# 9단계: CI에서 PostgreSQL migration 검증

이번 단계의 목표는 GitHub Actions에서 실제 PostgreSQL을 띄운 뒤 Alembic migration을
적용해 보는 것입니다. 단위 테스트와 Docker build만으로는 “DB 구조 변경 파일이 실제
DB에 적용되는가?”를 완전히 확인하기 어렵기 때문에 별도의 migration job을 추가했습니다.

## 이번 단계에서 수정한 파일

- [.github/workflows/backend-ci.yml](../../.github/workflows/backend-ci.yml)
  - `migration` job을 추가했습니다.
  - PostgreSQL 17 service container를 실행합니다.
  - `alembic upgrade head`로 모든 migration을 빈 DB에 적용합니다.
  - `alembic current`로 최종 revision을 로그에 남깁니다.

- [backend/README.md](../README.md)
  - 현재 단계를 9단계로 갱신했습니다.
  - CI 검증 범위에 migration을 추가했습니다.

- [backend/docs/README.md](README.md)
  - 9단계 문서 링크를 추가했습니다.

- [backend/docs/architecture.md](architecture.md)
  - CI 검증 흐름에 migration job을 추가했습니다.

## 왜 migration 검증이 필요한가?

서비스가 작을 때는 DB 테이블을 직접 만들거나 로컬에서만 migration을 실행해도 큰 문제가
없어 보입니다. 하지만 기능이 늘어나면 다음 문제가 생길 수 있습니다.

- migration 파일 순서가 꼬입니다.
- ORM 모델과 실제 테이블 구조가 달라집니다.
- 개발자의 로컬 DB에는 이미 테이블이 있어서 오류가 숨겨집니다.
- Docker image는 빌드되지만 배포 시작 시 `alembic upgrade head`에서 실패합니다.

CI에서 빈 PostgreSQL을 새로 띄우고 migration을 처음부터 끝까지 적용하면 이런 문제를
더 빨리 발견할 수 있습니다.

## migration job 흐름

```text
test job 성공
  → PostgreSQL 17 service container 시작
  → healthcheck 통과 대기
  → Python 3.12 설치
  → requirements.txt 설치
  → alembic upgrade head
  → alembic current
```

`docker-build` job은 이제 `test`와 `migration`이 모두 통과해야 실행됩니다.

```text
test ─┐
      ├─ docker-build
migration ┘
```

이렇게 배치한 이유는 Docker 이미지 빌드를 하기 전에 코드 테스트와 DB 구조 검증을 먼저
끝내기 위해서입니다.

## service container 설정

workflow에는 다음 PostgreSQL service가 추가되었습니다.

```yaml
services:
  postgres:
    image: postgres:17-alpine
    env:
      POSTGRES_DB: character_chat
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - 5432:5432
    options: >-
      --health-cmd "pg_isready -U postgres -d character_chat"
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

GitHub-hosted runner에서 직접 실행하는 job은 service container에 접근하기 위해 포트 매핑을
사용합니다. 그래서 Alembic의 `DATABASE_URL`은 다음처럼 `localhost`를 가리킵니다.

```text
postgresql+asyncpg://postgres:postgres@localhost:5432/character_chat
```

## Alembic 설정과 연결되는 방식

[backend/alembic/env.py](../alembic/env.py)는 `get_settings().database_url` 값을 읽어
Alembic의 `sqlalchemy.url`로 사용합니다. 그래서 CI job에서 `DATABASE_URL` 환경 변수를
넣어주면 migration은 테스트용 PostgreSQL에 적용됩니다.

```yaml
env:
  DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/character_chat
```

이 방식의 장점은 로컬, Docker Compose, CI가 모두 같은 설정 경로를 사용한다는 점입니다.
설정이 여러 군데로 갈라지지 않기 때문에 운영 전환 때 실수를 줄일 수 있습니다.

## 이번 단계의 한계

이번 단계는 “빈 DB에 migration이 적용되는지”를 확인합니다. 아직 다음 항목은 검증하지
않습니다.

- 이전 버전 DB에서 새 버전 DB로 업그레이드하는 시나리오
- `alembic downgrade` 검증
- 실제 API 서버를 띄운 뒤 `/health/ready`까지 호출하는 통합 테스트
- 테스트 데이터 seed 후 repository/API까지 연결하는 end-to-end 테스트

다음 운영 단계에서 이 범위를 조금씩 넓힐 수 있습니다.
