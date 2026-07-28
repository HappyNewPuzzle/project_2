# 31단계: HttpOnly refresh token 회전과 자동 세션 갱신

이번 단계의 목표는 access token이 만료될 때 사용자를 즉시 로그아웃시키는 대신,
서버가 관리하는 refresh session으로 짧은 access token을 자동 재발급하는 것입니다.
refresh token 원문은 JavaScript에 노출하지 않고 HttpOnly 쿠키에만 저장하며, DB에는
SHA-256 해시만 저장합니다.

## 주요 변경 파일

- [backend/app/db/models.py](../app/db/models.py)
  - `RefreshSession` 모델과 사용자 관계를 추가합니다.
- [backend/alembic/versions/20260728_0008_add_refresh_sessions.py](../alembic/versions/20260728_0008_add_refresh_sessions.py)
  - refresh session 테이블과 조회 index를 생성합니다.
- [backend/app/repositories/refresh_session_repository.py](../app/repositories/refresh_session_repository.py)
  - token hash 잠금 조회, 생성, family 폐기 SQL을 담당합니다.
- [backend/app/services/auth_service.py](../app/services/auth_service.py)
  - 로그인 발급, token 회전, 재사용 탐지, 로그아웃 폐기를 조정합니다.
- [backend/app/api/routes/auth.py](../app/api/routes/auth.py)
  - HttpOnly 쿠키와 `/auth/refresh`, `/auth/logout` 계약을 제공합니다.
- [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts)
  - 401에서 한 번만 refresh하고 원래 요청을 재시도합니다.
- [frontend/src/App.tsx](../../frontend/src/App.tsx)
  - 갱신된 access token을 저장하고 실제 사용자 전환 때만 화면 상태를 초기화합니다.

## access token과 refresh token의 역할

```text
access token
  짧은 수명의 서명된 JWT
  Authorization header로 보호 API에 전달
  현재 단계에서는 새로고침 유지를 위해 localStorage에 저장

refresh token
  의미 없는 고난도 난수(opaque token)
  HttpOnly 쿠키로만 전달
  DB에는 원문 대신 SHA-256 hash 저장
  새로운 access token 발급에 한 번만 사용
```

refresh token까지 localStorage에 넣으면 XSS가 발생했을 때 장기 세션 수단을
JavaScript가 바로 읽을 수 있습니다. HttpOnly는 스크립트의 쿠키 읽기를 막지만,
브라우저가 요청에 쿠키를 첨부하는 동작 자체는 허용합니다.

## DB 구조

```text
refresh_sessions
  id          UUID PK
  family_id   한 번의 로그인에서 이어진 회전 묶음
  user_id     users.id FK
  token_hash  SHA-256 hex, UNIQUE
  expires_at  절대 만료 시각
  revoked_at  사용·로그아웃·탈취 탐지 시 폐기 시각
  created_at  생성 시각
```

`family_id`가 필요한 이유는 token 한 개가 아니라 한 로그인 흐름 전체를 폐기하기
위해서입니다. 사용자가 두 기기에서 로그인하면 서로 다른 family가 만들어지므로,
한 기기의 로그아웃이 다른 기기 세션까지 무조건 종료시키지 않습니다.

## 로그인 흐름

```text
POST /auth/login
  → email/password 검증
  → access JWT 생성
  → opaque refresh token 생성
  → token hash와 새 family_id를 DB에 저장
  → access token은 JSON 응답
  → refresh token은 HttpOnly 쿠키
```

쿠키는 `/auth` 경로에만 전송됩니다. 따라서 캐릭터나 채팅 API 요청에는 장기 token이
불필요하게 포함되지 않습니다.

## 회전과 재사용 탐지

```text
POST /auth/refresh
  → 쿠키 원문의 SHA-256 hash 계산
  → SELECT ... FOR UPDATE로 행 잠금
  → 기존 행 revoked_at 설정
  → 같은 family_id의 새 refresh session 생성
  → transaction commit
  → 새 access token과 새 HttpOnly 쿠키 반환
```

행 잠금은 같은 token을 사용한 동시 요청 두 개가 모두 성공하는 것을 막습니다.
프론트엔드도 여러 보호 API가 동시에 401을 받아도 하나의 `refreshPromise`를 공유해
불필요한 회전 충돌을 줄입니다.

