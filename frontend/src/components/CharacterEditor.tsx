import { FormEvent, useEffect, useState } from "react";
import type { Character, CharacterUpdate } from "../types/api";

interface CharacterEditorProps {
  character?: Character;
  disabled: boolean;
  onUpdate: (characterId: string, payload: CharacterUpdate) => Promise<void>;
  onDelete: (characterId: string) => Promise<void>;
}

interface EditorFields {
  name: string;
  description: string;
  personality: string;
  speakingStyle: string;
  systemPrompt: string;
}

function fieldsFromCharacter(character?: Character): EditorFields {
  return {
    name: character?.name ?? "",
    description: character?.description ?? "",
    personality: character?.personality ?? "",
    speakingStyle: character?.speaking_style ?? "",
    systemPrompt: character?.system_prompt ?? "",
  };
}

// 선택된 캐릭터의 상세 보기와 소유 캐릭터 편집을 한 경계에서 처리합니다.
export function CharacterEditor({
  character,
  disabled,
  onUpdate,
  onDelete,
}: CharacterEditorProps) {
  const [fields, setFields] = useState(() => fieldsFromCharacter(character));
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  // 목록에서 다른 캐릭터를 선택하면 편집 중이던 입력과 삭제 확인을 초기화합니다.
  useEffect(() => {
    setFields(fieldsFromCharacter(character));
    setConfirmingDelete(false);
  }, [character]);

  function setField<Key extends keyof EditorFields>(
    key: Key,
    value: EditorFields[Key],
  ) {
    setFields((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!character?.owner_id) {
      return;
    }
    await onUpdate(character.id, {
      name: fields.name.trim(),
      description: fields.description.trim(),
      personality: fields.personality.trim(),
      speaking_style: fields.speakingStyle.trim(),
      system_prompt: fields.systemPrompt.trim(),
    });
  }

  async function requestDelete() {
    if (!character?.owner_id) {
      return;
    }
    if (!confirmingDelete) {
      setConfirmingDelete(true);
      return;
    }
    await onDelete(character.id);
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <span className="step-number">4</span>
        <div>
          <h2>캐릭터 관리</h2>
          <p>선택한 캐릭터의 상세 설정을 확인하고 관리합니다.</p>
        </div>
      </div>

      {!character ? (
        <p className="empty-state">먼저 캐릭터 목록에서 하나를 선택하세요.</p>
      ) : !character.owner_id ? (
        <div className="readonly-character">
          <strong>{character.name}</strong>
          <p>{character.description || "설명이 없습니다."}</p>
          <dl>
            <dt>성격</dt>
            <dd>{character.personality || "설정 없음"}</dd>
            <dt>말투</dt>
            <dd>{character.speaking_style || "설정 없음"}</dd>
          </dl>
          <p className="readonly-notice">
            공용 캐릭터는 모든 사용자가 함께 사용하므로 읽기 전용입니다.
          </p>
        </div>
      ) : (
        <form className="form-grid" onSubmit={submit}>
          <label>
            이름
            <input
              value={fields.name}
              maxLength={100}
              disabled={disabled}
              required
              onChange={(event) => setField("name", event.target.value)}
            />
          </label>
          <label>
            설명
            <textarea
              value={fields.description}
              maxLength={10_000}
              disabled={disabled}
              onChange={(event) => setField("description", event.target.value)}
            />
          </label>
          <label>
            성격
            <textarea
              value={fields.personality}
              maxLength={10_000}
              disabled={disabled}
              onChange={(event) => setField("personality", event.target.value)}
            />
          </label>
          <label>
            말투
            <textarea
              value={fields.speakingStyle}
              maxLength={10_000}
              disabled={disabled}
              onChange={(event) => setField("speakingStyle", event.target.value)}
            />
          </label>
          <label>
            시스템 프롬프트
            <textarea
              className="prompt-input"
              value={fields.systemPrompt}
              maxLength={20_000}
              disabled={disabled}
              onChange={(event) => setField("systemPrompt", event.target.value)}
            />
          </label>

          <div className="actions">
            <button type="submit" disabled={disabled || !fields.name.trim()}>
              변경사항 저장
            </button>
            <button
              type="button"
              className="danger"
              disabled={disabled}
              onClick={requestDelete}
            >
              {confirmingDelete ? "정말 삭제" : "캐릭터 삭제"}
            </button>
            {confirmingDelete && (
              <button
                type="button"
                className="secondary"
                disabled={disabled}
                onClick={() => setConfirmingDelete(false)}
              >
                취소
              </button>
            )}
          </div>
          {confirmingDelete && (
            <p className="delete-warning">
              삭제한 캐릭터는 복구할 수 없습니다. 기존 대화가 사용 중이면 서버가
              삭제를 거부합니다.
            </p>
          )}
        </form>
      )}
    </section>
  );
}
