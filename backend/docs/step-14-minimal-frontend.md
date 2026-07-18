# 14단계: 최소 프론트엔드 채팅 UI

이번 단계의 목표는 백엔드 API를 브라우저에서 직접 확인할 수 있는 최소 UI를 추가하는
것입니다. 아직 React 같은 프레임워크는 쓰지 않고, HTML 파일 하나로 회원가입, 로그인,
캐릭터 생성, 기억 저장, 스트리밍 채팅을 테스트합니다.

## 이번 단계에서 추가·수정한 파일

- [frontend/index.html](../../frontend/index.html)
  - 정적 HTML/CSS/JavaScript 프론트엔드입니다.
  - `/auth/register`, `/auth/login`, `/characters`, `/memories`, `/chat/stream`을 호출합니다.
  - POST 기반 SSE 스트리밍을 `fetch()`와 `ReadableStream`으로 처리합니다.

- [frontend/README.md](../../frontend/README.md)
  - 프론트엔드 실행 방법과 사용 순서를 정리했습니다.

- [backend/app/core/config.py](../app/core/config.py)
  - 개발용 프론트엔드 origin 목록인 `cors_allowed_origins` 설정을 추가했습니다.

- [backend/app/main.py](../app/main.py)
  - FastAPI `CORSMiddleware`를 추가했습니다.

## 왜 정적 HTML부터 시작하나?

프론트엔드 프레임워크를 바로 붙이면 상태 관리, 라우팅, 빌드 설정, 패키지 관리까지 함께
고민해야 합니다. 지금 단계의 핵심은 “백엔드 API가 실제 브라우저에서 어떤 흐름으로 쓰이는가”를
이해하는 것입니다.

그래서 다음을 우선했습니다.

- 빌드 없이 실행 가능
- API 요청 흐름이 JavaScript 코드에 그대로 보임
- 스트리밍 응답 처리 구조를 직접 확인 가능
- 백엔드와 프론트엔드 분리를 유지

## 스트리밍 처리 방식

브라우저의 `EventSource`는 기본적으로 GET 요청만 지원합니다. 현재 백엔드의 스트리밍 API는
메시지 본문과 JWT 헤더가 필요한 POST 요청입니다. 그래서 `fetch()`의 `ReadableStream`을
직접 읽어 SSE 블록을 파싱합니다.

```text
fetch("/chat/stream", POST)
  → response.body.getReader()
  → chunk를 TextDecoder로 문자열 변환
  → "\n\n" 기준으로 SSE 이벤트 분리
  → conversation/token/done/error 처리
```

## CORS 설정

프론트엔드를 `http://127.0.0.1:5173`에서 열고 백엔드를 `http://127.0.0.1:8000`에서
실행하면 브라우저 입장에서는 서로 다른 origin입니다. 그래서 백엔드에 CORS middleware를
추가했습니다.

기본 허용 origin:

```text
http://localhost:5173
http://127.0.0.1:5173
```

운영에서는 실제 프론트엔드 도메인만 허용하도록 환경 변수를 조정해야 합니다.
여러 origin은 콤마로 구분합니다.

## 실행 방법

백엔드:

```powershell
cd backend
docker compose up --build
```

프론트엔드:

```powershell
cd frontend
python -m http.server 5173
```

브라우저:

```text
http://127.0.0.1:5173
```

## 이번 단계의 한계

- 운영용 UI가 아니라 API 확인용 최소 UI입니다.
- 토큰을 `localStorage`에 저장하므로 XSS에 취약할 수 있습니다.
- 캐릭터 목록, 대화 목록, 기억 목록 UI는 아직 없습니다.
- 프론트엔드 자동 테스트는 아직 없습니다.

다음 단계에서는 배포 전 점검 문서와 환경 설정 검증 스크립트를 추가해 운영 준비도를 높입니다.
