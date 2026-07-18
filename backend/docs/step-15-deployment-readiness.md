# 15단계: 배포 전 환경 점검

이번 단계의 목표는 실제 배포 전에 위험한 기본값이 남아 있지 않은지 빠르게 확인하는
안전장치를 추가하는 것입니다. 아직 특정 클라우드에 배포하지는 않고, 어디에 배포하든 공통으로
확인해야 할 환경 설정을 점검합니다.

## 이번 단계에서 추가·수정한 파일

- [backend/scripts/check_deploy_env.py](../scripts/check_deploy_env.py)
  - `DATABASE_URL`, `JWT_SECRET_KEY`, `OPENAI_API_KEY`, `CORS_ALLOWED_ORIGINS`, `LOG_JSON`을 점검합니다.
  - 개발 허용 모드와 운영 엄격 모드를 구분합니다.

- [.github/workflows/backend-ci.yml](../../.github/workflows/backend-ci.yml)
  - CI에서 점검 스크립트를 개발 허용 모드로 실행해 문법과 설정 로딩을 확인합니다.

- [backend/Dockerfile](../Dockerfile)
  - 컨테이너 안에서도 점검 스크립트를 실행할 수 있도록 `scripts/`를 이미지에 포함했습니다.

- [backend/README.md](../README.md)
  - 현재 단계를 15단계로 갱신했습니다.

## 로컬 개발 점검

개발 중에는 OpenAI API 키나 운영 JWT secret이 없을 수 있습니다. 이때는 허용 플래그를 붙여
설정 로딩과 기본 구조만 확인합니다.

```powershell
cd backend
python scripts/check_deploy_env.py --allow-missing-openai --allow-dev-secret
```

## 운영 배포 전 점검

운영 배포 전에는 더 엄격하게 실행합니다.

```powershell
cd backend
python scripts/check_deploy_env.py --production
```

운영 모드에서는 다음 조건을 실패로 처리합니다.

- `DATABASE_URL`이 `postgresql+asyncpg://`로 시작하지 않음
- `JWT_SECRET_KEY`가 문서에 적힌 개발용 값 그대로임
- `OPENAI_API_KEY`가 없음
- `CORS_ALLOWED_ORIGINS`에 `*`가 포함됨
- 운영 CORS origin이 localhost를 가리킴

## Docker 컨테이너에서 점검

Docker 이미지 안에서도 같은 스크립트를 실행할 수 있습니다.

```powershell
docker run --rm `
  -e DATABASE_URL="postgresql+asyncpg://postgres:postgres@db:5432/character_chat" `
  -e JWT_SECRET_KEY="replace-this-with-a-long-random-production-secret" `
  -e OPENAI_API_KEY="sk-..." `
  -e CORS_ALLOWED_ORIGINS="https://your-frontend.example.com" `
  ai-character-chat-backend:ci `
  python scripts/check_deploy_env.py --production
```

## 배포 전 체크리스트

배포 전에 최소한 다음을 확인합니다.

1. `JWT_SECRET_KEY`를 긴 무작위 값으로 교체했다.
2. `OPENAI_API_KEY`를 실제 운영 secret으로 주입했다.
3. `DATABASE_URL`이 운영 PostgreSQL을 가리킨다.
4. `CORS_ALLOWED_ORIGINS`에는 실제 프론트엔드 도메인만 들어 있다.
5. `LOG_JSON=true`로 로그 수집이 쉽다.
6. `alembic upgrade head`가 배포 시작 전에 실행된다.
7. `/health/live`, `/health/ready`가 배포 플랫폼 health check에 연결된다.
8. `docker compose down -v` 같은 데이터 삭제 명령은 운영에서 사용하지 않는다.

## 이번 단계의 한계

- 실제 클라우드 배포 workflow는 아직 없습니다.
- secret manager, container registry, domain/TLS 설정은 아직 연결하지 않았습니다.
- Redis, object storage, observability SaaS 같은 외부 운영 컴포넌트는 아직 없습니다.

여기까지가 “로컬 개발에서 배포 준비 전 단계까지”의 1차 백엔드/프론트엔드 골격입니다.
