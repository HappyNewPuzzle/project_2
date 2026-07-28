import { consumeSseStream } from "./sse";
import type {
  AuthToken,
  Character,
  CharacterCreate,
  CharacterUpdate,
  ChatRequest,
  Conversation,
  Memory,
  MemoryCreate,
  MemoryReindexResponse,
  MemorySearchResult,
  MemoryUpdate,
  SavedMessage,
  SseEvent,
} from "../types/api";

// HTTP 상태와 백엔드 응답 본문을 함께 보존하는 프론트엔드 공통 오류입니다.
export class ApiError extends Error {
  public sessionHandled = false;

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
  private refreshPromise: Promise<string | null> | null = null;

  constructor(
    private readonly baseUrl: string,
    private token: string,
    private readonly onUnauthorized?: () => void,
    private readonly onTokenRefreshed?: (accessToken: string) => void,
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

  // 보호 API의 401만 App에 알리고 원래 ApiError도 호출자에게 전달합니다.
  private async checked(
    response: Response,
    notifyUnauthorized = true,
  ): Promise<Response> {
    try {
      return await ensureOk(response);
    } catch (error) {
      if (
        notifyUnauthorized &&
        this.token &&
        error instanceof ApiError &&
        error.status === 401
      ) {
        // App이 일반 오류 문구로 만료 안내를 덮어쓰지 않게 처리 여부를 남깁니다.
        error.sessionHandled = true;
        this.onUnauthorized?.();
      }
      throw error;
    }
  }

  // 동시에 여러 API가 401이어도 refresh 요청은 하나만 실행해 token 회전 충돌을 막습니다.
  private async renewAccessToken(): Promise<string | null> {
    if (!this.refreshPromise) {
      this.refreshPromise = fetch(this.url("/auth/refresh"), {
        method: "POST",
        credentials: "include",
      })
        .then(async (response) => {
          if (!response.ok) {
            return null;
          }
          const auth = (await response.json()) as AuthToken;
          this.token = auth.access_token;
          this.onTokenRefreshed?.(auth.access_token);
          return auth.access_token;
        })
        .catch(() => null)
        .finally(() => {
          this.refreshPromise = null;
        });
    }
    return this.refreshPromise;
  }

  // 쿠키 전송, 401 갱신, 원 요청 1회 재시도를 모든 보호 API에 동일하게 적용합니다.
  private async request(
    path: string,
    init: RequestInit = {},
    allowRefresh = true,
    notifyUnauthorized = true,
  ): Promise<Response> {
    const send = () =>
      fetch(this.url(path), {
        ...init,
        credentials: "include",
        headers: this.authHeaders(init.headers),
      });

    let response = await send();
    if (response.status === 401 && this.token && allowRefresh) {
      const renewedToken = await this.renewAccessToken();
      if (renewedToken) {
        response = await send();
      }
    }
    return this.checked(response, notifyUnauthorized);
  }

  private async json<T>(
    path: string,
    init: RequestInit = {},
    allowRefresh = true,
    notifyUnauthorized = true,
  ): Promise<T> {
    const response = await this.request(
      path,
      init,
      allowRefresh,
      notifyUnauthorized,
    );
    return (await response.json()) as T;
  }

  async register(email: string, password: string): Promise<void> {
    await this.json(
      "/auth/register",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      },
      false,
      false,
    );
  }

  async login(email: string, password: string): Promise<AuthToken> {
    const form = new URLSearchParams({ username: email, password });
    return this.json<AuthToken>(
      "/auth/login",
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: form,
      },
      false,
      false,
    );
  }

  async logout(): Promise<void> {
    // logout은 access token이 없어도 HttpOnly 쿠키만으로 서버 session을 폐기할 수 있습니다.
    await this.request(
      "/auth/logout",
      { method: "POST" },
      false,
      false,
    );
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
    await this.request(`/characters/${characterId}`, {
      method: "DELETE",
    });
  }

  async createMemory(payload: MemoryCreate): Promise<Memory> {
    return this.json<Memory>("/memories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  async listMemories(): Promise<Memory[]> {
    return this.json<Memory[]>("/memories?offset=0&limit=100");
  }

  async updateMemory(
    memoryId: string,
    payload: MemoryUpdate,
  ): Promise<Memory> {
    return this.json<Memory>(`/memories/${memoryId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  async deleteMemory(memoryId: string): Promise<void> {
    await this.request(`/memories/${memoryId}`, {
      method: "DELETE",
    });
  }

  async searchMemories(
    query: string,
    characterId: string | null,
  ): Promise<MemorySearchResult[]> {
    const params = new URLSearchParams({
      query,
      limit: "10",
    });
    if (characterId) {
      params.set("character_id", characterId);
    }
    return this.json<MemorySearchResult[]>(
      `/memories/search?${params.toString()}`,
    );
  }

  async reindexMemories(): Promise<number> {
    const response = await this.json<MemoryReindexResponse>(
      "/memories/reindex?limit=100",
      { method: "POST" },
    );
    return response.indexed_count;
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
    await this.request(`/conversations/${conversationId}`, {
      method: "DELETE",
    });
  }

  async streamChat(
    payload: ChatRequest,
    onEvent: (event: SseEvent) => void | Promise<void>,
  ): Promise<void> {
    const response = await this.request("/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.body) {
      throw new ApiError(502, "Streaming response body is missing.");
    }
    await consumeSseStream(response.body, onEvent);
  }
}
