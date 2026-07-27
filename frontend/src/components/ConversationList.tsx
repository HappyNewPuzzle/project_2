import type { Conversation } from "../types/api";

interface ConversationListProps {
  conversations: Conversation[];
  activeConversationId: string;
  disabled: boolean;
  onReload: () => Promise<void>;
  onOpen: (conversation: Conversation) => Promise<void>;
  onDelete: () => Promise<void>;
}

// 목록은 서버 데이터의 표시와 사용자 선택 전달만 담당합니다.
export function ConversationList({
  conversations,
  activeConversationId,
  disabled,
  onReload,
  onOpen,
  onDelete,
}: ConversationListProps) {
  return (
    <section className="panel">
      <div className="section-heading">
        <span className="step-number">5</span>
        <div>
          <h2>대화 목록</h2>
          <p>저장된 대화를 다시 열거나 현재 대화를 삭제합니다.</p>
        </div>
      </div>

      <div className="actions">
        <button className="secondary" disabled={disabled} onClick={onReload}>
          목록 새로고침
        </button>
        <button
          className="danger"
          disabled={disabled || !activeConversationId}
          onClick={onDelete}
        >
          현재 대화 삭제
        </button>
      </div>

      <div className="conversation-list" aria-live="polite">
        {conversations.length === 0 ? (
          <p className="empty-state">불러온 대화가 없습니다.</p>
        ) : (
          conversations.map((conversation) => (
            <button
              key={conversation.id}
              className={`conversation-item ${
                conversation.id === activeConversationId ? "active" : ""
              }`}
              disabled={disabled}
              onClick={() => onOpen(conversation)}
            >
              <span className="conversation-title">{conversation.title}</span>
              <span className="conversation-meta">
                {new Date(conversation.updated_at).toLocaleString("ko-KR")}
              </span>
            </button>
          ))
        )}
      </div>
    </section>
  );
}
