# 개발 단계별 학습 문서

이 디렉터리는 완성된 코드만 보는 대신, 프로젝트가 어떤 이유로 현재 구조에
도달했는지 단계별로 설명합니다.

## 추천 학습 순서

1. [프로젝트 종합 설명](../../PROJECT_OVERVIEW.md)
2. [전체 구조](architecture.md)
3. [1단계: 최소 채팅 API](step-01-minimal-chat.md)
4. [2단계: SSE 스트리밍](step-02-streaming.md)
5. [3단계: PostgreSQL 영속화](step-03-persistence.md)
6. [4단계: 캐릭터와 최근 문맥](step-04-character-context.md)
7. [5단계: JWT 인증과 소유권](step-05-authentication.md)
8. [6단계: 장기 기억](step-06-long-term-memory.md)
9. [7단계: 운영과 Docker](step-07-operations.md)
10. [8단계: GitHub Actions CI](step-08-ci.md)
11. [9단계: CI migration 검증](step-09-migration-ci.md)
12. [10단계: 사용자 흐름 통합 테스트](step-10-integration-tests.md)
13. [11단계: 사용자 권한 격리 통합 테스트](step-11-user-isolation.md)
14. [12단계: 스트리밍 저장 정책 통합 테스트](step-12-streaming-persistence.md)
15. [13단계: FastAPI HTTP 통합 테스트](step-13-api-integration.md)
16. [14단계: 최소 프론트엔드 채팅 UI](step-14-minimal-frontend.md)
17. [15단계: 배포 전 환경 점검](step-15-deployment-readiness.md)
18. [16단계: 대화방 목록과 메시지 조회 API](step-16-conversations-api.md)
19. [17단계: 프론트엔드 대화 목록 연결](step-17-frontend-conversations.md)
20. [18단계: Redis 기반 rate limit 준비](step-18-redis-rate-limit.md)
21. [19단계: 장기 기억 자동 추출 구조](step-19-auto-memory-extraction.md)
22. [20단계: embedding / pgvector 검색 준비](step-20-embedding-pgvector-readiness.md)
23. [21단계: OpenAI Embedding Provider](step-21-openai-embedding-provider.md)
24. [22단계: pgvector 저장 구조](step-22-pgvector-storage.md)
25. [23단계: 장기 기억 의미 검색](step-23-memory-semantic-search.md)
26. [24단계: 대화방 제목 자동 생성](step-24-conversation-titles.md)
27. [25단계: React + TypeScript 프론트엔드 구조화](step-25-react-frontend.md)

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
- `scripts`: 배포 전 환경 설정을 점검하는 운영 보조 도구
- `frontend/src`: React 컴포넌트, 상태, API client와 SSE parser
