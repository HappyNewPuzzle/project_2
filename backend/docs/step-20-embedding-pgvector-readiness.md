# 20단계: embedding / pgvector 검색 준비

이번 단계의 목표는 장기 기억이 많아졌을 때 관련성 기반 검색으로 확장할 수 있는 저장 경계와
provider 구조를 준비하는 것입니다.

## 추가·수정한 파일

- [backend/alembic/versions/20260718_0005_add_memory_embeddings.py](../alembic/versions/20260718_0005_add_memory_embeddings.py)
  - `memory_embeddings` 테이블을 추가했습니다.

- [backend/app/db/models.py](../app/db/models.py)
  - `MemoryEmbedding` ORM 모델을 추가했습니다.

- [backend/app/repositories/memory_embedding_repository.py](../app/repositories/memory_embedding_repository.py)
  - embedding upsert와 조회를 담당합니다.

- [backend/app/services/embedding_service.py](../app/services/embedding_service.py)
  - `EmbeddingProvider` 인터페이스를 추가했습니다.
  - 외부 API 없는 `HashingEmbeddingProvider`를 추가했습니다.
  - cosine similarity 검색 함수를 추가했습니다.

## 왜 바로 pgvector를 강제하지 않았나?

현재 Docker Compose는 기본 `postgres:17-alpine` 이미지를 사용합니다. 이 이미지에는 pgvector
확장이 기본 포함되어 있지 않을 수 있습니다. 지금 migration에서 `CREATE EXTENSION vector`를
강제하면 로컬과 CI가 깨질 가능성이 큽니다.

그래서 이번 단계에서는 다음 방식으로 준비했습니다.

```text
현재:
  memories
  memory_embeddings(vector_json)
  Python cosine 검색

다음 확장:
  pgvector extension
  memory_embeddings.embedding VECTOR(n)
  ORDER BY embedding <=> query_embedding
```

즉, 서비스와 repository 경계를 먼저 만들고 DB 저장 타입은 나중에 안전하게 교체할 수 있게
했습니다.

## 현재 한계

- 검색 API는 아직 노출하지 않았습니다.
- embedding은 개발용 hashing 방식입니다.
- 모든 embedding을 읽어 Python에서 cosine을 계산하므로 대량 데이터에 적합하지 않습니다.
- OpenAI embedding provider는 아직 연결하지 않았습니다.

다음 큰 단계에서는 실제 embedding provider와 pgvector 지원 PostgreSQL 이미지로 전환한 뒤,
memory 검색 API를 추가하면 됩니다.
