# 12단계: 스트리밍 저장 정책 통합 테스트

이번 단계의 목표는 스트리밍 응답이 DB에 저장되는 시점을 정확히 검증하는 것입니다.

스트리밍은 일반 응답보다 까다롭습니다. 사용자는 토큰을 실시간으로 보고 있지만, 서버는
아직 완성되지 않은 답변을 DB에 저장할지 말지 결정해야 합니다. 현재 설계는 다음 원칙을
따릅니다.

- 사용자 메시지는 LLM 호출 전에 먼저 저장한다.
- assistant 메시지는 스트리밍이 정상 완료된 뒤 전체 조각을 합쳐 저장한다.
- 스트리밍 중간에 실패하면 불완전한 assistant 메시지는 저장하지 않는다.

## 이번 단계에서 추가·수정한 파일

- [backend/tests/test_streaming_persistence_integration.py](../tests/test_streaming_persistence_integration.py)
  - 실제 PostgreSQL에서 정상 스트리밍 저장을 검증합니다.
  - 스트리밍 중간 실패 시 assistant 메시지가 남지 않는지 검증합니다.

- [backend/README.md](../README.md)
  - 현재 단계를 12단계로 갱신했습니다.

- [backend/docs/README.md](README.md)
  - 12단계 문서 링크를 추가했습니다.

## 테스트 흐름

정상 스트리밍:

```text
ChatService.start_turn()
  → user 메시지 저장
  → fake LLM stream: "안녕" + ", " + "스트리밍!"
  → stream_reply 정상 완료
  → assistant 메시지 "안녕, 스트리밍!" 저장
```

실패 스트리밍:

```text
ChatService.start_turn()
  → user 메시지 저장
  → fake LLM stream: "불완전" 전송 후 예외
  → stream_reply 예외 종료
  → assistant 메시지는 저장하지 않음
```

## 왜 이런 정책을 쓰나?

불완전한 AI 답변을 대화 기록에 저장하면 다음 요청의 문맥이 오염될 수 있습니다. 사용자는
화면에서 일부 토큰을 봤더라도, 서버 입장에서는 완성된 assistant 발화가 아닙니다.

그래서 현재 구조는 `stream_reply()`가 끝까지 정상 순회된 경우에만 `complete_turn()`을
호출합니다.

```text
정상 완료 → assistant 저장
중간 실패 → user만 저장
```

이 정책 덕분에 재시도 버튼이나 오류 안내 UI를 만들 때도 대화 기록이 비교적 깨끗하게
유지됩니다.

## 이번 단계의 한계

- 실제 HTTP SSE 라우터까지 통과하는 테스트는 아직 아닙니다.
- 브라우저 연결이 끊긴 경우의 ASGI cancellation은 별도 테스트하지 않았습니다.
- 실패한 user 메시지를 어떻게 재시도 UX로 보여줄지는 아직 프론트엔드 과제입니다.

다음 단계에서는 실제 FastAPI 앱에 DB 세션과 가짜 LLM을 주입해 HTTP 레벨에서 더 넓은
통합 테스트를 추가합니다.
