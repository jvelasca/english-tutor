import { useEffect, useRef, useState } from "react";
import { useChat } from "./hooks/useChat";
import { useHandsFree } from "./hooks/useHandsFree";
import { useAppearance } from "./hooks/useAppearance";
import { ChatMessage } from "./components/ChatMessage";
import { Composer } from "./components/Composer";
import { Academy } from "./components/Academy";
import { AppearancePanel } from "./components/AppearancePanel";
import { HandsFreeToggle } from "./components/HandsFreeToggle";
import { HelpDialog } from "./components/HelpDialog";
import { InsightCard } from "./components/InsightCard";
import { LearningProfile } from "./components/LearningProfile";
import { ListeningPractice } from "./components/ListeningPractice";
import { ModelSelect } from "./components/ModelSelect";
import { PronunciationPractice } from "./components/PronunciationPractice";
import { BucketToggle, ProgressDashboard } from "./components/ProgressDashboard";
import { ResizeHandle } from "./components/ResizeHandle";
import { Sidebar } from "./components/Sidebar";
import { SpeakingAssessment } from "./components/SpeakingAssessment";
import { SpeakingDiagnostic } from "./components/SpeakingDiagnostic";
import { SpeakingJourney } from "./components/SpeakingJourney";
import { SpeakingPanel } from "./components/SpeakingPanel";
import { TodayPlan } from "./components/TodayPlan";
import { TutorQualityPanel } from "./components/TutorQualityPanel";
import { UserMenu } from "./components/UserMenu";
import { WritingJourney } from "./components/WritingJourney";
import { WritingPanel } from "./components/WritingPanel";
import { SectionNav } from "./components/SectionNav";
import { StatusBar } from "./components/StatusBar";
import { ReadingPractice } from "./components/ReadingPractice";
import {
  AcademyIcon,
  GearIcon,
  HelpIcon,
  MenuIcon,
  PanelIcon,
  ToolsIcon,
} from "./components/Icons";
import { clampRight, clampSidebar } from "./utils/layout";
import type { Section } from "./utils/sections";
import type { SessionStep } from "./types/api";

const SUGGESTIONS = [
  "Let's have a conversation. Ask me anything!",
  "¿Cómo se dice 'buenos días' en inglés?",
  "Correct my sentence: I have 20 years old.",
];

const SKILL_SECTION: Record<string, Section> = {
  listening: "listening",
  speaking: "speaking",
  reading: "reading",
  writing: "writing",
  grammar: "grammar",
  pronunciation: "pronunciation",
};

