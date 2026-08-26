import { useState } from "react";
import { useChat } from "./hooks/useChat";
import { useHandsFree } from "./hooks/useHandsFree";
import { useAppearance } from "./hooks/useAppearance";
import { ChatMessage } from "./components/ChatMessage";
import { Composer } from "./components/Composer";
import { Academy } from "./components/Academy";
import { AppearancePanel } from "./components/AppearancePanel";
import { HandsFreeToggle } from "./components/HandsFreeToggle";
import { HelpDialog } from "./components/HelpDialog";
import { LearningProfile } from "./components/LearningProfile";
import { ListeningPractice } from "./components/ListeningPractice";
import { ModelSelect } from "./components/ModelSelect";
import { ModeBar, type AppView } from "./components/ModeBar";
import { PronunciationPractice } from "./components/PronunciationPractice";
import { ProgressDashboard } from "./components/ProgressDashboard";
import { ResizeHandle } from "./components/ResizeHandle";
import { Sidebar } from "./components/Sidebar";
import { SpeakingAssessment } from "./components/SpeakingAssessment";
import { SpeakingDiagnostic } from "./components/SpeakingDiagnostic";
import { SpeakingJourney } from "./components/SpeakingJourney";
import { SpeakingPanel } from "./components/SpeakingPanel";
import { TodayPlan } from "./components/TodayPlan";
import { TutorQualityPanel } from "./components/TutorQualityPanel";
import { UserMenu } from "./components/UserMenu";
import { clampRight, clampSidebar } from "./utils/layout";
import type { SessionStep, TutorMode } from "./types/api";

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
    makeFavorite,
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
    completeLesson,
  } = useChat();

  const appearance = useAppearance(currentUserId);
  const handsFree = useHandsFree(sendText);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [insightsOpen, setInsightsOpen] = useState(false);
  const [appearanceOpen, setAppearanceOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [view, setView] = useState<AppView>("chat");
  const [sessionVersion, setSessionVersion] = useState(0);

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
    setSessionVersion((v) => v + 1);
  };

  const handleSelectMode = (next: typeof mode) => {
    selectMode(next);
    setView("chat");
  };

  const SKILL_MODE: Record<string, TutorMode> = {
    grammar: "grammar",
    vocabulary: "conversation",
    speaking: "conversation",
    writing: "conversation",
    reading: "conversation",
    pronunciation: "pronunciation",
    listening: "conversation",
  };

  const handleSessionStep = (step: SessionStep) => {
    setView("chat");
    if (step.kind === "listening") {
      setInsightsOpen(true);
      requestAnimationFrame(() => {
        document
          .getElementById("listening-practice")
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      return;
    }
    if (step.objective_id && step.level_id) {
      startLesson(step.objective_id, step.title, step.level_id, step.skills);
      return;
    }
    const nextMode = step.skill ? SKILL_MODE[step.skill] : undefined;
    if (nextMode) selectMode(nextMode);
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
          <ModelSelect
            model={model}
            models={models}
            favoriteModel={favoriteModel}
            onSelect={selectModel}
            onFavorite={makeFavorite}
          />
          <button
            type="button"
            className="insights-toggle"
            onClick={() => setInsightsOpen(true)}
            aria-label="Abrir panel de análisis"
            aria-expanded={insightsOpen}
          >
            <PanelIcon />
          </button>
          <button
            type="button"
            className="icon-button"
            onClick={() => setAppearanceOpen(true)}
            title="Apariencia y tema"
            aria-label="Abrir ajustes de apariencia"
            aria-haspopup="dialog"
          >
            <GearIcon />
          </button>
          <button
            type="button"
            className="icon-button"
            onClick={() => setHelpOpen(true)}
            title="Ayuda"
            aria-label="Abrir ayuda"
            aria-haspopup="dialog"
          >
            <HelpIcon />
          </button>
        </div>
      </header>

      {appearanceOpen && (
        <AppearancePanel
          appearance={appearance.appearance}
          onUpdate={appearance.update}
          onReset={appearance.reset}
          onClose={() => setAppearanceOpen(false)}
        />
      )}

      {helpOpen && <HelpDialog onClose={() => setHelpOpen(false)} />}

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
                      await completeLesson();
                      setSessionVersion((v) => v + 1);
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
            <TodayPlan
              userId={currentUserId}
              onStep={handleSessionStep}
              refreshKey={sessionVersion}
            />
            <LearningProfile profile={profile} />
            <SpeakingDiagnostic userId={currentUserId} />
            <SpeakingPanel userId={currentUserId} />
            <SpeakingJourney userId={currentUserId} />
            <SpeakingAssessment userId={currentUserId} onAttempt={onAttempt} />
            <TutorQualityPanel messages={messages} />
            <div id="listening-practice">
              <ListeningPractice userId={currentUserId} onAttempt={onAttempt} />
            </div>
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

function GearIcon() {
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
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

function HelpIcon() {
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
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}
