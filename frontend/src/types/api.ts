// 백엔드 JWT 로그인 응답에서 프론트엔드가 사용하는 필드입니다.
export interface AuthToken {
  access_token: string;
  token_type: string;
}

// 캐릭터 생성 요청에 필요한 최소 입력입니다.
export interface CharacterCreate {
  name: string;
  description: string;
  speaking_style: string;
}

// 캐릭터 생성 응답에서 이후 채팅에 필요한 식별자와 표시 이름입니다.
export interface Character {
  id: string;
  name: string;
}

// 대화 목록 API 한 건의 응답 형식입니다.
export interface Conversation {
  id: string;
  user_id: string;
  character_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

// 저장된 메시지 API 응답 형식입니다.
export interface SavedMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

// 화면에 아직 저장되지 않은 스트리밍 메시지도 같은 구조로 표시하기 위한 타입입니다.
export interface ChatMessageView {
  id: string;
  role: "user" | "assistant";
  content: string;
}

// 스트리밍 채팅 요청은 새 대화와 기존 대화를 모두 표현합니다.
export interface ChatRequest {
  message: string;
  character_id?: string;
  conversation_id?: string;
}

// 백엔드 SSE conversation 이벤트 payload입니다.
export interface ConversationEventData {
  conversation_id: string;
  character_id: string;
}

// 백엔드 SSE token 이벤트 payload입니다.
export interface TokenEventData {
  delta: string;
}

// 파싱이 끝난 SSE 이벤트는 이름과 JSON payload를 함께 보관합니다.
export interface SseEvent {
  event: string;
  data: unknown;
}
