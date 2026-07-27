import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import type { ChatMessageView } from "../types/api";

interface ChatPanelProps {
  messages: ChatMessageView[];
  disabled: boolean;
  canStartChat: boolean;
  onSend: (message: string) => Promise<void>;
  onReset: () => void;
}

// 채팅 패널은 입력 UX와 메시지 표현을 담당하고 스트리밍 처리는 App에 위임합니다.
export function ChatPanel({
  messages,
  disabled,
  canStartChat,
  onSend,
  onReset,
}: ChatPanelProps) {
  const [message, setMessage] = useState("");
  const messageEndRef = useRef<HTMLDivElement>(null);

  // 새 토큰이 붙을 때마다 가장 최근 메시지가 보이도록 아래로 이동합니다.
  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) {
      return;
    }
    setMessage("");
    await onSend(trimmed);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <section className="panel chat-panel">
      <div className="chat-header">
        <div className="section-heading">
          <span className="step-number">4</span>
          <div>
            <h2>스트리밍 채팅</h2>
            <p>Enter로 전송하고 Shift+Enter로 줄을 바꿉니다.</p>
          </div>
        </div>
        <button className="secondary" disabled={disabled} onClick={onReset}>
          새 대화
        </button>
      </div>

      <div className="messages" aria-live="polite">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <span>✦</span>
            <p>캐릭터를 선택하고 첫 메시지를 보내보세요.</p>
          </div>
        ) : (
          messages.map((item) => (
            <article
              key={item.id}
              className={`message message-${item.role}`}
            >
              <strong>{item.role === "user" ? "나" : "AI"}</strong>
              <p>{item.content || "…"}</p>
            </article>
          ))
        )}
        <div ref={messageEndRef} />
      </div>

      <form className="composer" onSubmit={submit}>
        <textarea
          aria-label="채팅 메시지"
          placeholder="메시지를 입력하세요"
          value={message}
          disabled={disabled}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button disabled={disabled || !canStartChat || !message.trim()}>
          {disabled ? "응답 중…" : "전송"}
        </button>
      </form>
    </section>
  );
}
