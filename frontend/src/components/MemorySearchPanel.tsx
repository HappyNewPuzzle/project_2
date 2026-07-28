import { FormEvent, useEffect, useMemo, useState } from "react";
import type { Character, MemorySearchResult } from "../types/api";

interface MemorySearchPanelProps {
  characters: Character[];
  selectedCharacterId: string;
  disabled: boolean;
  onSearch: (
    query: string,
    characterId: string | null,
  ) => Promise<MemorySearchResult[] | null>;
  onReindex: () => Promise<number | null>;
}

function scoreLabel(score: number): string {
  return `${(score * 100).toFixed(1)}%`;
}

interface MemorySearchResultsProps {
  results: MemorySearchResult[];
  hasSearched: boolean;
  characterNames: Map<string, string>;
}

// 결과 표현을 분리해 검색 form 없이도 점수·범위 렌더링을 테스트할 수 있습니다.
export function MemorySearchResults({
  results,
  hasSearched,
  characterNames,
}: MemorySearchResultsProps) {
  return (
    <div className="search-results" aria-live="polite">
      {hasSearched && results.length === 0 ? (
        <p className="empty-state">의미가 가까운 활성 기억이 없습니다.</p>
      ) : (
        results.map((result, index) => (
          <article key={result.id} className="search-result">
            <div className="search-result-header">
              <strong>#{index + 1}</strong>
              <span>유사도 {scoreLabel(result.score)}</span>
            </div>
            <p>{result.content}</p>
            <small>
              {result.character_id
                ? characterNames.get(result.character_id) ??
                  "알 수 없는 캐릭터"
                : "모든 캐릭터"}{" "}
              · 중요도 {result.importance}
            </small>
          </article>
        ))
      )}
    </div>
  );
}

// 의미 검색 결과와 운영성 재색인 작업을 일반 기억 CRUD와 분리해 보여줍니다.
export function MemorySearchPanel({
  characters,
  selectedCharacterId,
  disabled,
  onSearch,
  onReindex,
}: MemorySearchPanelProps) {
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState(selectedCharacterId);
  const [results, setResults] = useState<MemorySearchResult[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [confirmingReindex, setConfirmingReindex] = useState(false);
  const [lastIndexedCount, setLastIndexedCount] = useState<number | null>(null);

  useEffect(() => {
    setScope(selectedCharacterId);
  }, [selectedCharacterId]);

  const characterNames = useMemo(
    () => new Map(characters.map((character) => [character.id, character.name])),
    [characters],
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedQuery = query.trim();
    if (!normalizedQuery) {
      return;
    }
    const found = await onSearch(normalizedQuery, scope || null);
    if (found !== null) {
      setResults(found);
      setHasSearched(true);
    }
  }

  async function requestReindex() {
    if (!confirmingReindex) {
      setConfirmingReindex(true);
      return;
    }
    const indexedCount = await onReindex();
    if (indexedCount !== null) {
      setLastIndexedCount(indexedCount);
      setConfirmingReindex(false);
    }
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <span className="step-number">6</span>
        <div>
          <h2>기억 의미 검색</h2>
          <p>키워드가 달라도 의미가 가까운 활성 기억을 찾습니다.</p>
        </div>
      </div>

      <form className="form-grid" onSubmit={submit}>
        <label>
          자연어 검색어
          <input
            value={query}
            maxLength={500}
            placeholder="예: 내가 좋아하는 취미가 뭐였지?"
            disabled={disabled}
            required
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label>
          검색 범위
          <select
            value={scope}
            disabled={disabled}
            onChange={(event) => setScope(event.target.value)}
          >
            <option value="">모든 활성 기억</option>
            {characters.map((character) => (
              <option key={character.id} value={character.id}>
                전역 + {character.name}
              </option>
            ))}
          </select>
        </label>
        <button disabled={disabled || !query.trim()}>의미 검색</button>
      </form>

      <MemorySearchResults
        results={results}
        hasSearched={hasSearched}
        characterNames={characterNames}
      />

      <div className="reindex-box">
        <div>
          <strong>기억 vector 재색인</strong>
          <p>
            현재 embedding provider의 vector가 없는 기억만 최대 100개 처리합니다.
          </p>
        </div>
        <div className="actions">
          <button
            className={confirmingReindex ? "danger" : "secondary"}
            disabled={disabled}
            onClick={requestReindex}
          >
            {confirmingReindex ? "재색인 실행 확인" : "재색인 준비"}
          </button>
          {confirmingReindex && (
            <button
              className="secondary"
              disabled={disabled}
              onClick={() => setConfirmingReindex(false)}
            >
              취소
            </button>
          )}
        </div>
        {lastIndexedCount !== null && (
          <p className="reindex-result">
            마지막 실행에서 {lastIndexedCount}개의 기억을 재색인했습니다.
          </p>
        )}
      </div>
    </section>
  );
}
