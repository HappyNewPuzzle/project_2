import { FormEvent, useEffect, useMemo, useState } from "react";
import type {
  Character,
  Memory,
  MemoryCreate,
  MemoryUpdate,
} from "../types/api";

interface MemoryPanelProps {
  memories: Memory[];
  characters: Character[];
  selectedCharacterId: string;
  disabled: boolean;
  onReload: () => Promise<void>;
  onCreate: (payload: MemoryCreate) => Promise<boolean>;
  onUpdate: (memoryId: string, payload: MemoryUpdate) => Promise<void>;
  onDelete: (memoryId: string) => Promise<boolean>;
}

type MemoryFilter = "all" | "global" | string;

// 기억 작성, 범위 필터, 활성화와 삭제를 하나의 학습용 관리 화면으로 제공합니다.
export function MemoryPanel({
  memories,
  characters,
  selectedCharacterId,
  disabled,
  onReload,
  onCreate,
  onUpdate,
  onDelete,
}: MemoryPanelProps) {
  const [content, setContent] = useState("");
  const [importance, setImportance] = useState(3);
  const [createScope, setCreateScope] = useState(selectedCharacterId);
  const [filter, setFilter] = useState<MemoryFilter>("all");
  const [confirmingMemoryId, setConfirmingMemoryId] = useState("");

  // 캐릭터 선택이 바뀌면 새 기억의 기본 적용 범위도 그 캐릭터로 맞춥니다.
  useEffect(() => {
    setCreateScope(selectedCharacterId);
  }, [selectedCharacterId]);

  // 캐릭터 ID를 사람이 읽을 수 있는 이름으로 바꾸기 위한 lookup입니다.
  const characterNames = useMemo(
    () => new Map(characters.map((character) => [character.id, character.name])),
    [characters],
  );

  const visibleMemories = useMemo(() => {
    if (filter === "all") {
      return memories;
    }
    if (filter === "global") {
      return memories.filter((memory) => memory.character_id === null);
    }
    return memories.filter((memory) => memory.character_id === filter);
  }, [filter, memories]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedContent = content.trim();
    if (!normalizedContent) {
      return;
    }
    const created = await onCreate({
      content: normalizedContent,
      character_id: createScope || null,
      importance,
    });
    // embedding/API 저장이 실패하면 사용자가 작성한 내용을 지우지 않습니다.
    if (created) {
      setContent("");
    }
  }

  async function requestDelete(memoryId: string) {
    if (confirmingMemoryId !== memoryId) {
      setConfirmingMemoryId(memoryId);
      return;
    }
    const deleted = await onDelete(memoryId);
    if (deleted) {
      setConfirmingMemoryId("");
    }
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <span className="step-number">5</span>
        <div>
          <h2>장기 기억</h2>
          <p>대화에 다시 사용할 사용자 정보와 선호를 관리합니다.</p>
        </div>
      </div>

      <form className="form-grid" onSubmit={submit}>
        <label>
          기억할 내용
          <textarea
            value={content}
            maxLength={5_000}
            placeholder="예: 사용자는 천문학과 별 사진을 좋아한다."
            disabled={disabled}
            required
            onChange={(event) => setContent(event.target.value)}
          />
        </label>
        <div className="memory-options">
          <label>
            적용 범위
            <select
              value={createScope}
              disabled={disabled}
              onChange={(event) => setCreateScope(event.target.value)}
            >
              <option value="">모든 캐릭터에 적용</option>
              {characters.map((character) => (
                <option key={character.id} value={character.id}>
                  {character.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            중요도
            <select
              value={importance}
              disabled={disabled}
              onChange={(event) => setImportance(Number(event.target.value))}
            >
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button disabled={disabled || !content.trim()}>기억 저장</button>
      </form>

      <div className="memory-toolbar">
        <label>
          목록 범위
          <select
            value={filter}
            disabled={disabled}
            onChange={(event) => setFilter(event.target.value)}
          >
            <option value="all">전체 기억</option>
            <option value="global">모든 캐릭터 기억</option>
            {characters.map((character) => (
              <option key={character.id} value={character.id}>
                {character.name}
              </option>
            ))}
          </select>
        </label>
        <button className="secondary" disabled={disabled} onClick={onReload}>
          기억 새로고침
        </button>
      </div>

      <div className="memory-list" aria-live="polite">
        {visibleMemories.length === 0 ? (
          <p className="empty-state">이 범위에 저장된 기억이 없습니다.</p>
        ) : (
          visibleMemories.map((memory) => (
            <article
              key={memory.id}
              className={`memory-item ${memory.is_active ? "" : "inactive"}`}
            >
              <div className="memory-item-header">
                <span>
                  {memory.character_id
                    ? characterNames.get(memory.character_id) ??
                      "알 수 없는 캐릭터"
                    : "모든 캐릭터"}
                </span>
                <small>중요도 {memory.importance}</small>
              </div>
              <p>{memory.content}</p>
              <div className="actions">
                <button
                  className="secondary compact"
                  disabled={disabled}
                  onClick={() =>
                    onUpdate(memory.id, { is_active: !memory.is_active })
                  }
                >
                  {memory.is_active ? "비활성화" : "활성화"}
                </button>
                <select
                  aria-label={`${memory.content} 중요도`}
                  value={memory.importance}
                  disabled={disabled}
                  onChange={(event) =>
                    onUpdate(memory.id, {
                      importance: Number(event.target.value),
                    })
                  }
                >
                  {[1, 2, 3, 4, 5].map((value) => (
                    <option key={value} value={value}>
                      중요도 {value}
                    </option>
                  ))}
                </select>
                <button
                  className="danger compact"
                  disabled={disabled}
                  onClick={() => requestDelete(memory.id)}
                >
                  {confirmingMemoryId === memory.id ? "정말 삭제" : "삭제"}
                </button>
                {confirmingMemoryId === memory.id && (
                  <button
                    className="secondary compact"
                    disabled={disabled}
                    onClick={() => setConfirmingMemoryId("")}
                  >
                    취소
                  </button>
                )}
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
