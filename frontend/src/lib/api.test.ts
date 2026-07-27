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
  });
});
