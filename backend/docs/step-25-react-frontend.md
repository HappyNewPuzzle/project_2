# 25단계: React + TypeScript 프론트엔드 구조화

이번 단계의 목표는 기존 단일 HTML 프론트엔드의 기능을 유지하면서 화면, 상태,
HTTP 통신과 SSE 파싱의 책임을 분리하는 것입니다. React 19, TypeScript, Vite 6,
Vitest를 사용하며 백엔드 API는 변경하지 않습니다.

## 왜 React와 Vite를 선택했나

현재 화면은 로그인 뒤 사용하는 하나의 애플리케이션입니다. 검색 엔진 노출,
서버 렌더링, 파일 기반 라우팅이 아직 필요하지 않으므로 Next.js의 서버 계층을
추가하기보다 작은 SPA로 시작합니다.

- React: 상태가 변하면 메시지와 선택 대화가 선언적으로 다시 그려집니다.
- TypeScript: SSE JSON처럼 런타임 데이터는 검사하면서 내부 데이터 계약은
  컴파일 시점에 확인할 수 있습니다.
- Vite: 개발 서버와 production bundle만 제공해 현재 범위가 작습니다.
- Vitest: Vite와 같은 모듈 설정으로 브라우저 독립 로직을 빠르게 검증합니다.

로컬 환경의 Node.js가 20.18이므로 Node 20.19 이상이 필요한 Vite 7 대신 Vite 6을
고정했습니다. GitHub Actions는 Node.js 22를 사용해 현재 LTS 계열에서도 빌드되는지
확인합니다.

## 주요 변경 파일

- [frontend/src/App.tsx](../../frontend/src/App.tsx)
  - 로그인 토큰, 캐릭터 ID, 대화 ID와 화면 메시지를 관리합니다.
  - 여러 API 작업의 로딩·오류 상태를 한 곳에서 처리합니다.
  - SSE 이벤트를 받아 assistant 메시지에 토큰을 이어 붙입니다.

- [frontend/src/components](../../frontend/src/components)
  - 인증, 캐릭터, 대화 목록, 채팅 화면을 독립 컴포넌트로 나눴습니다.
  - 컴포넌트는 API URL과 `fetch`를 직접 알지 않습니다.

- [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts)
  - Authorization header, JSON 요청, 오류 변환과 stream 시작을 담당합니다.

- [frontend/src/lib/sse.ts](../../frontend/src/lib/sse.ts)
  - 네트워크 chunk가 SSE 이벤트 중간에서 잘려도 buffer에 남깁니다.
  - CRLF와 LF, 여러 `data:` 줄과 마지막 빈 줄 없는 응답을 처리합니다.

- [frontend/src/types/api.ts](../../frontend/src/types/api.ts)
  - 백엔드 요청·응답과 화면 모델을 명시합니다.

- [frontend/src/lib/sse.test.ts](../../frontend/src/lib/sse.test.ts)
  - 실제 네트워크에서 흔한 분할 chunk 경계를 자동 검증합니다.

- [.github/workflows/frontend-ci.yml](../../.github/workflows/frontend-ci.yml)
  - push/PR마다 의존성을 lock file대로 설치하고 테스트와 빌드를 실행합니다.

## 상태와 책임 흐름

```text
사용자 입력
  → 화면 컴포넌트
  → App 작업 함수
  → ApiClient
  → FastAPI

FastAPI SSE
  → ReadableStream
  → SSE parser
  → App 메시지 상태 갱신
  → ChatPanel 다시 렌더링
```

`App` 하나에 모든 HTML을 두지 않고도 공통 상태를 여기에 둔 이유는 현재 화면 규모에서는
인증 store나 전역 상태 라이브러리가 오히려 개념을 늘리기 때문입니다. 화면과 라우트가
늘어날 때 Context 또는 전용 query/state 도구를 도입할 수 있습니다.

## SSE를 별도 파일로 둔 이유

`ReadableStream.read()`가 돌려주는 chunk는 토큰이나 SSE 이벤트 경계와 일치하지
않습니다.

```text
chunk 1: event: token\ndata: {"del
chunk 2: ta":"안녕"}\n\n
```

각 chunk를 바로 JSON으로 파싱하면 위 입력은 실패합니다. 현재 파서는 완성된 빈 줄
구분자가 나올 때까지 문자열을 buffer에 모은 뒤 이벤트 단위로 전달합니다. 이 로직은
UI 없이 테스트할 수 있으므로 `lib/sse.ts`로 분리했습니다.

## 타입과 런타임 검사의 경계

TypeScript 타입은 빌드 후 사라지므로 서버가 잘못된 JSON을 보내는 상황까지 막지는
못합니다. 따라서 `conversation`과 `token` SSE payload는 `typeof`로 실제 값을
확인한 뒤 상태에 반영합니다. 내부 컴포넌트 props와 API 결과 사용은 TypeScript로
검증합니다.

## 실행과 테스트

```powershell
cd frontend
npm install
npm run dev
```

별도 터미널에서:

```powershell
cd frontend
npm test
npm run build
```

`npm run build`는 먼저 `tsc --noEmit`으로 strict 타입 검사를 하고, 성공해야 Vite가
production bundle을 만듭니다. `dist/`는 생성물이라 Git에 저장하지 않습니다.

## 보안 메모

React는 문자열을 JSX로 렌더링할 때 기본적으로 escape하므로 대화 제목이나 메시지가
HTML로 실행되지 않습니다. `dangerouslySetInnerHTML`은 사용하지 않습니다.

현재 access token은 이전 단계처럼 `localStorage`에 저장합니다. 학습용 새로고침 편의를
위한 선택이며 XSS에 노출될 수 있으므로, 운영 단계에서는 CSP, HttpOnly cookie,
refresh token 회전과 로그아웃 정책을 함께 설계해야 합니다.

## 다음 단계

26단계 후보는 캐릭터 목록 조회·선택 UI입니다. 현재는 캐릭터를 생성한 직후의 ID만
기억하므로, 다시 로그인한 사용자가 기존 캐릭터를 찾아 선택할 수 있는 흐름을 먼저
보완하는 것이 자연스럽습니다.
