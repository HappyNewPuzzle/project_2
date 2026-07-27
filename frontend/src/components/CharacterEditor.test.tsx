import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Character } from "../types/api";
import { CharacterEditor } from "./CharacterEditor";

function makeCharacter(ownerId: string | null): Character {
  return {
    id: "character-1",
    owner_id: ownerId,
    name: "루나",
    description: "달빛 사서",
    personality: "차분함",
    speaking_style: "다정한 존댓말",
    system_prompt: "항상 캐릭터를 유지한다.",
    created_at: "2026-07-27T00:00:00Z",
    updated_at: "2026-07-27T00:00:00Z",
  };
}

describe("CharacterEditor", () => {
  it("공용 캐릭터에는 편집 폼과 삭제 버튼을 노출하지 않는다", () => {
    const html = renderToStaticMarkup(
      <CharacterEditor
        character={makeCharacter(null)}
        disabled={false}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(html).toContain("읽기 전용");
    expect(html).not.toContain("변경사항 저장");
    expect(html).not.toContain("캐릭터 삭제");
  });

  it("내 캐릭터에는 전체 편집 필드와 관리 버튼을 표시한다", () => {
    const html = renderToStaticMarkup(
      <CharacterEditor
        character={makeCharacter("user-1")}
        disabled={false}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(html).toContain("시스템 프롬프트");
    expect(html).toContain("변경사항 저장");
    expect(html).toContain("캐릭터 삭제");
  });
});
