import { useChat } from "./hooks/useChat";
import { ChatMessage } from "./components/ChatMessage";
import { Composer } from "./components/Composer";
import { ModeSelect } from "./components/ModeSelect";
import { PronunciationPractice } from "./components/PronunciationPractice";
import { Sidebar } from "./components/Sidebar";
import { UserSelect } from "./components/UserSelect";

const SUGGESTIONS = [
  "Let's have a conversation. Ask me anything!",
  "¿Cómo se dice 'buenos días' en inglés?",
  "Correct my sentence: I have 20 years old.",
];

export default function App() {
  const {
    messages,
    input,
    setInput,
    loading,
    model,
    setModel,
    models,
    mode,
    setMode,
    conversations,
    conversationId,
    users,
    currentUserId,
    bottomRef,
    send,
    newConversation,
    loadConversation,
    removeConversation,
    selectUser,
    addUser,
  } = useChat();

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        activeId={conversationId}
        onNew={newConversation}
        onSelect={loadConversation}
        onDelete={removeConversation}
      />

      <div className="main">
        <header className="header">
          <div className="brand">
            <span className="logo">EN</span>
            <div>
              <h1>English Tutor</h1>
              <p>100% local · Ollama</p>
            </div>
          </div>
          <div className="header-controls">
            <UserSelect
              users={users}
              currentUserId={currentUserId}
              onSelect={selectUser}
              onAdd={addUser}
            />
            <ModeSelect value={mode} onChange={setMode} />
            <select
              className="model-select"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              title="Modelo de Ollama"
            >
              {(models.length ? models : [model]).map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        </header>

        <main className="chat">
          {mode === "pronunciation" && <PronunciationPractice />}

          {messages.length === 0 && (
            <div className="empty">
              <h2>Hola</h2>
              <p>
                Soy tu profesor de inglés local. Escríbeme en inglés o en
                español para empezar a practicar.
              </p>
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => setInput(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <ChatMessage key={i} message={m} />
          ))}

          {loading && (
            <div className="row assistant">
              <div className="bubble typing">
                <span />
                <span />
                <span />
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </main>

        <Composer
          value={input}
          onChange={setInput}
          onSend={send}
          onTranscribed={setInput}
          disabled={loading || !input.trim()}
          busy={loading}
        />
      </div>
    </div>
  );
}
