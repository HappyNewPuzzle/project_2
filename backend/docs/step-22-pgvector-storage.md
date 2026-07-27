# 22단계: pgvector 저장 구조

이번 단계의 목표는 JSON 문자열로만 보관하던 embedding을 PostgreSQL의 실제
`VECTOR(1536)` 타입에 저장하는 것입니다. 검색 API는 다음 단계에서 추가하고, 이번에는
DB 확장·migration·ORM·저장 경계를 완성합니다.

## 추가·수정한 파일

- [compose.yaml](../compose.yaml)
  - PostgreSQL 이미지를 `pgvector/pgvector:0.8.2-pg17-bookworm`으로 변경했습니다.

- [requirements.txt](../requirements.txt)
  - SQLAlchemy에서 `VECTOR` 타입을 사용하는 `pgvector` 패키지를 추가했습니다.

- [alembic/versions/20260727_0006_add_pgvector_column.py](../alembic/versions/20260727_0006_add_pgvector_column.py)
  - `CREATE EXTENSION IF NOT EXISTS vector`를 실행합니다.
  - `memory_embeddings.embedding VECTOR(1536)` 컬럼을 추가합니다.
  - 기존 JSON embedding 중 1536차원 데이터만 안전하게 이전합니다.
  - cosine 검색용 부분 HNSW index를 추가합니다.

- [app/db/models.py](../app/db/models.py)
  - `MemoryEmbedding.embedding`을 `VECTOR(1536)` ORM 컬럼으로 선언했습니다.

- [app/repositories/memory_embedding_repository.py](../app/repositories/memory_embedding_repository.py)
  - 새 embedding을 JSON과 pgvector 컬럼에 병행 저장합니다.

- [tests/test_pgvector_integration.py](../tests/test_pgvector_integration.py)
  - 실제 PostgreSQL에서 extension과 1536차원 벡터 왕복 저장을 검증합니다.

## 왜 JSON 컬럼을 바로 삭제하지 않았나

운영 migration은 새 컬럼 추가, 데이터 이전, 애플리케이션 전환, 기존 컬럼 제거를 한 번에
처리하지 않는 편이 안전합니다. 현재는 다음 과도기 구조입니다.

```text
memory_embeddings
├─ vector_json  기존 호환/복구용
└─ embedding    pgvector 검색용 VECTOR(1536)
```

새 코드는 두 컬럼에 모두 기록합니다. 기존 행 중 차원이 1536인 값만 migration이 새
컬럼으로 복사하며, 예전 32차원 hashing 값은 잘못 변환하지 않고 재색인 대상으로 남깁니다.
검색 전환과 재색인이 끝난 후 별도 migration에서 `vector_json`을 제거할 수 있습니다.

## 왜 1536차원으로 고정했나

PostgreSQL의 `VECTOR(n)`은 모든 행이 같은 차원을 가져야 HNSW index를 안정적으로
사용할 수 있습니다. 현재 기본 OpenAI 모델인 `text-embedding-3-small`의 기본 길이에
맞춰 1536으로 고정했습니다.

```dotenv
EMBEDDING_DIMENSIONS=1536
OPENAI_EMBEDDING_DIMENSIONS=1536
```

차원을 바꾸려면 환경변수만 수정하는 것이 아니라 다음 항목을 함께 변경해야 합니다.

1. 새 DB migration
2. ORM의 `VECTOR(n)`
3. provider 출력 차원
4. 기존 기억 전체 재색인
5. HNSW index 재생성

## HNSW cosine index

추가된 index는 embedding이 있는 행만 대상으로 합니다.

```sql
CREATE INDEX ix_memory_embeddings_embedding_cosine
ON memory_embeddings
USING hnsw (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL;
```

23단계에서는 `embedding.cosine_distance(query_vector)`를 사용해 DB에서 가까운 기억만
가져옵니다.

공식 참고 자료:

- [pgvector Docker 설치](https://github.com/pgvector/pgvector#docker)
- [pgvector-python SQLAlchemy 사용법](https://github.com/pgvector/pgvector-python#sqlalchemy)

## 실행과 검증

기존 named volume에 일반 PostgreSQL 데이터가 있더라도 같은 PostgreSQL 17 계열이므로
새 이미지가 이를 열 수 있습니다. migration 적용 전에는 새 vector 컬럼이 없습니다.

```powershell
cd backend
docker compose pull db
docker compose up --build
```

직접 migration 상태와 extension을 확인할 수 있습니다.

```powershell
docker compose exec api alembic current
docker compose exec db psql -U postgres -d character_chat `
  -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
```

통합 테스트는 pgvector PostgreSQL이 실행된 환경에서 다음처럼 켭니다.

```powershell
$env:RUN_DB_INTEGRATION = "1"
pytest tests/test_pgvector_integration.py -q
```

## 다음 단계

23단계에서는 기억 생성/수정 시 embedding을 자동 재색인하고, 사용자·캐릭터 범위를
지키는 의미 검색 API와 pgvector cosine query를 추가합니다.
