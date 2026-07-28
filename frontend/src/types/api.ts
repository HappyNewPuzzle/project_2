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

// PATCH API는 바꾸려는 필드만 보낼 수 있도록 모두 선택 사항입니다.
export interface CharacterUpdate {
  name?: string;
  description?: string;
  personality?: string;
  speaking_style?: string;
  system_prompt?: string;
}

// 캐릭터 생성·목록 API가 반환하는 전체 공개 필드입니다.
export interface Character {
  id: string;
  owner_id: string | null;
  name: string;
  description: string;
  personality: string;
  speaking_style: string;
  system_prompt: string;
  created_at: string;
  updated_at: string;
}

// 새 장기 기억은 전역 또는 특정 캐릭터 범위에 연결됩니다.
export interface MemoryCreate {
  content: string;
  character_id: string | null;
  importance: number;
}

// 기억 내용, 중요도와 활성 상태는 각각 부분 수정할 수 있습니다.
export interface MemoryUpdate {
  content?: string;
  importance?: number;
  is_active?: boolean;
}

// 기억 목록과 CRUD 응답에서 사용하는 전체 공개 필드입니다.
export interface Memory {
  id: string;
  character_id: string | null;
  content: string;
  importance: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// 의미 검색 응답은 기억 데이터에 cosine similarity 점수를 추가합니다.
export interface MemorySearchResult extends Memory {
  score: number;
}

// 재색인 응답은 이번 요청에서 새 vector를 만든 기억 개수를 반환합니다.
export interface MemoryReindexResponse {
  indexed_count: number;
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
