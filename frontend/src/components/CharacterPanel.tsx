import { FormEvent, useState } from "react";
import type { CharacterCreate } from "../types/api";

interface CharacterPanelProps {
  selectedCharacterId: string;
  disabled: boolean;
  onCreate: (payload: CharacterCreate) => Promise<void>;
}

// 캐릭터 작성 폼은 입력 상태를 소유하고, 생성된 ID는 App의 공통 상태로 올립니다.
export function CharacterPanel({
  selectedCharacterId,
  disabled,
  onCreate,
}: CharacterPanelProps) {
  const [name, setName] = useState("루나");
  const [description, setDescription] = useState("달빛 도서관의 사서");
  const [speakingStyle, setSpeakingStyle] = useState(
    "차분하고 다정한 존댓말",
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onCreate({
      name: name.trim(),
      description: description.trim(),
      speaking_style: speakingStyle.trim(),
    });
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <span className="step-number">2</span>
        <div>
          <h2>캐릭터 만들기</h2>
          <p>성격과 말투가 채팅의 시스템 프롬프트에 반영됩니다.</p>
        </div>
      </div>

      <form className="form-grid" onSubmit={submit}>
        <label>
          이름
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={disabled}
            required
          />
        </label>
        <label>
          설명
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            disabled={disabled}
            required
          />
        </label>
        <label>
          말투
          <input
            value={speakingStyle}
            onChange={(event) => setSpeakingStyle(event.target.value)}
            disabled={disabled}
            required
          />
        </label>
        <div className="actions">
          <button type="submit" disabled={disabled}>
            캐릭터 생성
          </button>
        </div>
      </form>

      <p className="identifier">
        선택 캐릭터: {selectedCharacterId || "아직 없음"}
      </p>
    </section>
  );
}
