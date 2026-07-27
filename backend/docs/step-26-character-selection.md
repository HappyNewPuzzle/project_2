# 26단계: 기존 캐릭터 목록 조회와 선택

이번 단계의 목표는 로그인한 사용자가 새 캐릭터를 매번 만들지 않고, 공용 캐릭터와
자신이 이전에 만든 캐릭터를 조회해 채팅 대상으로 선택할 수 있게 하는 것입니다.
백엔드에는 이미 권한이 적용된 `GET /characters`가 있으므로 DB와 API 계약은 변경하지
않고 React 프론트엔드의 데이터 흐름을 확장합니다.

## 주요 변경 파일

- [frontend/src/components/CharacterList.tsx](../../frontend/src/components/CharacterList.tsx)
  - 캐릭터 이름, 설명, 말투와 소유 구분을 카드 목록으로 표시합니다.
  - 현재 선택 항목에 `aria-pressed`와 시각적 강조를 적용합니다.

- [frontend/src/App.tsx](../../frontend/src/App.tsx)
  - 캐릭터 배열을 공통 상태로 관리합니다.
  - 로그인 직후 캐릭터와 대화 목록을 동시에 불러옵니다.
  - 캐릭터 선택 시 기존 대화와 화면 메시지를 초기화합니다.

- [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts)
  - `GET /characters?offset=0&limit=100` 호출을 추가했습니다.

- [frontend/src/types/api.ts](../../frontend/src/types/api.ts)
  - 백엔드 `CharacterResponse`의 전체 필드를 TypeScript 타입에 반영했습니다.

- [frontend/src/components/CharacterList.test.tsx](../../frontend/src/components/CharacterList.test.tsx)
  - 공용/소유 표시, 선택 접근성 속성과 사용자 문자열 escape를 검증합니다.

## 백엔드를 수정하지 않은 이유

4단계에서 이미 다음 API가 만들어졌습니다.

```http
GET /characters?offset=0&limit=100
Authorization: Bearer {access_token}
```

서비스 계층은 로그인 사용자가 읽을 수 있는 캐릭터만 반환합니다.

```text
목록 결과 = owner_id가 NULL인 공용 캐릭터
          + owner_id가 현재 user_id인 내 캐릭터
```

프론트엔드 편의를 위해 같은 기능의 새 endpoint를 만들면 유지해야 할 API가 중복됩니다.
기존 계약을 재사용하고 프론트 API client에 호출 메서드만 추가했습니다.

## 캐릭터를 바꾸면 새 대화가 되는 이유

하나의 대화방은 생성할 때 선택한 `character_id`를 계속 사용합니다. 진행 중인
대화에서 화면의 캐릭터 ID만 바꾸면 UI는 새 캐릭터를 표시하지만, 서버는 대화방에
고정된 기존 캐릭터로 답변하는 불일치가 생길 수 있습니다.

```text
캐릭터 카드 선택
  → characterId 변경
  → conversationId 제거
  → 화면 messages 제거
  → 다음 메시지로 새 대화 생성
```

이 규칙 덕분에 서로 다른 캐릭터의 시스템 프롬프트와 대화 문맥이 한 대화방에서
섞이지 않습니다. 반대로 대화 목록에서 이전 대화를 열면 그 대화의
`character_id`가 다시 선택 상태가 됩니다.

## 로그인 직후 목록 로딩

`setToken()`은 React 상태를 예약하므로 같은 함수 안의 기존 `api` 객체는 즉시 새
토큰으로 바뀌지 않습니다. 따라서 로그인 응답의 access token으로 짧게 새
`ApiClient`를 만들고 두 목록을 병렬로 조회합니다.

```text
POST /auth/login
  → access token
  → Promise.all(
      GET /characters,
      GET /conversations
    )
  → 화면 상태 반영
```

다음 렌더링부터는 `useMemo`가 새 토큰을 가진 공통 API client를 만듭니다.

## 공용과 내 캐릭터 표시

`CharacterResponse.owner_id`가 `null`이면 공용 캐릭터입니다. 그 외 값은 백엔드의
사용자 격리를 통과한 현재 사용자의 캐릭터이므로 “내 캐릭터”로 표시합니다.
다른 사용자의 캐릭터는 애초에 목록 결과에 포함되지 않습니다.

이 이름과 설명은 서버 데이터이므로 React의 일반 JSX 문자열로 렌더링합니다.
`dangerouslySetInnerHTML`을 사용하지 않아 `<script>` 같은 문자열도 HTML 코드가
아닌 텍스트로 표시됩니다.

## 페이지 크기

현재 UI는 학습 단계의 단순한 선택 목록이므로 backend가 허용하는 최대 크기인
100개를 한 번에 요청합니다. 캐릭터 수가 커지면 다음 중 하나로 확장해야 합니다.

- “더 보기” 버튼으로 `offset` 증가
- cursor pagination API
- 이름 검색과 서버 필터
- 목록 가상화

## 테스트

```powershell
cd frontend
npm test
npm run build
```

추가 검증 항목:

- 목록 요청 URL에 `offset=0&limit=100` 포함
- Bearer access token 포함
- 공용/내 캐릭터 배지 표시
- 현재 선택 카드의 `aria-pressed=true`
- `<달빛 사서>` 같은 이름이 escape되어 출력

## 다음 단계

27단계 후보는 캐릭터 수정·삭제 UI입니다. 백엔드의 `PATCH /characters/{id}`와
`DELETE /characters/{id}`를 연결하되, 공용 캐릭터는 읽기 전용으로 유지하고 대화에서
사용 중인 캐릭터 삭제의 `409 Conflict`를 이해하기 쉽게 안내할 수 있습니다.
