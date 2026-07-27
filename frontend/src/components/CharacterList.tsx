import type { Character } from "../types/api";

interface CharacterListProps {
  characters: Character[];
  selectedCharacterId: string;
  disabled: boolean;
  onReload: () => Promise<void>;
  onSelect: (character: Character) => void;
}

// 서버의 캐릭터 목록을 선택 가능한 카드로 표현하는 전용 컴포넌트입니다.
export function CharacterList({
  characters,
  selectedCharacterId,
  disabled,
  onReload,
  onSelect,
}: CharacterListProps) {
  return (
    <section className="panel">
      <div className="section-heading">
        <span className="step-number">3</span>
        <div>
          <h2>캐릭터 선택</h2>
          <p>공용 캐릭터 또는 내가 만든 캐릭터로 새 대화를 시작합니다.</p>
        </div>
      </div>

      <button className="secondary" disabled={disabled} onClick={onReload}>
        캐릭터 새로고침
      </button>

      <div className="character-list" aria-live="polite">
        {characters.length === 0 ? (
          <p className="empty-state">불러온 캐릭터가 없습니다.</p>
        ) : (
          characters.map((character) => (
            <button
              key={character.id}
              className={`character-item ${
                character.id === selectedCharacterId ? "active" : ""
              }`}
              disabled={disabled}
              aria-pressed={character.id === selectedCharacterId}
              onClick={() => onSelect(character)}
            >
              <span className="character-item-header">
                <strong>{character.name}</strong>
                <small>{character.owner_id ? "내 캐릭터" : "공용"}</small>
              </span>
              <span className="character-description">
                {character.description || "설명이 없습니다."}
              </span>
              {character.speaking_style && (
                <span className="character-style">
                  말투 · {character.speaking_style}
                </span>
              )}
            </button>
          ))
        )}
      </div>
    </section>
  );
}
