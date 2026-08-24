import { useState } from "react";
import { useChat } from "./hooks/useChat";
import { useHandsFree } from "./hooks/useHandsFree";
import { useTheme } from "./hooks/useTheme";
import { ChatMessage } from "./components/ChatMessage";
import { Composer } from "./components/Composer";
import { Academy } from "./components/Academy";
import { HandsFreeToggle } from "./components/HandsFreeToggle";
import { LearningProfile } from "./components/LearningProfile";
import { ListeningPractice } from "./components/ListeningPractice";
import { ModeBar, type AppView } from "./components/ModeBar";
import { PronunciationPractice } from "./components/PronunciationPractice";
import { ProgressDashboard } from "./components/ProgressDashboard";
import { ResizeHandle } from "./components/ResizeHandle";
import { Sidebar } from "./components/Sidebar";
import { ThemeToggle } from "./components/ThemeToggle";
import { TutorQualityPanel } from "./components/TutorQualityPanel";
import { UserMenu } from "./components/UserMenu";
import { clampRight, clampSidebar } from "./utils/layout";

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
    selectModel,
    models,
    favoriteModel,
    toggleFavorite,
    mode,
    selectMode,
    layout,
    setLayout,
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
    editUser,
    history,
    events,
    bucket,
    setBucket,
    refreshHistory,
    refreshEvents,
    profile,
    activeObjective,
    startLesson,
    clearLesson,
    finishLesson,
  } = useChat();

  const { theme, toggleTheme } = useTheme();
  const handsFree = useHandsFree(sendText);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [insightsOpen, setInsightsOpen] = useState(false);
  const [view, setView] = useState<AppView>("chat");

  const closeSidebar = () => setSidebarOpen(false);
  const closeInsights = () => setInsightsOpen(false);

  const handleNew = () => {
    newConversation();
    closeSidebar();
  };

  const handleSelect = (id: string) => {
    loadConversation(id);
    closeSidebar();
  };

  const handleDragSidebar = (dx: number) =>
    setLayout({ ...layout, sidebarWidth: clampSidebar(layout.sidebarWidth + dx) });

  const handleDragRight = (dx: number) =>
    setLayout({ ...layout, rightWidth: clampRight(layout.rightWidth - dx) });

  const onAttempt = () => {
    refreshHistory();
    refreshEvents();
  };

  const handleSelectMode = (next: typeof mode) => {
    selectMode(next);
    setView("chat");
  };

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <button
            type="button"
            className="menu-button"
            onClick={() => setSidebarOpen(true)}
            aria-label="Abrir conversaciones"
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
          <UserMenu
            users={users}
            currentUserId={currentUserId}
            onSelect={selectUser}
            onAdd={addUser}
            onEdit={editUser}
          />
          <ModeBar
            mode={mode}
            view={view}
            bands={profile?.estimated_bands}
            onSelectMode={handleSelectMode}
            onSelectAcademy={() => setView("academy")}
          />
          <HandsFreeToggle
            enabled={handsFree.enabled}
            status={handsFree.status}
            onToggle={handsFree.toggle}
          />
          <select
            className="model-select"
            value={model}
            onChange={(e) => selectModel(e.target.value)}
            title="Modelo de Ollama"
            aria-label="Modelo de Ollama"
          >
            {(models.length ? models : [model]).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <button
            type="button"
            className={`model-favorite${
              favoriteModel === model ? " active" : ""
            }`}
            onClick={toggleFavorite}
            title={
              favoriteModel === model
                ? "Quitar de favoritos"
                : "Marcar como favorito (modelo por defecto)"
            }
            aria-label="Modelo favorito"
            aria-pressed={favoriteModel === model}
          >
            <StarIcon filled={favoriteModel === model} />
          </button>
          <button
            type="button"
            className="insights-toggle"
            onClick={() => setInsightsOpen(true)}
            aria-label="Abrir panel de análisis"
            aria-expanded={insightsOpen}
          >
            <PanelIcon />
          </button>
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
        </div>
      </header>

      {view === "academy" ? (
        <Academy
          userId={currentUserId}
          onStartLesson={(id, title, levelId, skills) => {
            startLesson(id, title, levelId, skills);
            setView("chat");
          }}
          onClose={() => setView("chat")}
        />
      ) : (
      <div className="workspace">
        <aside
          className={`pane pane--sidebar${sidebarOpen ? " open" : ""}`}
          style={{ width: layout.sidebarWidth }}
        >
          <button
            type="button"
            className="pane-close"
            onClick={closeSidebar}
            aria-label="Cerrar conversaciones"
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
        </aside>
        <button
          type="button"
          className={`pane-backdrop${sidebarOpen ? " open" : ""}`}
          onClick={closeSidebar}
          aria-label="Cerrar conversaciones"
          tabIndex={-1}
        />

        <ResizeHandle
          onDrag={handleDragSidebar}
          label="Redimensionar panel de conversaciones"
        />

        <main className="pane pane--main">
          <div className="chat-scroll">
            <div className="chat-inner">
              {activeObjective && (
                <div className="lesson-banner">
                  <span>Lección activa</span>
                  <strong>{activeObjective.title}</strong>
                  <button
                    type="button"
                    onClick={async () => {
                      await finishLesson();
                      setView("academy");
                    }}
                    aria-label="Terminar la lección"
                  >
                    Terminar lección
                  </button>
                  <button
                    type="button"
                    onClick={clearLesson}
                    aria-label="Salir de la lección"
                  >
                    Salir
                  </button>
                </div>
              )}

              {mode === "pronunciation" && (
                <PronunciationPractice
                  userId={currentUserId}
                  onAttempt={onAttempt}
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

              {messages.map((m) => (
                <ChatMessage
                  key={m.id ?? `${m.role}-${m.content}`}
                  message={m}
                />
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
            </div>
          </div>

          <div className="composer-wrap">
            <Composer
              value={input}
              onChange={setInput}
              onSend={send}
              onTranscribed={setInput}
              disabled={loading || !input.trim()}
              busy={loading}
            />
          </div>
        </main>

        <ResizeHandle
          onDrag={handleDragRight}
          label="Redimensionar panel de análisis"
        />

        <aside
          className={`pane pane--insights${insightsOpen ? " open" : ""}`}
          style={{ width: layout.rightWidth }}
        >
          <div className="insights-header">
            <span className="insights-title">Análisis</span>
            <button
              type="button"
              className="pane-close"
              onClick={closeInsights}
              aria-label="Cerrar panel de análisis"
            >
              Cerrar
            </button>
          </div>
          <div className="insights-scroll">
            <ProgressDashboard
              history={history}
              events={events}
              bucket={bucket}
              onBucketChange={setBucket}
            />
            <LearningProfile profile={profile} />
            <TutorQualityPanel messages={messages} />
            <ListeningPractice userId={currentUserId} onAttempt={onAttempt} />
          </div>
        </aside>
        <button
          type="button"
          className={`pane-backdrop pane-backdrop--insights${
            insightsOpen ? " open" : ""
          }`}
          onClick={closeInsights}
          aria-label="Cerrar panel de análisis"
          tabIndex={-1}
        />
      </div>
      )}
    </div>
  );
}

function StarIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

function PanelIcon() {
  return (
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
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <line x1="9" y1="3" x2="9" y2="21" />
    </svg>
  );
}
