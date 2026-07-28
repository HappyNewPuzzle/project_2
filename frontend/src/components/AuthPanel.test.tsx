import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AuthPanel } from "./AuthPanel";

function renderAuthPanel(authenticated: boolean): string {
  return renderToStaticMarkup(
    <AuthPanel
      apiBaseUrl="http://localhost:8000"
      authenticated={authenticated}
      disabled={false}
      onApiBaseUrlChange={vi.fn()}
      onRegister={vi.fn()}
      onLogin={vi.fn()}
      onLogout={vi.fn()}
    />,
  );
}

describe("AuthPanel", () => {
  it("로그인된 세션에만 로그아웃 동작을 표시한다", () => {
    expect(renderAuthPanel(true)).toContain("로그아웃");
    expect(renderAuthPanel(false)).not.toContain("로그아웃");
  });

  it("인증 상태에 맞는 안내 문구를 표시한다", () => {
    expect(renderAuthPanel(true)).toContain("현재 세션을 종료");
    expect(renderAuthPanel(false)).toContain("테스트 계정을 만들거나");
  });
});
