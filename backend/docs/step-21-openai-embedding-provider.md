# 21단계: OpenAI Embedding Provider

이번 단계의 목표는 20단계에서 만든 `EmbeddingProvider` 경계에 실제 OpenAI 구현을
추가하는 것입니다. 아직 검색 API나 pgvector 쿼리는 만들지 않고, 텍스트를 실제 의미
벡터로 바꾸는 책임만 완성합니다.

## 추가·수정한 파일

- [app/core/config.py](../app/core/config.py)
  - `EMBEDDING_PROVIDER`로 `hashing`과 `openai`를 선택합니다.
  - OpenAI embedding 모델과 차원을 환경변수로 분리했습니다.

- [app/services/embedding_service.py](../app/services/embedding_service.py)
  - `OpenAIEmbeddingProvider`가 공식 Python SDK의 `embeddings.create()`를 호출합니다.
  - API 키 누락과 외부 API 실패를 애플리케이션 공통 예외로 바꿉니다.
  - `get_embedding_provider()`가 환경 설정에 맞는 구현체를 선택합니다.

- [tests/test_embedding_service.py](../tests/test_embedding_service.py)
  - 실제 API 비용 없이 가짜 client로 요청 인자와 반환 벡터를 검증합니다.
  - API 키 누락 오류를 검증합니다.

## 실행 설정

기본 설정은 외부 호출이 없는 개발용 hashing provider입니다.

```dotenv
EMBEDDING_PROVIDER=hashing
EMBEDDING_DIMENSIONS=32
```

실제 OpenAI embedding을 사용하려면 `.env`를 다음처럼 바꿉니다.

```dotenv
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=실제_API_키
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=1536
```

`text-embedding-3-small`의 기본 벡터 길이는 1536입니다. OpenAI의
`text-embedding-3` 계열은 `dimensions` 요청 매개변수로 더 짧은 벡터를 만들 수
있으므로, 이후 pgvector 컬럼 차원과 이 값을 반드시 같게 유지해야 합니다.

공식 참고 문서:
[OpenAI Vector embeddings guide](https://developers.openai.com/api/docs/guides/embeddings#how-to-get-embeddings)

## 요청 흐름

```text
환경변수
  -> get_embedding_provider()
     -> hashing: HashingEmbeddingProvider
     -> openai:  OpenAIEmbeddingProvider
                   -> OpenAI Embeddings API
                   -> list[float]
```

provider 이름에는 모델과 차원을 함께 저장합니다.

```text
openai:text-embedding-3-small:1536
```

이 정보가 있어야 모델이나 차원이 바뀐 뒤 기존 벡터와 새 벡터를 실수로 섞지 않고
재색인할 수 있습니다.

## 테스트

```powershell
cd backend
pytest -q
```

테스트는 OpenAI API를 호출하지 않습니다. 가짜 SDK client가
`model`, `input`, `encoding_format`, `dimensions` 인자를 받았는지만 확인합니다.

## 현재 한계와 다음 단계

- 아직 기억 생성 시 embedding을 자동 저장하지 않습니다.
- 아직 pgvector 컬럼과 similarity SQL을 사용하지 않습니다.
- 다른 provider로 전환하면 기존 기억의 재색인 작업이 필요합니다.

22단계에서는 pgvector가 포함된 PostgreSQL 이미지와 `VECTOR(n)` 컬럼으로 전환하고,
DB가 cosine 거리 계산을 담당하도록 준비합니다.
