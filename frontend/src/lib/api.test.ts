import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClient, normalizeApiBaseUrl } from "./api";

afterEach(() => {
  // 각 테스트가 교체한 전역 fetch를 원래 상태로 되돌립니다.
  vi.unstubAllGlobals();
});

describe("normalizeApiBaseUrl", () => {
  it("공백과 마지막 슬래시를 제거한다", () => {
    expect(normalizeApiBaseUrl("  http://127.0.0.1:8000/// ")).toBe(
      "http://127.0.0.1:8000",
    );
  });

  it("경로 중간의 슬래시는 유지한다", () => {
    expect(normalizeApiBaseUrl("https://example.com/api")).toBe(
      "https://example.com/api",
    );
  });
});

describe("ApiClient.listCharacters", () => {
  it("인증 header와 최대 목록 범위를 함께 전송한다", async () => {
    const characters = [
      {
        id: "character-1",
        owner_id: null,
        name: "루나",
        description: "달빛 도서관의 사서",
        personality: "",
        speaking_style: "차분한 말투",
        system_prompt: "",
        created_at: "2026-07-27T00:00:00Z",
        updated_at: "2026-07-27T00:00:00Z",
      },
    ];
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(characters), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://127.0.0.1:8000/", "access-token");

    await expect(client.listCharacters()).resolves.toEqual(characters);
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://127.0.0.1:8000/characters?offset=0&limit=100",
    );
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(request.headers).get("Authorization")).toBe(
      "Bearer access-token",
    );
    expect(request.credentials).toBe("include");
  });
});

describe("ApiClient character mutations", () => {
  it("캐릭터 수정 payload를 PATCH JSON으로 보낸다", async () => {
    const updatedCharacter = {
      id: "character-1",
      owner_id: "user-1",
      name: "수정된 루나",
      description: "",
      personality: "",
      speaking_style: "",
      system_prompt: "",
      created_at: "2026-07-27T00:00:00Z",
      updated_at: "2026-07-27T01:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(updatedCharacter), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://localhost:8000", "token");

    await expect(
      client.updateCharacter("character-1", { name: "수정된 루나" }),
    ).resolves.toEqual(updatedCharacter);
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(request.method).toBe("PATCH");
    expect(request.body).toBe(JSON.stringify({ name: "수정된 루나" }));
  });

  it("409 JSON detail을 ApiError 메시지로 보존한다", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: "Character is used by an existing conversation.",
          }),
          {
            status: 409,
            statusText: "Conflict",
            headers: { "Content-Type": "application/json" },
          },
        ),
      ),
    );
    const client = new ApiClient("http://localhost:8000", "token");

    await expect(client.deleteCharacter("character-1")).rejects.toMatchObject({
      status: 409,
      message:
        "409 Conflict: Character is used by an existing conversation.",
    });
  });
});

describe("ApiClient memory management", () => {
  it("기억 생성 범위와 중요도를 JSON으로 전송한다", async () => {
    const memory = {
      id: "memory-1",
      character_id: "character-1",
      content: "사용자는 별을 좋아한다.",
      importance: 4,
      is_active: true,
      created_at: "2026-07-27T00:00:00Z",
      updated_at: "2026-07-27T00:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(memory), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://localhost:8000", "token");

    await expect(
      client.createMemory({
        content: "사용자는 별을 좋아한다.",
        character_id: "character-1",
        importance: 4,
      }),
    ).resolves.toEqual(memory);
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(request.method).toBe("POST");
    expect(JSON.parse(request.body as string)).toEqual({
      content: "사용자는 별을 좋아한다.",
      character_id: "character-1",
      importance: 4,
    });
  });

  it("기억 활성 상태를 PATCH로 변경한다", async () => {
    const updated = {
      id: "memory-1",
      character_id: null,
      content: "전역 기억",
      importance: 3,
      is_active: false,
      created_at: "2026-07-27T00:00:00Z",
      updated_at: "2026-07-27T01:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(updated), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://localhost:8000", "token");

    await client.updateMemory("memory-1", { is_active: false });
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://localhost:8000/memories/memory-1",
    );
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(request.method).toBe("PATCH");
    expect(request.body).toBe(JSON.stringify({ is_active: false }));
  });

  it("기억 목록은 최대 100개 범위를 요청한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("[]", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://localhost:8000", "token");

    await expect(client.listMemories()).resolves.toEqual([]);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://localhost:8000/memories?offset=0&limit=100",
    );
  });

  it("기억 삭제를 인증된 DELETE 요청으로 보낸다", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://localhost:8000", "memory-token");

    await expect(client.deleteMemory("memory-1")).resolves.toBeUndefined();
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(request.method).toBe("DELETE");
    expect(new Headers(request.headers).get("Authorization")).toBe(
      "Bearer memory-token",
    );
  });
});

