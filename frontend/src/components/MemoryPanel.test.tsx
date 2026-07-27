import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Character, Memory } from "../types/api";
import { MemoryPanel } from "./MemoryPanel";

const character: Character = {
  id: "character-1",
  owner_id: "user-1",
  name: "루나",
  description: "",
  personality: "",
  speaking_style: "",
  system_prompt: "",
  created_at: "2026-07-27T00:00:00Z",
  updated_at: "2026-07-27T00:00:00Z",
};

const memories: Memory[] = [
  {
    id: "global-memory",
    character_id: null,
    content: "<별 사진>을 좋아한다.",
    importance: 5,
    is_active: true,
    created_at: "2026-07-27T00:00:00Z",
    updated_at: "2026-07-27T00:00:00Z",
  },
  {
    id: "character-memory",
    character_id: character.id,
    content: "루나와는 천문학 이야기를 한다.",
    importance: 3,
    is_active: false,
    created_at: "2026-07-27T00:00:00Z",
    updated_at: "2026-07-27T00:00:00Z",
  },
];

describe("MemoryPanel", () => {
  it("전역과 캐릭터 기억의 범위·중요도·활성 상태를 렌더링한다", () => {
    const html = renderToStaticMarkup(
      <MemoryPanel
        memories={memories}
        characters={[character]}
        selectedCharacterId={character.id}
        disabled={false}
        onReload={vi.fn()}
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(html).toContain("모든 캐릭터");
    expect(html).toContain("루나");
    expect(html).toContain("중요도 5");
    expect(html).toContain("활성화");
    expect(html).toContain("&lt;별 사진&gt;");
    expect(html).not.toContain("<별 사진>");
  });

  it("기억이 없으면 빈 상태를 표시한다", () => {
    const html = renderToStaticMarkup(
      <MemoryPanel
        memories={[]}
        characters={[]}
        selectedCharacterId=""
        disabled={false}
        onReload={vi.fn()}
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(html).toContain("저장된 기억이 없습니다");
  });
});
