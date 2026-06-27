# 4단계: 캐릭터와 최근 대화 문맥

## 목표

캐릭터별 이름·설명·성격·말투·추가 지침을 관리하고, 최근 대화 기록과 함께 LLM에
전달해 캐릭터다운 연속 대화를 만듭니다.

## 캐릭터 API

```text
POST   /characters
GET    /characters
GET    /characters/{id}
PATCH  /characters/{id}
DELETE /characters/{id}
```

사용 중인 캐릭터와 기본 캐릭터는 삭제할 수 없습니다. 대화 도중 다른 캐릭터 ID를
보내면 문맥과 인격이 섞이지 않도록 409를 반환합니다.

## 프롬프트 분리

```text
instructions:
  서비스 공통 규칙
  + 캐릭터 이름/설명/성격/말투/추가 지침

input:
  최근 user/assistant 메시지 N개
```

캐릭터 규칙은 사용자 대화보다 높은 우선순위의 `instructions`로 전달합니다.
대화 기록은 실제 발화 주체를 보존한 role/content 배열입니다.

## 문맥 제한

`CHAT_HISTORY_LIMIT` 기본값은 20입니다. 전체 대화를 매번 보내지 않는 이유는 다음과
같습니다.

- 대화가 길어져도 요청 비용과 지연이 무한히 증가하지 않습니다.
- 모델 context window를 관리하기 쉽습니다.
- 6단계 장기 기억에서 최근 문맥과 요약 기억의 역할을 분리할 수 있습니다.

repository는 DB에서 최신 N개를 내림차순으로 고른 뒤, LLM에는 다시 오래된 순서로
전달합니다.

## 기존 데이터 migration

`20260628_0002_add_characters.py`는 다음 순서를 지킵니다.

1. `characters` 테이블 생성
2. 고정 ID의 기본 Assistant 삽입
3. `conversations.character_id`를 nullable로 추가
4. 기존 대화를 기본 캐릭터에 연결
5. `NOT NULL`, 외래 키, 인덱스 적용

처음부터 NOT NULL 컬럼을 추가하면 기존 conversation 행 때문에 migration이
실패하므로 데이터 보정 후 제약을 강화합니다.

## 직접 확인할 코드

1. `app/services/character_service.py`의 프롬프트 조립
2. `app/services/chat_service.py`의 최근 메시지 변환
3. `app/services/llm_service.py`의 instructions/input 분리
4. `tests/test_chat_service.py`의 LLM 입력 검증

## 다음 단계

5단계에서는 사용자 회원가입, 비밀번호 해시, JWT 로그인, 캐릭터와 대화방 소유권을
추가합니다.
