# AI Character Chat Backend

## 현재 단계

2단계까지 구현되어 있습니다. DB나 인증 없이 일반 JSON 응답과 SSE 스트리밍 응답을
모두 제공합니다.

```text
backend/
├─ app/
│  ├─ main.py
│  ├─ api/routes/chat.py
│  ├─ core/config.py
│  ├─ schemas/chat.py
│  └─ services/llm_service.py
├─ tests/test_chat.py
├─ requirements.txt
└─ .env.example
```

라우터는 HTTP 입출력과 상태 코드만 담당합니다. `LLMProvider`가 `generate()`와
`stream()` 경계를 정의하며, 현재 구현체인 `OpenAILLMProvider`는 나중에 다른 provider로
교체할 수 있습니다.

## 실행

PowerShell에서:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`의 `OPENAI_API_KEY`를 실제 키로 바꾼 뒤 서버를 시작합니다.

```powershell
uvicorn app.main:app --reload
```

API 문서는 `http://127.0.0.1:8000/docs`에서 확인할 수 있습니다.

## 테스트

실제 API 호출:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body '{"message":"안녕! 너는 누구야?"}'
```

스트리밍 응답은 `curl.exe -N`으로 버퍼링 없이 확인할 수 있습니다.

```powershell
curl.exe -N `
  -X POST http://127.0.0.1:8000/chat/stream `
  -H "Content-Type: application/json" `
  -d '{"message":"스트리밍으로 자기소개해줘"}'
```

응답 형식:

```text
event: token
data: {"delta":"안녕"}

event: token
data: {"delta":"!"}

event: done
data: {}
```

스트리밍 도중 오류가 발생하면 HTTP 상태 코드는 이미 전송된 뒤이므로 `event: error`로
오류를 알립니다. 클라이언트는 `token`, `done`, `error` 이벤트를 각각 처리해야 합니다.

API 키 없이 자동 테스트:

```powershell
pytest
```

테스트에서는 FastAPI 의존성을 가짜 LLM provider로 바꾸므로 비용과 네트워크 호출이
발생하지 않습니다.

## 전체 로드맵

1. 최소 채팅: 단일 메시지 요청, LLM 호출, JSON 응답 (완료)
2. 스트리밍: provider의 stream 인터페이스와 `StreamingResponse`/SSE 추가 (완료)
3. 영속화: PostgreSQL, SQLAlchemy, Alembic, 사용자·캐릭터·대화·메시지 모델
4. 캐릭터: 캐릭터별 시스템 프롬프트와 최근 대화 조립
5. 인증: 비밀번호 해시, JWT access token, 사용자별 리소스 권한
6. 장기 기억: 최근 N개 메시지, 요약 및 memory 테이블, 이후 pgvector 검색
7. 운영 준비: Docker, 구조화 로그, 관측성, rate limit, 테스트와 배포 자동화

## 다음 단계에서 개선할 점

- PostgreSQL과 SQLAlchemy async 세션 추가
- Alembic migration 구성
- 대화 및 메시지 모델과 repository 작성
- provider 오류를 rate limit, timeout, 인증 오류로 세분화