const SECTION_KICKER: Partial<Record<Section, string>> = {
  speaking: "Práctica de conversación",
  writing: "Práctica de escritura",
  grammar: "Práctica de gramática",
};

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
    selectMode,
    section,
    selectSection,
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
  const [view, setView] = useState<"chat" | "academy">("chat");
  const [sessionVersion, setSessionVersion] = useState(0);
  const [toolsOpen, setToolsOpen] = useState(false);
  const toolsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!toolsOpen) return;
    function onClick(e: MouseEvent) {
      if (toolsRef.current && !toolsRef.current.contains(e.target as Node)) {
        setToolsOpen(false);
      }
    }
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [toolsOpen]);

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

  const handleSelectSection = (next: Section) => {
    selectSection(next);
    if (next === "grammar") selectMode("grammar");
    else if (next === "speaking" || next === "writing") selectMode("conversation");
    setView("chat");
  };

  const handleStartLesson = (
    objectiveId: string,
    title: string,
    levelId: string,
    skills: string[],
  ) => {
    startLesson(objectiveId, title, levelId, skills);
    selectSection("speaking");
    selectMode("conversation");
    setView("chat");
  };

  const handleSessionStep = (step: SessionStep) => {
    if (step.kind === "listening" || step.skill === "listening") {
      handleSelectSection("listening");
      return;
    }
    if (step.objective_id && step.level_id) {
      handleStartLesson(step.objective_id, step.title, step.level_id, step.skills);
      return;
    }
    const next = step.skill ? SKILL_SECTION[step.skill] : undefined;
    if (next) handleSelectSection(next);
  };

  const isChat = section === "speaking" || section === "writing" || section === "grammar";

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <div className="brand">
            <button
              type="button"
              className="menu-button"
              onClick={() => setSidebarOpen(true)}
              aria-label="Abrir conversaciones"
              aria-expanded={sidebarOpen}
            >
              <MenuIcon size={18} />
            </button>
            <span className="logo">EN</span>
            <div className="brand-text">
              <h1>English Tutor</h1>
              <p>100% local · Ollama</p>
            </div>
          </div>
          <span className="header-sep" aria-hidden="true" />
          <UserMenu
            users={users}
            currentUserId={currentUserId}
            onSelect={selectUser}
            onAdd={addUser}
            onEdit={editUser}
          />
        </div>

        <div className="header-nav">
          <SectionNav
            section={section}
            bands={profile?.estimated_bands}
            onSelect={handleSelectSection}
          />
          <button
            type="button"
            className={`header-academy${view === "academy" ? " active" : ""}`}
            aria-pressed={view === "academy"}
            onClick={() => setView("academy")}
            title="Academy · currículum CEFR"
          >
            <AcademyIcon size={17} />
            <span>Academy</span>
          </button>
        </div>

        <div className="header-controls">
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
          <div className="header-tools-wrap" ref={toolsRef}>
            <button
              type="button"
              className="icon-button"
              onClick={() => setToolsOpen((o) => !o)}
              title="Herramientas"
              aria-label="Herramientas"
              aria-haspopup="menu"
              aria-expanded={toolsOpen}
            >
              <ToolsIcon />
            </button>
            {toolsOpen && (
              <div className="header-tools-menu" role="menu">
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setAppearanceOpen(true);
                    setToolsOpen(false);
                  }}
                >
                  <GearIcon size={16} />
                  Apariencia y tema
                </button>
              </div>
            )}
          </div>
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
          <button
            type="button"
            className="insights-toggle"
            onClick={() => setInsightsOpen(true)}
            aria-label="Abrir panel de análisis"
            aria-expanded={insightsOpen}
          >
            <PanelIcon />
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
          onStartLesson={handleStartLesson}
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
            {isChat && (
              <>
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

                    {messages.length === 0 && (
                      <div className="empty">
                        <span className="empty-badge" aria-hidden="true">
                          EN
                        </span>
                        <span className="empty-kicker">
                          {SECTION_KICKER[section] ?? "Práctica"}
                        </span>
                        <h2>Hola</h2>
                        <p>
                          Soy tu profesor de inglés local. Escríbeme en inglés o
                          en español para empezar a practicar.
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
              </>
            )}

            {section === "listening" && (
              <ListeningPractice userId={currentUserId} onAttempt={onAttempt} />
            )}

            {section === "reading" && (
              <ReadingPractice
                userId={currentUserId}
                onOpenAcademy={() => setView("academy")}
                onStartLesson={handleStartLesson}
              />
            )}

            {section === "pronunciation" && (
              <PronunciationPractice userId={currentUserId} onAttempt={onAttempt} />
            )}
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
              <InsightCard
                title="Tu progreso"
                defaultOpen
                actions={<BucketToggle value={bucket} onChange={setBucket} />}
              >
                <ProgressDashboard history={history} events={events} />
              </InsightCard>
              <InsightCard title="Plan de hoy" defaultOpen>
                <TodayPlan
                  userId={currentUserId}
                  onStep={handleSessionStep}
                  refreshKey={sessionVersion}
                />
              </InsightCard>
              <InsightCard title="Tu perfil">
                <LearningProfile profile={profile} />
              </InsightCard>
              <InsightCard title="Expresión oral">
                <SpeakingDiagnostic userId={currentUserId} />
              </InsightCard>
              <InsightCard title="Speaking">
                <SpeakingPanel userId={currentUserId} />
              </InsightCard>
              <InsightCard title="Speaking Journey">
                <SpeakingJourney userId={currentUserId} />
              </InsightCard>
              <InsightCard title="Writing">
                <WritingPanel userId={currentUserId} />
              </InsightCard>
              <InsightCard title="Writing Journey">
                <WritingJourney userId={currentUserId} />
              </InsightCard>
              <InsightCard title="Speaking Assessment">
                <SpeakingAssessment userId={currentUserId} onAttempt={onAttempt} />
              </InsightCard>
              <InsightCard title="Calidad del tutor">
                <TutorQualityPanel messages={messages} />
              </InsightCard>
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

      <StatusBar />
    </div>
  );
}
