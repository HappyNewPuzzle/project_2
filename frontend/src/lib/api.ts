import { consumeSseStream } from "./sse";
import type {
  AuthToken,
  Character,
  CharacterCreate,
  CharacterUpdate,
  ChatRequest,
  Conversation,
  SavedMessage,
  SseEvent,
} from "../types/api";

// HTTP 상태와 백엔드 응답 본문을 함께 보존하는 프론트엔드 공통 오류입니다.
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// 사용자가 입력한 Base URL 뒤 슬래시를 제거해 모든 경로 조합을 일정하게 만듭니다.
export function normalizeApiBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

// 백엔드 오류 응답을 화면에 표시할 수 있는 하나의 오류 형식으로 바꿉니다.
async function ensureOk(response: Response): Promise<Response> {
  if (response.ok) {
    return response;
  }
  const body = await response.text();
  let detail = body;
  try {
    const parsed = JSON.parse(body) as unknown;
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      "detail" in parsed &&
      typeof parsed.detail === "string"
    ) {
      detail = parsed.detail;
    }
  } catch {
    // JSON이 아닌 proxy 오류 페이지라면 원문을 그대로 사용합니다.
  }
  throw new ApiError(
    response.status,
    `${response.status} ${response.statusText}: ${detail}`,
  );
}

// Base URL과 access token을 묶어 화면 컴포넌트에서 fetch 세부사항을 숨깁니다.
export class ApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly token: string,
  ) {}

  private url(path: string): string {
    return `${normalizeApiBaseUrl(this.baseUrl)}${path}`;
  }

  private authHeaders(extra: HeadersInit = {}): Headers {
    const headers = new Headers(extra);
    if (this.token) {
      headers.set("Authorization", `Bearer ${this.token}`);
    }
    return headers;
  }

  private async json<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(this.url(path), {
      ...init,
      headers: this.authHeaders(init.headers),
    });
    await ensureOk(response);
    return (await response.json()) as T;
  }

  async register(email: string, password: string): Promise<void> {
    await this.json("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  }

  async login(email: string, password: string): Promise<AuthToken> {
    const form = new URLSearchParams({ username: email, password });
    return this.json<AuthToken>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
  }

  async createCharacter(payload: CharacterCreate): Promise<Character> {
    return this.json<Character>("/characters", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  // 한 화면에서 선택할 수 있도록 현재 API 최대 크기인 100개까지 조회합니다.
  async listCharacters(): Promise<Character[]> {
    return this.json<Character[]>("/characters?offset=0&limit=100");
  }

  async updateCharacter(
    characterId: string,
    payload: CharacterUpdate,
  ): Promise<Character> {
    return this.json<Character>(`/characters/${characterId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  async deleteCharacter(characterId: string): Promise<void> {
    const response = await fetch(this.url(`/characters/${characterId}`), {
      method: "DELETE",
      headers: this.authHeaders(),
    });
    await ensureOk(response);
  }

  async saveMemory(characterId: string): Promise<void> {
    await this.json("/memories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: "사용자는 React 프론트엔드에서 테스트 중이다",
        character_id: characterId || null,
        importance: 3,
      }),
    });
  }

  async listConversations(): Promise<Conversation[]> {
    return this.json<Conversation[]>("/conversations");
  }

  async listMessages(conversationId: string): Promise<SavedMessage[]> {
    return this.json<SavedMessage[]>(
      `/conversations/${conversationId}/messages`,
    );
  }

  async deleteConversation(conversationId: string): Promise<void> {
    const response = await fetch(
      this.url(`/conversations/${conversationId}`),
      {
        method: "DELETE",
        headers: this.authHeaders(),
      },
    );
    await ensureOk(response);
  }

  async streamChat(
    payload: ChatRequest,
    onEvent: (event: SseEvent) => void | Promise<void>,
  ): Promise<void> {
    const response = await fetch(this.url("/chat/stream"), {
      method: "POST",
      headers: this.authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
    await ensureOk(response);
    if (!response.body) {
      throw new ApiError(502, "Streaming response body is missing.");
    }
    await consumeSseStream(response.body, onEvent);
  }
}
