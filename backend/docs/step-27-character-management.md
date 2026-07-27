# 27단계: 사용자 소유 캐릭터 수정과 삭제

이번 단계의 목표는 26단계에서 선택한 캐릭터의 상세 설정을 확인하고, 현재 사용자가
소유한 캐릭터만 수정·삭제할 수 있는 UI를 제공하는 것입니다. 백엔드의 기존
`PATCH /characters/{id}`와 `DELETE /characters/{id}`를 연결하며 공용 캐릭터와
사용 중인 캐릭터에 대한 서버 보호 규칙을 유지합니다.

## 주요 변경 파일

- [frontend/src/components/CharacterEditor.tsx](../../frontend/src/components/CharacterEditor.tsx)
  - 선택 캐릭터의 상세 정보와 편집 폼을 표시합니다.
  - 공용 캐릭터는 읽기 전용으로 렌더링합니다.
  - 삭제를 두 번 확인하고 취소할 수 있게 합니다.

- [frontend/src/App.tsx](../../frontend/src/App.tsx)
  - 선택 캐릭터를 목록 상태에서 계산합니다.
  - 수정 결과로 목록 항목을 교체합니다.
  - 삭제 성공 후 선택·대화·메시지 상태를 초기화합니다.
  - `409 Conflict`를 사용자가 이해할 수 있는 문장으로 변환합니다.

- [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts)
  - 캐릭터 PATCH와 DELETE 요청을 추가했습니다.
  - FastAPI 오류 JSON의 `detail`을 공통 `ApiError`에 보존합니다.

- [frontend/src/types/api.ts](../../frontend/src/types/api.ts)
  - 부분 수정 요청을 나타내는 `CharacterUpdate`를 추가했습니다.

- [frontend/src/components/CharacterEditor.test.tsx](../../frontend/src/components/CharacterEditor.test.tsx)
  - 공용 캐릭터와 사용자 소유 캐릭터의 UI 권한 차이를 검증합니다.

## 프론트엔드 권한과 서버 권한

목록 API는 공용 캐릭터와 현재 사용자의 캐릭터만 반환합니다. 프론트엔드는
`owner_id`에 따라 다음처럼 UI를 나눕니다.

```text
owner_id = null
  → 상세 정보 표시
  → 편집·삭제 버튼 없음

owner_id = UUID
  → 전체 편집 폼 표시
  → 수정·삭제 버튼 표시
```

버튼을 숨기는 것은 사용성을 위한 처리이지 보안 경계가 아닙니다. 사용자는 브라우저
개발자 도구나 별도 HTTP client로 요청을 직접 만들 수 있으므로 백엔드는 계속
`owner_id == current_user.id`를 확인하고 위반 시 `403`을 반환합니다.

```text
UI 권한 = 실수 방지와 명확한 사용 경험
서버 권한 = 실제 데이터 보호
```

## 부분 수정 API

백엔드는 PATCH 요청에 포함된 필드만 바꿀 수 있습니다.

```http
PATCH /characters/{character_id}
Authorization: Bearer {access_token}
Content-Type: application/json
```

```json
{
  "name": "수정된 루나",
  "description": "별빛 기록관의 사서",
  "personality": "차분하고 호기심이 많다",
  "speaking_style": "다정한 존댓말",
  "system_prompt": "항상 캐릭터를 유지한다."
}
```

현재 편집 폼은 사용자가 전체 설정을 한 화면에서 이해하기 쉽도록 다섯 필드를 모두
보냅니다. API client의 `CharacterUpdate` 필드는 선택 사항이라 향후 이름 하나만
바꾸는 inline edit도 같은 메서드를 사용할 수 있습니다.

수정 응답의 최신 캐릭터 객체는 배열 전체를 다시 조회하지 않고 같은 ID의 항목만
교체합니다.

```text
PATCH 성공
  → updated Character 수신
  → characters.map()
  → 같은 id 항목만 updated로 교체
  → 선택 상태와 목록 즉시 갱신
```

## 삭제 확인과 상태 정리

삭제는 되돌리기 어려우므로 한 번의 클릭으로 요청하지 않습니다.

```text
“캐릭터 삭제” 클릭
  → 경고 문구 표시
  → 버튼이 “정말 삭제”로 변경
  → 두 번째 클릭
  → DELETE 요청
```

다른 캐릭터를 선택하거나 취소 버튼을 누르면 확인 상태가 초기화됩니다. 삭제가
성공하면 캐릭터 목록에서 해당 항목을 제거하고 `characterId`, `conversationId`,
화면 메시지를 비웁니다.

## 사용 중인 캐릭터의 409 Conflict

`conversations.character_id` 외래 키는 캐릭터 삭제로 과거 대화의 의미가 사라지지
않도록 삭제를 제한합니다.

```http
DELETE /characters/{character_id}
```

```json
{
  "detail": "Character is used by an existing conversation."
}
```

프론트엔드는 `409 Conflict`를 다음 안내로 바꿉니다.

```text
기존 대화에서 사용 중인 캐릭터는 삭제할 수 없습니다.
연결된 대화를 먼저 삭제하세요.
```

캐릭터를 강제로 지우거나 대화의 캐릭터 ID를 임의로 바꾸지 않는 이유는 저장된
대화의 캐릭터 문맥을 보존하기 위해서입니다.

## 공통 API 오류 개선

이전에는 오류 응답 본문 전체가 다음처럼 표시됐습니다.

```text
409 Conflict: {"detail":"Character is used..."}
```

현재 `ensureOk()`는 JSON을 파싱할 수 있으면 문자열 `detail`을 꺼내고, proxy가 HTML
또는 일반 텍스트 오류를 반환하면 원문을 유지합니다. HTTP status는 `ApiError.status`에
별도로 남기므로 화면 흐름에서 409만 구체적으로 처리할 수 있습니다.

## 테스트

```powershell
cd frontend
npm test
npm run build
```

추가 검증 항목:

- 공용 캐릭터에 편집 폼과 삭제 버튼이 없음
- 사용자 소유 캐릭터에 전체 편집 필드가 표시됨
- PATCH method와 JSON payload
- DELETE 409 응답의 status와 `detail` 보존
- TypeScript strict 검사와 production bundle 생성

백엔드 전체 테스트도 다음 조건으로 재검증합니다.

```powershell
cd backend
docker compose run --rm --volume "${PWD}:/app" --env REDIS_URL= api python -m pytest -q
```

## 다음 단계

28단계 후보는 장기 기억 관리 UI입니다. 현재 프론트엔드는 고정된 테스트 기억만
저장하므로, 기억 목록·직접 작성·활성화·삭제와 캐릭터별 범위를 화면에서 관리하는
흐름으로 확장할 수 있습니다.
