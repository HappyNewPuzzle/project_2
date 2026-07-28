import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Character, MemorySearchResult } from "../types/api";
import {
  MemorySearchPanel,
  MemorySearchResults,
} from "./MemorySearchPanel";

const character: Character = {
  id: "character-1",
  owner_id: "user-1",
  name: "루나",
  description: "",
  personality: "",
  speaking_style: "",
  system_prompt: "",
  created_at: "2026-07-28T00:00:00Z",
  updated_at: "2026-07-28T00:00:00Z",
};

describe("MemorySearchPanel", () => {
  it("선택 캐릭터 검색 범위와 재색인 안내를 표시한다", () => {
    const html = renderToStaticMarkup(
      <MemorySearchPanel
        characters={[character]}
        selectedCharacterId={character.id}
        disabled={false}
        onSearch={vi.fn()}
        onReindex={vi.fn()}
      />,
    );

    expect(html).toContain("전역 + 루나");
    expect(html).toContain("최대 100개");
    expect(html).toContain("재색인 준비");
  });
});

describe("MemorySearchResults", () => {
  it("순위·유사도·범위와 escape된 기억 내용을 렌더링한다", () => {
    const results: MemorySearchResult[] = [
      {
        id: "memory-1",
        character_id: character.id,
        content: "<별과 우주>를 좋아한다.",
        importance: 5,
        is_active: true,
        score: 0.9342,
        created_at: "2026-07-28T00:00:00Z",
        updated_at: "2026-07-28T00:00:00Z",
      },
    ];
    const html = renderToStaticMarkup(
      <MemorySearchResults
        results={results}
        hasSearched={true}
        characterNames={new Map([[character.id, character.name]])}
      />,
    );

    expect(html).toContain("#1");
    expect(html).toContain("93.4%");
    expect(html).toContain("루나");
    expect(html).toContain("&lt;별과 우주&gt;");
  });

  it("검색 결과가 없으면 명시적인 빈 상태를 표시한다", () => {
    const html = renderToStaticMarkup(
      <MemorySearchResults
        results={[]}
        hasSearched={true}
        characterNames={new Map()}
      />,
    );

    expect(html).toContain("의미가 가까운 활성 기억이 없습니다");
  });
});
