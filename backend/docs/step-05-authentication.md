# 5단계: JWT 인증과 사용자별 소유권

## 목표

회원가입과 로그인을 추가하고, 로그인한 사용자만 채팅할 수 있으며 캐릭터와
대화 기록이 사용자 사이에서 섞이지 않도록 합니다.

## 인증 API

```text
POST /auth/register
POST /auth/login
GET  /auth/me
```

로그인은 OAuth2 password form을 사용합니다. `username` 필드에는 이메일을 넣고,
성공하면 `access_token`과 `token_type=bearer`를 받습니다.

## 비밀번호 처리

```text
원문 비밀번호 → pwdlib PasswordHash.recommended() → Argon2 해시 → DB 저장
로그인 비밀번호 + DB 해시 → verify() → 성공/실패
```

원문 비밀번호는 DB나 로그에 저장하지 않습니다. 존재하지 않는 이메일에도 dummy
해시 검증을 수행해 응답 시간만으로 계정 존재 여부를 추측하기 어렵게 합니다.

## JWT 처리

JWT에는 다음 최소 claim만 담습니다.

```json
{
  "sub": "사용자 UUID 문자열",
  "exp": "만료 시각"
}
```

JWT는 암호화가 아니라 서명입니다. payload에 비밀번호나 개인정보를 넣으면 안 됩니다.
`decode_access_token()`은 허용한 알고리즘을 명시하고 서명과 만료를 검증합니다.

## 현재 사용자 의존성

```text
Authorization: Bearer <token>
  → OAuth2PasswordBearer
  → decode_access_token()
  → UserRepository.get(sub)
  → 활성 사용자
  → ChatService / CharacterService
```

토큰이 유효해도 사용자가 삭제됐거나 비활성 상태면 접근을 허용하지 않습니다.

## 소유권 규칙

- 새 캐릭터의 `owner_id`는 현재 사용자 UUID입니다.
- 기본 캐릭터는 `owner_id=NULL`인 공용 읽기 전용 리소스입니다.
- 새 대화의 `user_id`는 현재 사용자 UUID입니다.
- 다른 사용자의 캐릭터 수정·삭제는 403입니다.
- 다른 사용자의 대화방 조회는 존재 여부 노출을 줄이기 위해 404처럼 처리합니다.

## migration

`20260628_0003_add_users_and_ownership.py`는 다음 순서로 실행됩니다.

1. `users` 테이블과 unique 이메일 인덱스 생성
2. 로그인할 수 없는 legacy 사용자 삽입
3. `characters.owner_id` 추가
4. `conversations.user_id`를 nullable로 추가
5. 기존 대화를 legacy 사용자에 연결
6. `NOT NULL`, 외래 키, 인덱스 적용

## 직접 확인할 코드

1. `app/core/security.py`: Argon2와 JWT
2. `app/services/auth_service.py`: 회원가입·로그인 순서
3. `app/api/dependencies.py`: 현재 사용자 주입
4. `app/services/chat_service.py`: 대화 소유권 확인
5. `tests/test_security.py`: 실제 해시와 JWT 왕복

## 다음 단계

6단계에서는 최근 메시지와 별도로 중요한 정보를 장기 기억으로 저장하고, 이후
pgvector 기반 검색으로 확장할 수 있는 구조를 추가합니다.