이미 `revoked_at`이 있는 token이 다시 들어오면 탈취된 token일 가능성이 있습니다.
이때는 같은 family의 활성 session을 모두 폐기하고 다시 로그인하도록 합니다.

```text
정상 회전: old(revoked) → new(active)
old token 재사용 감지
  → old와 new가 속한 family 전체 revoke
  → HTTP 401
```

## 로그아웃

`POST /auth/logout`은 현재 쿠키의 family 전체를 폐기하고 브라우저 쿠키를 만료시킵니다.
알 수 없는 token도 성공으로 처리해 외부에서 token 존재 여부를 추측하지 못하게 합니다.

네트워크 장애로 서버 폐기에 실패하더라도 프론트엔드는 현재 브라우저의 access token과
사용자 데이터를 제거합니다. 서버 쪽 세션은 만료 시각까지 남을 수 있으므로 운영
환경에서는 로그아웃 실패 로그와 재시도 정책도 관찰해야 합니다.

## 프론트엔드 자동 갱신

```text
보호 API 요청
  → 2xx: 기존 처리 계속
  → 401:
      POST /auth/refresh (credentials: include)
      → 성공: ApiClient token 교체
              원래 요청을 새 Bearer token으로 1회 재시도
      → 실패: 세션과 사용자 화면 상태 초기화
```

재시도는 한 번만 허용해 refresh 실패와 권한 문제에서 무한 요청이 생기지 않게 합니다.
로그인 실패의 401은 자격 증명 오류이므로 자동 refresh와 세션 초기화 대상에서
제외합니다.

access token이 자동 갱신될 때 React workspace를 remount하면 작성 중인 채팅까지
사라집니다. 그래서 token 문자열 대신 `sessionGeneration`을 사용하고, 로그인·로그아웃
같은 실제 사용자 전환 때만 값을 증가시킵니다.

## CORS와 쿠키 설정

브라우저가 다른 포트의 API와 쿠키를 주고받으려면 두 조건이 모두 필요합니다.

```text
프론트 fetch: credentials: "include"
백엔드 CORS: allow_credentials=True
```

개발 기본값은 `SameSite=Lax`, `Secure=false`입니다. HTTPS 운영 환경에서는 최소한
다음처럼 설정해야 합니다.

```env
REFRESH_COOKIE_SECURE=true
REFRESH_COOKIE_SAMESITE=lax
```

프론트와 API가 서로 다른 site라서 `SameSite=None`이 필요하면 `Secure=true`를 함께
사용해야 합니다. 쿠키 기반 endpoint를 cross-site로 열 때는 허용 origin을 정확히
제한하고 Origin 검증 또는 CSRF token 같은 방어를 추가해야 합니다.

## 실행과 테스트

마이그레이션과 백엔드 테스트:

```powershell
cd backend
docker compose build api
docker compose run --rm `
  -e PYTHONPATH=/app `
  -e REDIS_URL= `
  -e RUN_DB_INTEGRATION=1 `
  -v ${PWD}/tests:/app/tests `
  api pytest -q
```

프론트엔드 테스트:

```powershell
cd frontend
npm test
npm run build
```

검증 범위:

- 로그인 응답의 HttpOnly refresh 쿠키
- refresh 시 access token과 쿠키 회전
- 로그아웃 쿠키 만료
- 실제 PostgreSQL의 token hash 저장과 회전
- 이미 사용한 token 재사용 시 family 전체 폐기
- 보호 API 401 후 refresh와 원 요청 재시도
- refresh 실패 시 기존 401 세션 초기화
- 인증 요청의 `credentials: include`

## 현재 한계와 다음 단계

- access token은 아직 localStorage에 있어 XSS 위험이 남아 있습니다.
- refresh cookie 운영 설정과 CSRF 방어는 배포 topology에 맞춰 강화해야 합니다.
- 사용자가 기기별 활성 세션을 보고 개별 폐기하는 API는 아직 없습니다.
- 브라우저 실제 쿠키·CORS 동작은 단위 테스트 외 E2E 검증이 필요합니다.

32단계 후보는 Playwright 기반 브라우저 E2E 테스트입니다. 회원가입부터 로그인,
캐릭터 선택, 세션 자동 갱신, 로그아웃까지 실제 브라우저와 API를 함께 검증할 수
있습니다.
