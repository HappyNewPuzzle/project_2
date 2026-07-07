# 8단계: GitHub Actions CI 자동 검증

이번 단계의 목표는 코드를 GitHub에 올릴 때마다 백엔드가 기본적으로 깨지지 않았는지
자동으로 확인하는 것입니다. 아직 배포 자동화까지는 하지 않고, 테스트와 Docker 빌드
검증에 집중합니다.

## 이번 단계에서 추가한 파일

- [.github/workflows/backend-ci.yml](../../.github/workflows/backend-ci.yml)
  - push, pull request, 수동 실행 시 백엔드 CI를 실행합니다.
  - Python 3.12 환경에서 `pytest -q`를 실행합니다.
  - 테스트가 통과하면 Docker 이미지 빌드까지 확인합니다.

## 왜 CI를 먼저 추가하나?

서비스 기능이 늘어나면 “내 컴퓨터에서는 됐는데 GitHub에 올린 뒤 깨지는” 상황이
쉽게 생깁니다. CI는 그런 실수를 일찍 잡아주는 안전망입니다.

특히 이 프로젝트는 다음 요소가 함께 움직입니다.

- FastAPI 라우터
- SQLAlchemy 모델과 repository
- JWT 인증
- 장기 기억 로직
- Dockerfile

CI를 붙이면 이후 단계에서 기능을 추가할 때마다 최소한 다음 두 가지를 자동으로
확인할 수 있습니다.

1. 테스트 코드가 모두 통과하는가?
2. Docker 이미지가 빌드 가능한가?

## 워크플로 실행 조건

```yaml
on:
  push:
    branches: ["main"]
    paths:
      - "backend/**"
      - ".github/workflows/backend-ci.yml"
  pull_request:
    branches: ["main"]
    paths:
      - "backend/**"
      - ".github/workflows/backend-ci.yml"
  workflow_dispatch:
```

이 설정은 백엔드 코드나 CI 설정이 바뀔 때만 실행되도록 범위를 제한합니다. 문서나
프론트엔드만 바뀌는 상황에서는 불필요한 백엔드 검증을 줄일 수 있습니다.

`workflow_dispatch`는 GitHub Actions 화면에서 사람이 직접 다시 실행할 수 있게 하는
옵션입니다. 네트워크 문제처럼 일시적인 실패가 있었을 때 유용합니다.

## 테스트 job 구조

`test` job은 다음 순서로 동작합니다.

```text
checkout
  → Python 3.12 설치
  → pip 캐시 준비
  → requirements.txt 설치
  → pytest -q 실행
```

테스트용 환경 변수도 workflow 안에 명시했습니다.

```yaml
JWT_SECRET_KEY: ci-test-secret-key-change-me-please-keep-long
DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/character_chat
OPENAI_API_KEY: ""
LOG_JSON: "false"
```

현재 테스트는 외부 LLM과 실제 DB 접속을 대부분 가짜 객체로 대체합니다. 그래서
GitHub Secrets에 실제 OpenAI API 키를 등록하지 않아도 CI가 돌 수 있습니다.

## Docker build job 구조

`docker-build` job은 `test` job이 성공한 뒤 실행됩니다.

```text
test 성공
  → checkout
  → docker build --tag ai-character-chat-backend:ci .
```

여기서는 이미지를 registry에 push하지 않습니다. 아직 배포 단계가 아니기 때문에
Dockerfile과 빌드 컨텍스트가 정상인지 확인하는 데만 목적이 있습니다.

## 왜 compose up까지 하지 않았나?

이번 단계에서는 “빠르고 안정적인 기본 검증”을 우선했습니다. `docker compose up`으로
실제 PostgreSQL까지 띄우는 통합 테스트는 더 실제 환경에 가깝지만, 실행 시간이 늘고
실패 원인이 복잡해집니다.

후속 단계에서 다음 검증을 추가할 수 있습니다.

- PostgreSQL service container를 붙인 migration 테스트
- `alembic upgrade head` 자동 검증
- `/health/ready` 통합 테스트
- Docker image registry push
- 배포 환경별 CD workflow

## 로컬에서 비슷하게 확인하는 방법

PowerShell에서 다음 명령을 실행하면 CI와 거의 같은 검증을 로컬에서도 해볼 수 있습니다.

```powershell
cd backend
pytest -q
docker build --tag ai-character-chat-backend:local .
```

현재 작업 환경에서 Windows Python 실행이 제한될 수 있다면 Docker 이미지 안에서 테스트를
실행하는 방식도 사용할 수 있습니다.

```powershell
docker build --tag ai-character-chat-backend:local .
docker run --rm `
  --entrypoint python `
  --mount "type=bind,source=$((Get-Location).Path),target=/workspace,readonly" `
  --workdir /workspace `
  ai-character-chat-backend:local `
  -m pytest -q
```

## 이번 단계의 한계

- 실제 PostgreSQL service container를 사용한 통합 테스트는 아직 없습니다.
- Alembic migration을 CI에서 직접 실행하지는 않습니다.
- Docker 이미지를 GitHub Container Registry에 push하지 않습니다.
- 배포 자동화는 아직 포함하지 않습니다.

즉, 이번 단계는 “코드와 이미지가 기본적으로 살아 있는지 확인하는 안전망”입니다.
