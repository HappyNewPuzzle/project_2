import { describe, expect, it } from "vitest";
import { normalizeApiBaseUrl } from "./api";

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
