import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Character } from "../types/api";
import { CharacterList } from "./CharacterList";

const characters: Character[] = [
  {
    id: "public-character",
    owner_id: null,
    name: "<달빛 사서>",
    description: "공용 캐릭터",
    personality: "",
    speaking_style: "차분하게",
    system_prompt: "",
    created_at: "2026-07-27T00:00:00Z",
    updated_at: "2026-07-27T00:00:00Z",
  },
  {
    id: "my-character",
    owner_id: "user-1",
    name: "내 캐릭터",
    description: "",
    personality: "",
    speaking_style: "",
    system_prompt: "",
    created_at: "2026-07-27T00:00:00Z",
    updated_at: "2026-07-27T00:00:00Z",
  },
];

describe("CharacterList", () => {
  it("공용/소유 구분과 현재 선택 상태를 안전한 HTML로 렌더링한다", () => {
    const html = renderToStaticMarkup(
      <CharacterList
        characters={characters}
        selectedCharacterId="my-character"
        disabled={false}
        onReload={vi.fn()}
        onSelect={vi.fn()}
      />,
    );

    expect(html).toContain("공용");
    expect(html).toContain("내 캐릭터");
    expect(html).toContain('aria-pressed="true"');
    expect(html).toContain("&lt;달빛 사서&gt;");
    expect(html).not.toContain("<달빛 사서>");
  });
});
