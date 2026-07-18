# 10단계: 실제 사용자 흐름 통합 테스트

이번 단계의 목표는 기능별 테스트를 넘어 실제 사용자 흐름이 PostgreSQL 위에서 끝까지
이어지는지 검증하는 것입니다.

## 이번 단계에서 추가·수정한 파일

- [backend/tests/test_user_flow_integration.py](../tests/test_user_flow_integration.py)
  - 실제 PostgreSQL 세션을 사용합니다.
  - 회원가입 → 로그인 → 캐릭터 생성 → 장기 기억 저장 → 채팅 응답 저장 흐름을 검증합니다.
  - 외부 LLM API 대신 `RecordingLLMProvider`라는 가짜 provider를 사용합니다.

- [.github/workflows/backend-ci.yml](../../.github/workflows/backend-ci.yml)
  - migration job에서 `RUN_DB_INTEGRATION=1`을 켠 뒤 통합 테스트를 실행합니다.

- [backend/README.md](../README.md)
  - 현재 단계를 10단계로 갱신했습니다.

- [backend/docs/README.md](README.md)
  - 10단계 문서 링크를 추가했습니다.

- [backend/docs/architecture.md](architecture.md)
  - CI 검증 흐름에 PostgreSQL 통합 테스트를 추가했습니다.

## 왜 API E2E가 아니라 Service 통합 테스트인가?

현재 프로젝트에는 이미 라우터별 빠른 API 계약 테스트가 있습니다. 그 테스트들은 FastAPI
의존성을 가짜 서비스로 바꿔서 HTTP 응답 형식과 상태 코드를 빠르게 확인합니다.

이번 단계에서 확인하고 싶은 것은 조금 다릅니다.

- 실제 SQLAlchemy 세션에서 commit이 정상 동작하는가?
- 회원가입 후 같은 사용자 ID로 캐릭터와 기억이 연결되는가?
- ChatService가 최근 메시지와 장기 기억을 LLM 입력으로 조립하는가?
- LLM 답변 완료 후 assistant 메시지가 DB에 저장되는가?

이 목적에는 라우터까지 모두 통과하는 E2E보다 Service + 실제 DB 통합 테스트가 더 작고
명확합니다. 외부 OpenAI API는 가짜 provider로 대체해 비용과 네트워크 변수를 제거했습니다.

## 테스트 흐름

```text
PostgreSQL 준비
  → alembic upgrade head
  → AuthService.register()
  → AuthService.login()
  → CharacterService.create()
  → MemoryService.create()
  → ChatService.reply()
      → 사용자 메시지 저장
      → 장기 기억 조회
      → 캐릭터 instructions 조립
      → 가짜 LLM generate()
      → assistant 메시지 저장
  → messages 테이블 검증
```

## `RUN_DB_INTEGRATION=1`을 둔 이유

통합 테스트는 실제 PostgreSQL이 필요합니다. 그래서 평소 로컬에서 `pytest`만 실행할 때는
자동으로 skip됩니다.

```python
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="RUN_DB_INTEGRATION=1일 때만 PostgreSQL 통합 테스트를 실행한다.",
)
```

이 구조의 장점은 다음과 같습니다.

- 빠른 단위/API 테스트는 계속 빠르게 유지됩니다.
- CI처럼 DB가 준비된 환경에서는 더 깊은 검증을 수행합니다.
- 개발자가 원할 때만 로컬 PostgreSQL로 통합 테스트를 실행할 수 있습니다.

## CI에서 실행되는 방식

GitHub Actions의 `migration` job은 이제 다음 순서로 실행됩니다.

```text
PostgreSQL 17 service container 시작
  → alembic upgrade head
  → alembic current
  → RUN_DB_INTEGRATION=1 pytest tests/test_user_flow_integration.py -q
```

즉 migration이 성공한 DB 위에서 실제 서비스 흐름까지 확인합니다.

## 로컬 실행 방법

이미 PostgreSQL과 migration이 준비되어 있다면 다음처럼 실행할 수 있습니다.

```powershell
cd backend
$env:RUN_DB_INTEGRATION = "1"
pytest tests/test_user_flow_integration.py -q
```

Docker Compose로 별도 PostgreSQL을 띄우는 경우에는 먼저 DB를 준비합니다.

```powershell
docker compose up -d db
alembic upgrade head
$env:RUN_DB_INTEGRATION = "1"
pytest tests/test_user_flow_integration.py -q
```

## 이번 단계의 한계

- FastAPI HTTP 라우터까지 모두 통과하는 end-to-end 테스트는 아직 아닙니다.
- 스트리밍 응답의 실제 DB 저장 흐름은 별도로 검증하지 않았습니다.
- 사용자 간 권한 격리 시나리오를 PostgreSQL 통합 테스트로 넓히지는 않았습니다.

다음 단계에서는 이 통합 테스트 기반 위에 `/health/ready`와 실제 ASGI 앱 기동 검증,
또는 권한 격리 통합 테스트를 추가할 수 있습니다.
