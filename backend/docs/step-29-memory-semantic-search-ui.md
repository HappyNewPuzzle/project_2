# 29단계: 장기 기억 의미 검색과 재색인 UI

이번 단계의 목표는 23단계에서 완성한 pgvector 의미 검색과 재색인 API를 React
프론트엔드에서 직접 확인할 수 있게 하는 것입니다. 사용자는 자연어 검색어와 선택적
캐릭터 범위를 보내고, 의미가 가까운 활성 기억을 cosine similarity 점수와 함께
확인할 수 있습니다.

## 주요 변경 파일

- [frontend/src/components/MemorySearchPanel.tsx](../../frontend/src/components/MemorySearchPanel.tsx)
  - 자연어 검색, 캐릭터 범위, 결과 순위·유사도와 재색인 UI를 제공합니다.
  - 재색인은 비용을 고려해 두 번 확인합니다.

- [frontend/src/App.tsx](../../frontend/src/App.tsx)
  - 검색과 재색인 작업을 공통 로딩·오류 상태에 연결합니다.
  - 실패 시 기존 검색 결과와 확인 상태를 보존합니다.

- [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts)
  - 검색 query parameter를 `URLSearchParams`로 안전하게 인코딩합니다.
  - 재색인 응답에서 실제 처리 개수를 반환합니다.

- [frontend/src/types/api.ts](../../frontend/src/types/api.ts)
  - `MemorySearchResult`와 `MemoryReindexResponse` 계약을 추가했습니다.

- [frontend/src/components/MemorySearchPanel.test.tsx](../../frontend/src/components/MemorySearchPanel.test.tsx)
  - 순위, 점수, 범위, 빈 결과와 문자열 escape를 검증합니다.

## 키워드 검색과 의미 검색의 차이

키워드 검색은 같은 단어가 포함됐는지 찾습니다. 의미 검색은 문장을 embedding
vector로 바꾼 뒤 방향이 가까운 기억을 찾습니다.

```text
저장된 기억:
“사용자는 밤하늘 사진 촬영을 좋아한다.”

검색어:
“내 취미가 뭐였지?”
```

두 문장에 같은 핵심 단어가 없어도 embedding 공간에서 의미가 가까우면 결과가 될 수
있습니다.

```text
검색어
  → 현재 EmbeddingProvider.embed()
  → query vector
  → pgvector cosine distance 검색
  → 현재 사용자·활성 상태·캐릭터 범위 필터
  → 상위 10개 기억과 similarity
```

## 검색 API

```http
GET /memories/search
  ?query=내가 좋아하는 취미가 뭐였지?
  &character_id={optional_uuid}
  &limit=10
Authorization: Bearer {access_token}
```

프론트엔드는 `URLSearchParams`를 사용하므로 한글, 공백, `&` 같은 문자가 query
구조를 깨지 않고 percent encoding됩니다.

응답 예:

```json
[
  {
    "id": "99999999-9999-9999-9999-999999999999",
    "character_id": null,
    "content": "사용자는 밤하늘 사진 촬영을 좋아한다.",
    "importance": 5,
    "is_active": true,
    "score": 0.9342,
    "created_at": "2026-07-28T00:00:00Z",
    "updated_at": "2026-07-28T00:00:00Z"
  }
]
```

## 캐릭터 검색 범위

범위를 지정하지 않으면 현재 사용자의 모든 활성 기억이 후보입니다. 캐릭터를
선택하면 채팅 문맥과 같은 범위를 사용합니다.

```text
character_id 없음
  → 사용자의 모든 활성 기억

character_id = 루나
  → 활성 전역 기억
  + 루나 전용 활성 기억
```

다른 캐릭터의 전용 기억이 결과에 섞이지 않으며, 다른 사용자의 vector는 SQL의
`user_id` 조건 때문에 후보가 되지 않습니다.

## 유사도 점수 해석

화면은 API의 `score`에 100을 곱해 소수점 한 자리 백분율 모양으로 표시합니다.

```text
0.9342 → 93.4%
```

이 값은 정답 확률이나 모델의 확신도가 아니라 두 vector의 cosine similarity입니다.
provider, 언어, 문장 길이와 데이터 분포에 따라 점수 범위가 달라지므로 모든 서비스에
통하는 고정 임계값으로 해석하면 안 됩니다.

운영 단계에서는 실제 사용자 검색 데이터를 평가해 다음 정책을 정해야 합니다.

- 최소 similarity threshold
- 반환 개수
- 중요도와 similarity의 결합 방식
- 중복 기억 제거

## 활성 기억만 검색하는 이유

사용자가 비활성화한 기억은 “삭제하지는 않지만 현재 사용하지 않겠다”는 의도입니다.
채팅 문맥뿐 아니라 의미 검색에서도 제외해야 화면 검색 결과와 실제 LLM 사용 범위가
일치합니다.

## 재색인

provider를 바꾸거나 기존 기억에 vector가 없을 때 다음 API를 사용합니다.

```http
POST /memories/reindex?limit=100
Authorization: Bearer {access_token}
```

재색인은 모든 기억을 매번 다시 처리하지 않습니다.

```text
현재 사용자 기억
  → embedding 행이 없는 기억
  또는 embedding provider가 현재 설정과 다른 기억
  → 최대 100개 embed
  → 같은 transaction에 upsert
  → indexed_count 반환
```

응답:

```json
{
  "indexed_count": 3
}
```

OpenAI embedding provider를 사용하면 외부 API 호출 비용과 지연이 발생할 수 있습니다.
그래서 첫 클릭은 실행 확인 상태로만 바꾸고, 두 번째 클릭에서 요청합니다. 취소하거나
요청이 실패하면 확인 상태를 유지하거나 되돌릴 수 있습니다.

## 검색 결과 상태

검색 요청이 실패했을 때 이전 결과를 빈 배열로 덮어쓰지 않습니다. 사용자는 실패 전
결과를 계속 확인하면서 URL, provider 또는 서버 상태를 점검할 수 있습니다.

성공했지만 결과가 0개라면 명시적인 빈 상태를 표시해 “아직 검색하지 않음”과
“검색했지만 결과 없음”을 구분합니다.

## rate limit

검색과 재색인은 embedding provider를 호출하므로 일반 목록 조회보다 비용이 큽니다.
백엔드는 두 API에 채팅과 같은 rate limit dependency를 적용합니다. 프론트 버튼
비활성화만으로 요청 남용을 막을 수 없으므로 서버 제한을 유지합니다.

## 테스트

```powershell
cd frontend
npm test
npm run build
```

추가 검증 항목:

- 한글·공백 검색어의 URL encoding
- 선택 캐릭터 ID와 limit query
- 재색인 POST와 Bearer header
- `indexed_count` 반환
- 결과 순위와 similarity 백분율
- 전역·캐릭터 범위 이름
- 검색 결과 내용의 HTML escape
- 검색 완료 후 결과가 없는 상태

백엔드는 Docker Compose CI 조건에서 전체 pytest를 재검증합니다.

## 다음 단계

30단계 후보는 인증 세션 UX입니다. 현재 access token은 localStorage에 저장되지만
로그아웃, 만료 감지, 인증 상태 초기화가 없습니다. 로그아웃 시 토큰과 사용자별 화면
상태를 함께 지우고, `401 Unauthorized` 응답을 일관되게 처리하는 구조를 추가할 수
있습니다.
