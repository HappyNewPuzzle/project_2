import { useCallback, useMemo, useState } from "react";
import { AuthPanel } from "./components/AuthPanel";
import { CharacterEditor } from "./components/CharacterEditor";
import { CharacterList } from "./components/CharacterList";
import { CharacterPanel } from "./components/CharacterPanel";
import { ChatPanel } from "./components/ChatPanel";
import { ConversationList } from "./components/ConversationList";
import { MemoryPanel } from "./components/MemoryPanel";
import { usePersistentState } from "./hooks/usePersistentState";
import { ApiClient, ApiError } from "./lib/api";
import type {
  Character,
  CharacterCreate,
  CharacterUpdate,
  ChatMessageView,
  Conversation,
  Memory,
  MemoryCreate,
  MemoryUpdate,
} from "./types/api";

// unknown인 JSON이 객체인지 먼저 검사해 잘못된 SSE payload 접근을 막습니다.
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.";
}

export default function App() {
  const [apiBaseUrl, setApiBaseUrl] = usePersistentState(
    "apiBaseUrl",
    "http://127.0.0.1:8000",
  );
  const [token, setToken] = usePersistentState("token", "");
  const [characterId, setCharacterId] = usePersistentState("characterId", "");
  const [conversationId, setConversationId] = usePersistentState(
    "conversationId",
    "",
  );
  const [characters, setCharacters] = useState<Character[]>([]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<ChatMessageView[]>([]);
  const [status, setStatus] = useState(
    token ? "저장된 로그인 토큰이 있습니다." : "먼저 회원가입 또는 로그인하세요.",
  );
  const [busy, setBusy] = useState(false);

  // URL이나 토큰이 바뀔 때만 API client를 다시 만듭니다.
  const api = useMemo(
    () => new ApiClient(apiBaseUrl, token),
    [apiBaseUrl, token],
  );
  const selectedCharacter = useMemo(
    () => characters.find((character) => character.id === characterId),
    [characterId, characters],
  );

  // 모든 버튼 작업의 로딩 상태와 오류 표시를 한 곳에서 처리합니다.
  async function runAction(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
    } catch (error) {
      setStatus(`오류: ${errorMessage(error)}`);
    } finally {
      setBusy(false);
    }
  }

  const loadConversations = useCallback(async () => {
    const loaded = await api.listConversations();
    setConversations(loaded);
    setStatus(`대화 ${loaded.length}개를 불러왔습니다.`);
  }, [api]);

  const loadCharacters = useCallback(async () => {
    const loaded = await api.listCharacters();
    setCharacters(loaded);
    setStatus(`캐릭터 ${loaded.length}개를 불러왔습니다.`);
  }, [api]);

  const loadMemories = useCallback(async () => {
    const loaded = await api.listMemories();
    setMemories(loaded);
    setStatus(`장기 기억 ${loaded.length}개를 불러왔습니다.`);
  }, [api]);

  async function register(email: string, password: string) {
    await runAction(async () => {
      await api.register(email, password);
      setStatus("회원가입을 완료했습니다. 이제 로그인하세요.");
    });
  }

  async function login(email: string, password: string) {
    await runAction(async () => {
      const auth = await api.login(email, password);
      setToken(auth.access_token);

      // state 반영을 기다리지 않고 새 토큰을 가진 client로 초기 목록을 동시에 읽습니다.
      const authenticatedApi = new ApiClient(apiBaseUrl, auth.access_token);
      const [loadedCharacters, loadedConversations, loadedMemories] =
        await Promise.all([
          authenticatedApi.listCharacters(),
          authenticatedApi.listConversations(),
          authenticatedApi.listMemories(),
        ]);
      setCharacters(loadedCharacters);
      setConversations(loadedConversations);
      setMemories(loadedMemories);
      setStatus(
        `로그인했습니다. 캐릭터 ${loadedCharacters.length}개, 대화 ${loadedConversations.length}개, 기억 ${loadedMemories.length}개를 불러왔습니다.`,
      );
    });
  }

  async function createCharacter(payload: CharacterCreate) {
    await runAction(async () => {
      const character = await api.createCharacter(payload);
      setCharacterId(character.id);
      setConversationId("");
      setMessages([]);
      // 생성 결과를 목록 앞에 넣어 별도 새로고침 없이 바로 선택 상태를 보여줍니다.
      setCharacters((current) => [
        character,
        ...current.filter((item) => item.id !== character.id),
      ]);
      setStatus(`캐릭터 생성 완료: ${character.name}`);
    });
  }

  function selectCharacter(character: Character) {
    // 대화방은 생성 시 캐릭터가 고정되므로 선택 변경은 반드시 새 대화로 전환합니다.
    setCharacterId(character.id);
    setConversationId("");
    setMessages([]);
    setStatus(`“${character.name}” 캐릭터를 선택했습니다.`);
  }

  async function updateCharacter(
    targetCharacterId: string,
    payload: CharacterUpdate,
  ) {
    await runAction(async () => {
      const updated = await api.updateCharacter(targetCharacterId, payload);
      setCharacters((current) =>
        current.map((character) =>
          character.id === updated.id ? updated : character,
        ),
      );
      setStatus(`“${updated.name}” 캐릭터를 수정했습니다.`);
    });
  }

  async function deleteCharacter(targetCharacterId: string) {
    await runAction(async () => {
      try {
        await api.deleteCharacter(targetCharacterId);
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          throw new Error(
            "기존 대화에서 사용 중인 캐릭터는 삭제할 수 없습니다. 연결된 대화를 먼저 삭제하세요.",
          );
        }
        throw error;
      }
      setCharacters((current) =>
        current.filter((character) => character.id !== targetCharacterId),
      );
      setCharacterId("");
      setConversationId("");
      setMessages([]);
      setStatus("캐릭터를 삭제했습니다.");
    });
  }

  async function createMemory(payload: MemoryCreate) {
    let createdSuccessfully = false;
    await runAction(async () => {
      const created = await api.createMemory(payload);
      setMemories((current) => [
        created,
        ...current.filter((memory) => memory.id !== created.id),
      ]);
      setStatus("새 장기 기억을 저장했습니다.");
      createdSuccessfully = true;
    });
    return createdSuccessfully;
  }

  async function updateMemory(memoryId: string, payload: MemoryUpdate) {
    await runAction(async () => {
      const updated = await api.updateMemory(memoryId, payload);
      setMemories((current) =>
        current.map((memory) => (memory.id === updated.id ? updated : memory)),
      );
      setStatus("장기 기억을 수정했습니다.");
    });
  }

  async function deleteMemory(memoryId: string) {
    let deletedSuccessfully = false;
    await runAction(async () => {
      await api.deleteMemory(memoryId);
      setMemories((current) =>
        current.filter((memory) => memory.id !== memoryId),
      );
      setStatus("장기 기억을 삭제했습니다.");
      deletedSuccessfully = true;
    });
    return deletedSuccessfully;
  }

  async function openConversation(conversation: Conversation) {
    await runAction(async () => {
      const savedMessages = await api.listMessages(conversation.id);
      setConversationId(conversation.id);
      setCharacterId(conversation.character_id);
      setMessages(
        savedMessages.map((item) => ({
          id: item.id,
          role: item.role,
          content: item.content,
        })),
      );
      setStatus(`대화 “${conversation.title}”을 열었습니다.`);
    });
  }

  async function deleteConversation() {
    if (!conversationId) {
      setStatus("삭제할 현재 대화가 없습니다.");
      return;
    }
    await runAction(async () => {
      await api.deleteConversation(conversationId);
      setConversationId("");
      setMessages([]);
      const loaded = await api.listConversations();
      setConversations(loaded);
      setStatus("현재 대화를 삭제했습니다.");
    });
  }

  function resetConversation() {
    setConversationId("");
    setMessages([]);
    setStatus("새 대화로 전환했습니다.");
  }

  async function sendMessage(message: string) {
    await runAction(async () => {
      const userMessage: ChatMessageView = {
        id: crypto.randomUUID(),
        role: "user",
        content: message,
      };
      const assistantId = crypto.randomUUID();
      setMessages((current) => [
        ...current,
        userMessage,
        { id: assistantId, role: "assistant", content: "" },
      ]);
      setStatus("AI 응답을 받고 있습니다…");

      await api.streamChat(
        {
          message,
          character_id: conversationId ? undefined : characterId || undefined,
          conversation_id: conversationId || undefined,
        },
        (event) => {
          if (event.event === "conversation" && isRecord(event.data)) {
            const nextConversationId = event.data.conversation_id;
            const nextCharacterId = event.data.character_id;
            if (
              typeof nextConversationId === "string" &&
              typeof nextCharacterId === "string"
            ) {
              setConversationId(nextConversationId);
              setCharacterId(nextCharacterId);
            }
          }

          if (
            event.event === "token" &&
            isRecord(event.data) &&
            typeof event.data.delta === "string"
          ) {
            // callback 안에서도 좁혀진 string 타입을 유지하도록 지역 변수에 보관합니다.
            const delta = event.data.delta;
            setMessages((current) =>
              current.map((item) =>
                item.id === assistantId
                  ? { ...item, content: item.content + delta }
                  : item,
              ),
            );
          }

          if (event.event === "error") {
            const message =
              isRecord(event.data) && typeof event.data.message === "string"
                ? event.data.message
                : "Streaming error";
            throw new Error(message);
          }
        },
      );

      const loaded = await api.listConversations();
      setConversations(loaded);
      setStatus("응답을 완료했습니다.");
    });
  }

  return (
    <main>
      <header className="hero">
        <div>
          <p className="eyebrow">STEP 28 · LONG-TERM MEMORY</p>
          <h1>AI Character Chat</h1>
          <p>
            인증, 캐릭터, 대화 기록과 SSE 스트리밍을 컴포넌트로 분리한
            학습용 클라이언트입니다.
          </p>
        </div>
        <span className={`connection ${token ? "connected" : ""}`}>
          <i />
          {token ? "로그인됨" : "로그인 필요"}
        </span>
      </header>

      <div className="workspace">
        <aside>
          <AuthPanel
            apiBaseUrl={apiBaseUrl}
            disabled={busy}
            onApiBaseUrlChange={setApiBaseUrl}
            onRegister={register}
            onLogin={login}
          />
          <CharacterPanel
            selectedCharacterId={characterId}
            disabled={busy || !token}
            onCreate={createCharacter}
          />
          <CharacterList
            characters={characters}
            selectedCharacterId={characterId}
            disabled={busy || !token}
            onReload={() => runAction(loadCharacters)}
            onSelect={selectCharacter}
          />
          <CharacterEditor
            character={selectedCharacter}
            disabled={busy || !token}
            onUpdate={updateCharacter}
            onDelete={deleteCharacter}
          />
          <MemoryPanel
            memories={memories}
            characters={characters}
            selectedCharacterId={characterId}
            disabled={busy || !token}
            onReload={() => runAction(loadMemories)}
            onCreate={createMemory}
            onUpdate={updateMemory}
            onDelete={deleteMemory}
          />
          <ConversationList
            conversations={conversations}
            activeConversationId={conversationId}
            disabled={busy || !token}
            onReload={() => runAction(loadConversations)}
            onOpen={openConversation}
            onDelete={deleteConversation}
          />
        </aside>

        <ChatPanel
          messages={messages}
          disabled={busy}
          canStartChat={Boolean(token && (characterId || conversationId))}
          onSend={sendMessage}
          onReset={resetConversation}
        />
      </div>

      <p className={`status ${status.startsWith("오류:") ? "error" : ""}`}>
        {status}
      </p>
    </main>
  );
}
