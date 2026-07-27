# 23단계: 장기 기억 의미 검색

이번 단계의 목표는 기억을 저장할 때 embedding을 자동 생성하고, PostgreSQL pgvector가
사용자 질문과 의미가 가까운 기억을 직접 검색하게 만드는 것입니다.

## 추가된 API

```text
GET  /memories/search?query=...&character_id=...&limit=10
POST /memories/reindex?limit=100
```

- `search`
  - 현재 사용자의 활성 기억만 검색합니다.
  - `character_id`가 있으면 전역 기억과 해당 캐릭터 기억만 검색합니다.
  - 없으면 현재 사용자가 가진 모든 캐릭터 범위의 활성 기억을 검색합니다.
  - cosine similarity가 높은 순서로 `score`와 기억 데이터를 반환합니다.

- `reindex`
  - embedding이 없거나 현재 provider와 다른 기존 기억을 다시 색인합니다.
  - 한 요청에서 최대 100개만 처리해 API 비용과 응답 시간을 제한합니다.
  - 여러 번 호출하면 남은 기억을 이어서 처리할 수 있습니다.

두 API 모두 embedding 비용이 발생할 수 있으므로 채팅과 같은 사용자별 rate limit을
적용합니다.

## 수정한 주요 파일

- [app/api/routes/memories.py](../app/api/routes/memories.py)
  - 검색과 재색인 HTTP API를 추가했습니다.
  - `/search`를 `/{memory_id}`보다 먼저 선언해 문자열이 UUID 경로로 잘못 해석되지 않게
    했습니다.

- [app/services/memory_service.py](../app/services/memory_service.py)
  - 기억 생성 시 내용과 embedding을 같은 트랜잭션으로 저장합니다.
  - 기억 내용이 바뀌었을 때만 embedding을 다시 생성합니다.
  - 사용자·캐릭터 검증 후 검색 repository를 호출합니다.
  - 기존 기억의 제한적 재색인을 조정합니다.

- [app/repositories/memory_embedding_repository.py](../app/repositories/memory_embedding_repository.py)
  - pgvector `cosine_distance()` 정렬 쿼리를 추가했습니다.
  - 사용자 ID, 활성 상태, 캐릭터 범위를 SQL 조건에 포함합니다.

- [app/services/memory_extraction_service.py](../app/services/memory_extraction_service.py)
  - 채팅에서 자동 추출된 기억도 저장과 동시에 embedding을 생성합니다.

- [tests/test_memory_search_integration.py](../tests/test_memory_search_integration.py)
  - 실제 pgvector DB에서 전체 검색 흐름과 권한 격리를 검증합니다.

## 저장 흐름

```text
POST /memories
  → 캐릭터 접근 권한 확인
  → EmbeddingProvider.embed(content)
  → memories INSERT
  → memory_embeddings UPSERT
  → 한 번의 COMMIT
```

embedding API가 실패하면 기억만 저장되는 불완전한 상태를 만들지 않고 요청 전체를
실패시킵니다. 내용이 아닌 중요도나 활성 상태만 수정할 때는 embedding을 다시 만들지
않습니다.

자동 기억 추출도 같은 원칙을 사용합니다.

```text
LLM memory 후보 추출
  → 모든 후보 embedding 생성
  → memories + memory_embeddings 저장
  → 한 번의 COMMIT
```

자동 추출 실패는 기존 정책대로 채팅 답변 성공을 취소하지 않습니다.

## 검색 쿼리 구조

SQLAlchemy의 핵심 구조는 다음과 같습니다.

```python
distance = MemoryEmbedding.embedding.cosine_distance(query_vector)

statement = (
    select(Memory, distance.label("distance"))
    .join(MemoryEmbedding)
    .where(
        Memory.user_id == current_user_id,
        Memory.is_active.is_(True),
        MemoryEmbedding.embedding.is_not(None),
    )
    .order_by(distance)
    .limit(limit)
)
```

pgvector HNSW index를 사용하려면 거리 연산 결과 자체를 오름차순 정렬하고 `LIMIT`을
적용해야 합니다. API의 `score`는 다음처럼 사람이 이해하기 쉬운 similarity로
변환합니다.

```text
cosine similarity = 1 - cosine distance
```

부동소수점 오차를 고려해 반환 점수는 `-1.0`부터 `1.0` 범위로 제한합니다.

공식 참고 자료:

- [OpenAI embeddings guide](https://developers.openai.com/api/docs/guides/embeddings#how-to-get-embeddings)
- [pgvector 검색과 index 사용법](https://github.com/pgvector/pgvector#querying)
- [pgvector-python SQLAlchemy](https://github.com/pgvector/pgvector-python#sqlalchemy)

## API 사용 예시

로그인한 사용자의 access token이 있다고 가정합니다.

```powershell
$headers = @{ Authorization = "Bearer YOUR_ACCESS_TOKEN" }

$results = Invoke-RestMethod `
  -Method Get `
  -Uri "http://127.0.0.1:8000/memories/search?query=천문학&limit=10" `
  -Headers $headers
```

응답 예시:

```json
[
  {
    "id": "99999999-9999-9999-9999-999999999999",
    "character_id": null,
    "content": "사용자는 천문학을 좋아한다",
    "importance": 4,
    "is_active": true,
    "created_at": "2026-07-27T10:00:00Z",
    "updated_at": "2026-07-27T10:00:00Z",
    "score": 0.91
  }
]
```

기존 기억을 현재 provider로 재색인합니다.

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/memories/reindex?limit=100" `
  -Headers $headers
```

```json
{
  "indexed_count": 12
}
```

## 설정에 따른 동작

기본 `EMBEDDING_PROVIDER=hashing`은 외부 비용 없이 구조를 테스트하기 위한 방식입니다.
실제 의미 품질이 필요한 환경에서는 다음 설정을 사용합니다.

```dotenv
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=실제_API_키
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=1536
```

provider를 변경한 뒤 `/memories/reindex`를 반복 호출해야 기존 기억도 같은 벡터 공간으로
변환됩니다.

## 다음 단계

24단계에서는 사용자가 대화방을 쉽게 구분할 수 있도록 첫 대화 내용을 바탕으로 제목을
자동 생성하고, 대화방 목록 API와 프론트엔드에 제목을 표시합니다.
