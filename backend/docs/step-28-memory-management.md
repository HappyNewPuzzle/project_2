# 28단계: 장기 기억 관리 UI

이번 단계의 목표는 프론트엔드의 고정된 “테스트 기억 저장” 버튼을 실제 장기 기억
관리 화면으로 교체하는 것입니다. 사용자는 기억을 직접 작성하고, 전역 또는 특정
캐릭터 범위를 선택하며, 중요도·활성 상태를 변경하고 삭제할 수 있습니다.

## 주요 변경 파일

- [frontend/src/components/MemoryPanel.tsx](../../frontend/src/components/MemoryPanel.tsx)
  - 기억 작성, 범위 선택, 목록 필터, 활성화, 중요도 변경과 삭제를 제공합니다.
  - 삭제는 두 번 확인하고 실패 시 확인 상태를 유지합니다.

- [frontend/src/App.tsx](../../frontend/src/App.tsx)
  - 기억 목록을 공통 상태로 관리합니다.
  - 로그인 직후 캐릭터·대화·기억 목록을 동시에 조회합니다.
  - 생성·수정·삭제 응답을 목록에 즉시 반영합니다.

- [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts)
  - 기억 생성·목록·부분 수정·삭제 API를 추가했습니다.

- [frontend/src/types/api.ts](../../frontend/src/types/api.ts)
  - `MemoryCreate`, `MemoryUpdate`, `Memory` 타입을 백엔드 스키마와 맞췄습니다.

- [frontend/src/components/MemoryPanel.test.tsx](../../frontend/src/components/MemoryPanel.test.tsx)
  - 범위·중요도·활성 상태와 안전한 문자열 렌더링을 검증합니다.

## 기억 범위

새 기억은 두 가지 범위 중 하나로 저장합니다.

```text
character_id = null
  → 모든 캐릭터 대화에서 사용할 전역 기억

character_id = 특정 UUID
  → 해당 캐릭터 대화에서만 사용할 기억
```

예를 들어 “사용자는 한국어 답변을 선호한다”는 전역 기억이 적합하고,
“루나와는 천문학 이야기를 이어간다”는 루나 캐릭터 전용 기억이 적합합니다.

채팅 서비스는 현재 캐릭터를 기준으로 다음 기억을 함께 조회합니다.

```text
활성 전역 기억
  +
현재 캐릭터의 활성 기억
  → 중요도 내림차순
  → 최근 수정순
  → 상위 memory_limit개를 프롬프트에 포함
```

## 생성 API

```http
POST /memories
Authorization: Bearer {access_token}
Content-Type: application/json
```

```json
{
  "content": "사용자는 천문학과 별 사진을 좋아한다.",
  "character_id": null,
  "importance": 4
}
```

내용은 최대 5,000자이며 중요도는 1부터 5까지입니다. 캐릭터 ID를 지정하면 백엔드가
현재 사용자에게 접근 가능한 캐릭터인지 확인합니다.

기억 생성은 텍스트 행만 저장하는 작업이 아닙니다.

```text
content
  → EmbeddingProvider.embed()
  → memories 행 생성
  → memory_embeddings vector 저장
  → 하나의 transaction commit
```

embedding provider가 실패하면 불완전한 기억을 남기지 않고 전체 작업을 rollback합니다.
따라서 프론트엔드는 저장 실패 시 사용자가 작성한 textarea 내용을 지우지 않습니다.

## 활성 상태와 중요도

활성 상태는 기억을 삭제하지 않고 채팅 문맥에서 잠시 제외할 때 사용합니다.

```http
PATCH /memories/{memory_id}
Content-Type: application/json

{"is_active": false}
```

- 활성: 채팅 프롬프트와 의미 검색 후보에 포함
- 비활성: DB와 화면에는 남지만 LLM 문맥에서는 제외

중요도도 같은 PATCH API로 1~5 사이에서 바꿉니다. 중요도가 높은 활성 기억은 제한된
프롬프트 기억 개수 안에 먼저 포함됩니다.

내용 자체를 바꾸는 PATCH도 백엔드가 지원합니다. 내용이 실제로 변경되면 새 embedding을
만들어 vector를 교체해야 하므로, 이번 UI는 빈번한 재색인을 피하고 작성·활성화·중요도
관리부터 제공합니다.

## 목록 필터

API의 최대 page size인 100개를 한 번 불러와 다음 필터를 브라우저에서 즉시 적용합니다.

- 전체 기억
- 모든 캐릭터에 적용되는 전역 기억
- 선택한 캐릭터 전용 기억

현재 규모에서는 filter를 바꿀 때마다 서버 요청하지 않아 반응이 빠르고 구현이
단순합니다. 사용자당 기억이 100개를 넘으면 이 방식은 모든 데이터를 보여주지
못하므로 서버 pagination과 `character_id` query를 UI 상태에 연결해야 합니다.

## 상태 갱신

각 mutation 뒤 전체 목록을 다시 요청하지 않습니다.

```text
생성 성공 → 새 기억을 배열 앞에 추가
수정 성공 → 같은 id 항목만 응답 객체로 교체
삭제 성공 → 같은 id 항목 제거
```

서버 응답을 사용하므로 `updated_at`, 정규화된 내용과 기본값까지 실제 저장 상태와
일치합니다.

## 삭제 확인

기억 삭제도 한 번의 클릭으로 실행하지 않습니다.

```text
삭제 클릭
  → 버튼이 “정말 삭제”로 변경
  → 두 번째 클릭
  → DELETE /memories/{id}
```

실패하면 다시 시도할 수 있도록 확인 상태를 유지하고, 성공했을 때만 목록에서
제거합니다.

## 보안과 사용자 격리

기억 카드에 별도 owner ID가 없어도 안전한 이유는 백엔드의 모든 기억 repository
조회가 `memory.user_id == current_user.id`를 포함하기 때문입니다. 타인의 기억 ID로
GET, PATCH, DELETE를 시도해도 현재 사용자 범위에서는 찾을 수 없어 `404`가 됩니다.

프론트엔드의 필터링은 표시 편의를 위한 것이며 사용자 격리 보안은 서버 SQL 조건이
담당합니다.

## 테스트

```powershell
cd frontend
npm test
npm run build
```

추가 검증 항목:

- 기억 생성의 content, character scope와 importance JSON
- 활성 상태 PATCH
- 목록 요청의 `offset=0&limit=100`
- 전역·캐릭터 기억 표시
- 중요도와 비활성 상태 표시
- 기억 내용의 HTML escape
- 기억이 없는 범위의 빈 상태

백엔드는 Docker Compose의 CI 조건에서 전체 pytest를 다시 실행합니다.

## 다음 단계

29단계 후보는 장기 기억 의미 검색 UI입니다. 이미 구현된
`GET /memories/search`를 연결해 자연어 질문과 의미적으로 가까운 활성 기억을
similarity score와 함께 확인하고, 필요할 때 기존 기억 재색인을 실행할 수 있습니다.
