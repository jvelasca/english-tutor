import { useState } from "react";
import { useChat } from "./hooks/useChat";
import { useHandsFree } from "./hooks/useHandsFree";
import { useTheme } from "./hooks/useTheme";
import { ChatMessage } from "./components/ChatMessage";
import { Composer } from "./components/Composer";
import { HandsFreeToggle } from "./components/HandsFreeToggle";
import { ModeSelect } from "./components/ModeSelect";
import { PronunciationPractice } from "./components/PronunciationPractice";
import { ProgressSummary } from "./components/ProgressSummary";
import { Sidebar } from "./components/Sidebar";
import { ThemeToggle } from "./components/ThemeToggle";
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
    sendText,
    newConversation,
    loadConversation,
    removeConversation,
    selectUser,
    addUser,
    progress,
    refreshProgress,
  } = useChat();

  const { theme, toggleTheme } = useTheme();
  const handsFree = useHandsFree(sendText);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const closeSidebar = () => setSidebarOpen(false);

  const handleNew = () => {
    newConversation();
    closeSidebar();
  };

  const handleSelect = (id: string) => {
    loadConversation(id);
    closeSidebar();
  };

  return (
    <div className="app">
      <div className={`sidebar-drawer${sidebarOpen ? " open" : ""}`}>
        <button
          type="button"
          className="sidebar-close"
          onClick={closeSidebar}
          aria-label="Cerrar menú"
        >
          Cerrar
        </button>
        <Sidebar
          conversations={conversations}
          activeId={conversationId}
          onNew={handleNew}
          onSelect={handleSelect}
          onDelete={removeConversation}
        />
      </div>

      <button
        type="button"
        className={`sidebar-backdrop${sidebarOpen ? " open" : ""}`}
        onClick={closeSidebar}
        aria-label="Cerrar menú"
        tabIndex={-1}
      />

      <div className="main">
        <header className="header">
          <div className="brand">
            <button
              type="button"
              className="menu-button"
              onClick={() => setSidebarOpen(true)}
              aria-label="Abrir menú"
              aria-expanded={sidebarOpen}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
            <span className="logo">EN</span>
            <div className="brand-text">
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
            <HandsFreeToggle
              enabled={handsFree.enabled}
              status={handsFree.status}
              onToggle={handsFree.toggle}
            />
            <select
              className="model-select"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              title="Modelo de Ollama"
              aria-label="Modelo de Ollama"
            >
              {(models.length ? models : [model]).map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
          </div>
        </header>

        <ProgressSummary progress={progress} />

        <main className="chat">
          {mode === "pronunciation" && (
            <PronunciationPractice
              userId={currentUserId}
              onAttempt={refreshProgress}
            />
          )}

          {messages.length === 0 && (
            <div className="empty">
              <span className="empty-badge" aria-hidden="true">
                EN
              </span>
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
            <div className="row assistant" role="status" aria-live="polite">
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