describe("ApiClient semantic memory operations", () => {
  it("검색어와 캐릭터 범위를 URL query로 안전하게 인코딩한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("[]", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://localhost:8000", "search-token");

    await expect(
      client.searchMemories("별과 우주 이야기", "character-1"),
    ).resolves.toEqual([]);
    const requestedUrl = new URL(fetchMock.mock.calls[0]?.[0] as string);
    expect(requestedUrl.pathname).toBe("/memories/search");
    expect(requestedUrl.searchParams.get("query")).toBe("별과 우주 이야기");
    expect(requestedUrl.searchParams.get("character_id")).toBe("character-1");
    expect(requestedUrl.searchParams.get("limit")).toBe("10");
  });

  it("재색인 결과의 처리 개수를 반환한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ indexed_count: 3 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://localhost:8000", "reindex-token");

    await expect(client.reindexMemories()).resolves.toBe(3);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://localhost:8000/memories/reindex?limit=100",
    );
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(request.method).toBe("POST");
    expect(new Headers(request.headers).get("Authorization")).toBe(
      "Bearer reindex-token",
    );
  });
});

describe("ApiClient unauthorized session handling", () => {
  it("401이면 refresh 후 새 access token으로 원 요청을 한 번 재시도한다", async () => {
    const onUnauthorized = vi.fn();
    const onTokenRefreshed = vi.fn();
    const characters = [{ id: "character-1", name: "루나" }];
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Expired access token." }), {
          status: 401,
          statusText: "Unauthorized",
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "renewed-token",
            token_type: "bearer",
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(characters), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient(
      "http://localhost:8000",
      "expired-token",
      onUnauthorized,
      onTokenRefreshed,
    );

    await expect(client.listCharacters()).resolves.toEqual(characters);
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "http://localhost:8000/auth/refresh",
    );
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: "POST",
      credentials: "include",
    });
    const retriedRequest = fetchMock.mock.calls[2]?.[1] as RequestInit;
    expect(new Headers(retriedRequest.headers).get("Authorization")).toBe(
      "Bearer renewed-token",
    );
    expect(onTokenRefreshed).toHaveBeenCalledWith("renewed-token");
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it("보호 API의 401은 callback을 호출하고 처리 표시를 남긴다", async () => {
    const onUnauthorized = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Invalid access token." }), {
          status: 401,
          statusText: "Unauthorized",
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const client = new ApiClient(
      "http://localhost:8000",
      "expired-token",
      onUnauthorized,
    );

    const error = await client.listCharacters().catch((caught: unknown) => caught);
    expect(onUnauthorized).toHaveBeenCalledOnce();
    expect(error).toMatchObject({
      status: 401,
      sessionHandled: true,
    });
  });

  it("로그인 실패 401은 기존 세션 callback을 호출하지 않는다", async () => {
    const onUnauthorized = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Invalid credentials." }), {
          status: 401,
          statusText: "Unauthorized",
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const client = new ApiClient(
      "http://localhost:8000",
      "existing-token",
      onUnauthorized,
    );

    const error = await client
      .login("user@example.com", "wrong-password")
      .catch((caught: unknown) => caught);
    expect(onUnauthorized).not.toHaveBeenCalled();
    expect(error).toMatchObject({
      status: 401,
      sessionHandled: false,
    });
  });

  it("로그인과 로그아웃에도 HttpOnly 쿠키용 credentials 옵션을 사용한다", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "access-token",
            token_type: "bearer",
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://localhost:8000", "");

    await client.login("user@example.com", "password");
    await client.logout();

    expect(
      (fetchMock.mock.calls[0]?.[1] as RequestInit).credentials,
    ).toBe("include");
    expect(
      (fetchMock.mock.calls[1]?.[1] as RequestInit).credentials,
    ).toBe("include");
  });
});
