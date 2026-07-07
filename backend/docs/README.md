# 개발 단계별 학습 문서

이 디렉터리는 완성된 코드만 보는 대신, 프로젝트가 어떤 이유로 현재 구조에
도달했는지 단계별로 설명합니다.

## 추천 학습 순서

1. [전체 구조](architecture.md)
2. [1단계: 최소 채팅 API](step-01-minimal-chat.md)
3. [2단계: SSE 스트리밍](step-02-streaming.md)
4. [3단계: PostgreSQL 영속화](step-03-persistence.md)
5. [4단계: 캐릭터와 최근 문맥](step-04-character-context.md)
6. [5단계: JWT 인증과 소유권](step-05-authentication.md)
7. [6단계: 장기 기억](step-06-long-term-memory.md)
8. [7단계: 운영과 Docker](step-07-operations.md)
9. [8단계: GitHub Actions CI](step-08-ci.md)
10. [9단계: CI migration 검증](step-09-migration-ci.md)

각 문서를 읽은 뒤 문서에 링크된 실제 파일을 나란히 열어 보는 것을 권장합니다.
라우터에서 시작해 서비스, repository, DB 모델 순으로 따라가면 요청 한 건의 흐름을
가장 쉽게 이해할 수 있습니다.

## 현재 계층의 한 문장 정의

- `api/routes`: HTTP 요청을 받고 HTTP/SSE 응답으로 변환
- `schemas`: 외부 데이터의 형식과 검증 규칙
- `services`: 실제 서비스 규칙과 작업 순서
- `repositories`: SQLAlchemy 쿼리와 ORM 조작
- `db`: 테이블 구조와 세션 수명
- `llm_service`: 외부 LLM SDK를 감싸는 교체 지점
- `alembic`: DB 구조 변경 이력
- `tests`: 외부 시스템 없이 각 계층의 계약 검증
- `.github/workflows`: GitHub에 push/PR 될 때 자동 검증하는 CI 설정
