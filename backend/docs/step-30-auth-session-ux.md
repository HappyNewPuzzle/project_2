# 30단계: 로그아웃과 401 인증 세션 UX

이번 단계의 목표는 localStorage에 access token을 저장만 하던 프론트엔드에 명시적인
로그아웃과 만료 세션 처리를 추가하는 것입니다. 보호 API가 `401 Unauthorized`를
반환하면 토큰뿐 아니라 이전 사용자의 캐릭터·기억·대화·메시지와 컴포넌트 내부
입력까지 함께 초기화합니다.

## 주요 변경 파일

- [frontend/src/components/AuthPanel.tsx](../../frontend/src/components/AuthPanel.tsx)
  - 로그인 상태에만 로그아웃 버튼과 세션 안내를 표시합니다.

- [frontend/src/App.tsx](../../frontend/src/App.tsx)
  - 사용자 데이터 초기화와 세션 초기화를 분리합니다.
  - 로그아웃과 만료 401을 같은 안전한 초기화 흐름에 연결합니다.
  - 토큰 변경 시 workspace를 remount해 컴포넌트 내부 상태도 제거합니다.

- [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts)
  - 모든 보호 API 응답의 401을 공통 `checked()` 경계에서 감지합니다.
  - 로그인 실패 401은 만료 callback에서 제외합니다.
  - `ApiError.sessionHandled`로 중복 오류 문구를 막습니다.

- [frontend/src/components/AuthPanel.test.tsx](../../frontend/src/components/AuthPanel.test.tsx)
  - 인증 상태에 따른 로그아웃 UI 차이를 검증합니다.

## stateless JWT 로그아웃

현재 백엔드는 access token을 DB나 Redis session으로 저장하지 않습니다. 서버는 요청마다
JWT 서명, 만료 시각과 subject를 검증합니다.

```text
로그인
  → 서버가 sub=user UUID, exp가 있는 JWT 서명
  → 브라우저가 access token 저장

보호 API
  → Authorization: Bearer token
  → 서버가 서명과 exp 검증
```

따라서 현재 로그아웃은 서버의 token을 삭제하는 요청이 아니라 클라이언트가 token을
더 이상 보내지 않도록 제거하는 작업입니다.

```text
로그아웃
  → localStorage token 제거
  → 선택 characterId 제거
  → conversationId 제거
  → 캐릭터·기억·대화·메시지 배열 제거
  → 입력 form과 검색 결과 remount
```

이미 복사된 access token은 원래 만료 시각까지 유효할 수 있습니다. 즉시 폐기가
필요하면 refresh token 저장소, token rotation 또는 denylist 같은 서버 상태가
추가로 필요합니다.

## 사용자 데이터와 세션 초기화 분리

`clearUserData()`는 현재 사용자에게 속한 화면 데이터만 지웁니다.

```text
characterId
conversationId
characters
memories
conversations
messages
```

`clearSession(message)`은 token을 지운 뒤 `clearUserData()`를 호출하고 상태 안내를
바꿉니다. 이 분리 덕분에 다른 사용자로 로그인할 때는 새 token을 설정하기 전에
이전 데이터만 먼저 비울 수 있습니다.

API Base URL은 사용자 소유 데이터가 아닌 개발 환경 설정이므로 로그아웃해도
유지합니다.

## 컴포넌트 내부 상태까지 지우는 이유

App 배열만 비워도 다음 데이터는 각 컴포넌트의 `useState`에 남을 수 있습니다.

- 전송하지 않은 채팅 draft
- 작성 중인 장기 기억
- 의미 검색 결과와 검색어
- 캐릭터 편집 form
- 삭제·재색인 확인 상태

다른 사용자가 같은 브라우저에서 로그인하면 이전 사용자의 민감한 입력을 볼 수
있습니다. workspace의 React `key`를 token 기준으로 바꾸면 인증 전환 시 subtree가
unmount되고 새 상태로 mount됩니다.

```tsx
<div className="workspace" key={token || "anonymous"}>
```

`key`는 DOM에 표시되지 않지만, 향후에는 token 전체 대신 별도 session generation
값을 사용하는 것도 좋습니다.

## 공통 401 처리

모든 API 메서드에 401 처리를 반복하면 DELETE나 streaming 같은 수동 fetch 경로를
빠뜨리기 쉽습니다. `ApiClient.checked()`가 성공 여부 검사와 세션 callback을 함께
담당합니다.

```text
fetch response
  → checked()
  → ensureOk()
  → ApiError(status=401)
  → 보호 API이고 기존 token이 있으면
      sessionHandled = true
      onUnauthorized()
  → 원래 ApiError rethrow
```

App의 `runAction()`은 `sessionHandled`가 true이면 callback이 만든 만료 안내를
일반 `오류: 401 ...` 문구로 덮어쓰지 않습니다.

## 로그인 실패 401과 만료 401

두 응답은 status만 보면 모두 401이지만 의미가 다릅니다.

```text
POST /auth/login의 401
  → 입력한 email/password가 잘못됨
  → 기존 세션을 자동 삭제하지 않음
  → 일반 로그인 오류 표시

GET /characters 같은 보호 API의 401
  → 저장 token이 만료·손상됐거나 사용자를 인증할 수 없음
  → 현재 세션과 사용자 데이터 초기화
  → 다시 로그인 안내
```

`register()`와 `login()`은 `checked(response, false)`를 사용해 unauthorized
callback을 호출하지 않습니다.

## JWT exp를 브라우저에서 미리 읽지 않는 이유

JWT payload는 암호화되지 않아 브라우저가 `exp`를 읽을 수 있지만, 클라이언트는
서명을 검증할 secret이 없습니다. 또한 다음 상황은 payload 시간만으로 판단할 수
없습니다.

- 서버 secret 변경
- 사용자 비활성화 또는 삭제
- 손상된 서명
- 서버와 브라우저 시간 차이
- 향후 token denylist 적용

브라우저의 exp timer는 UX 개선용으로 추가할 수 있지만, 인증 상태의 최종 기준은
항상 서버 응답입니다. 이번 단계는 모든 보호 API의 401을 일관되게 처리합니다.

## localStorage 보안 한계

localStorage token은 JavaScript가 읽을 수 있으므로 XSS가 발생하면 탈취될 수 있습니다.
현재 선택은 학습용 SPA에서 새로고침 후 세션을 유지하기 위한 것입니다.

운영 인증으로 확장할 때는 다음 항목을 함께 설계해야 합니다.

- 짧은 access token 수명
- HttpOnly, Secure, SameSite refresh cookie
- refresh token rotation과 reuse detection
- Content Security Policy
- 로그아웃 시 refresh session 폐기
- CSRF 방어

HttpOnly cookie 하나만 적용한다고 모든 위험이 자동으로 해결되지는 않습니다.

## 테스트

```powershell
cd frontend
npm test
npm run build
```

추가 검증 항목:

- 로그인 상태에만 로그아웃 버튼 표시
- 보호 API 401에서 unauthorized callback 1회 호출
- 처리된 `ApiError.sessionHandled=true`
- 로그인 실패 401에서는 callback 미호출
- 로그인 실패 오류는 `sessionHandled=false`
- TypeScript strict 검사와 production bundle

백엔드는 Docker Compose CI 조건에서 전체 pytest를 재검증합니다.

## 다음 단계

31단계 후보는 refresh token 기반 세션 갱신입니다. HttpOnly cookie, refresh token
rotation, 서버 측 session 저장과 폐기를 추가하고 access token 만료 시 한 번만
자동 갱신한 뒤 원래 요청을 재시도하는 구조로 확장할 수 있습니다.
