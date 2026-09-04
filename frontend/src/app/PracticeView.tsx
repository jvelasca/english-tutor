import { lazy, Suspense, useState } from "react";
import type { ChatApi } from "../hooks/useChat";
import type { NextBestActivity } from "../types/api";
import { ArrowLeft, Loader2 } from "lucide-react";
import { ChatMessage } from "../components/ChatMessage";
import { Composer } from "../components/Composer";
import { Button } from "../components/ui/button";
import { ListeningPractice } from "../features/listening/ListeningPractice";
import { PronunciationPractice } from "../components/PronunciationPractice";
import { ReadingPractice } from "../features/reading/ReadingPractice";
import { ResizeHandle } from "../components/ResizeHandle";
import { Sidebar } from "../components/Sidebar";
import { MenuIcon, PanelIcon } from "../components/Icons";
import { clampRight, clampSidebar, RIGHT_MAX, RIGHT_MIN, SIDEBAR_MAX, SIDEBAR_MIN } from "../utils/layout";
import type { Section } from "../utils/sections";
import type { SessionStep } from "../types/api";
import { navigateTo } from "../router/hash";
import { FORMATION_PATH, LEARN_PATH } from "../router/paths";
import type { LearnActivity } from "../router/learnHub";
import { LearnActivitySwitcher } from "../components/LearnActivitySwitcher";
import { useI18n } from "../hooks/useI18n";

const AnalysisPanel = lazy(() =>
  import("../components/AnalysisPanel").then((m) => ({ default: m.AnalysisPanel })),
);

const SUGGESTIONS = [
  "Let's have a conversation. Ask me anything!",
  "How do you say 'buenos días' in English?",
  "Correct my sentence: I have 20 years old.",
];

const SECTION_KICKER: Partial<Record<Section, string>> = {
  speaking: "kicker.speaking",
  writing: "kicker.writing",
  grammar: "kicker.grammar",
};

interface PracticeViewProps {
  route: "learn" | "chat";
  chat: ChatApi;
  /** Actividad de APRENDER activa (para el atajo de la franja superior). */
  activeActivity: LearnActivity | null;
  onAttempt: () => void;
  onNextBestStart: (section: Section | null, step: NextBestActivity) => void;
  onStep: (step: SessionStep) => void;
  onStartLesson: (
    objectiveId: string,
    title: string,
    levelId: string,
    skills: string[],
  ) => void;
  onFinishLesson: () => void;
  onOpenCourse: () => void;
}

export function PracticeView({
  route,
  chat,
  activeActivity,
  onAttempt,
  onNextBestStart,
  onStartLesson,
  onFinishLesson,
  onOpenCourse,
}: PracticeViewProps) {
  const { t } = useI18n();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [insightsOpen, setInsightsOpen] = useState(false);

  const {
    messages,
    input,
    setInput,
    loading,
    section,
    layout,
    setLayout,
    conversations,
    conversationId,
    currentUserId,
    bottomRef,
    send,
    newConversation,
    loadConversation,
    removeConversation,
    activeObjective,
    clearLesson,
  } = chat;

  const isChat = section === "speaking" || section === "writing" || section === "grammar";
  // El historial de conversaciones vive solo en Conversar (ruta "chat") y sin
  // una lección de curso activa: mientras la lección está en curso el workspace
  // es el de la lección (sin historial; la envoltura de curso vive en la barra
  // de contexto de esta pantalla, WS7).
  const showSidebar = route === "chat" && !activeObjective;
  // En Aprender, las secciones de práctica pura (no conversación) usan todo el
  // ancho: el panel de análisis nunca se acopla y se abre como drawer con el
  // botón flotante. Las secciones conversacionales conservan su layout.
  const drawerAnalysis = route === "learn" && !isChat;

  // Barra de contexto (WS7): una lección del curso solo está en curso cuando la
  // ruta es "chat" (Conversar) y hay un objetivo activo (las lecciones se
  // lanzan siempre desde Formación). Sin objetivo activo la práctica es libre.
  const inLesson = route === "chat" && activeObjective !== null;
  const contextBackPath = inLesson ? FORMATION_PATH : LEARN_PATH;
  const contextBackLabel = inLesson ? t("nav.formation") : t("learn.back");

  const closeSidebar = () => setSidebarOpen(false);

  const handleNew = () => {
    newConversation();
    closeSidebar();
  };

  const handleSelect = (id: string) => {
    loadConversation(id);
    closeSidebar();
  };

  const handleDragSidebar = (dx: number) => {
    // El asa solo se arrastra en desktop (≥1024px); además del tope absoluto,
    // no dejamos que el panel lateral acapare más de ~35% del viewport.
    const max = Math.max(SIDEBAR_MIN, Math.floor(window.innerWidth * 0.35));
    const next = clampSidebar(layout.sidebarWidth + dx);
    setLayout({ ...layout, sidebarWidth: Math.min(next, max) });
  };

  const handleDragRight = (dx: number) => {
    // Además del tope absoluto (RIGHT_MAX), limitamos el panel de análisis a
    // ~60% del viewport para que la zona central conserve espacio en desktop.
    const max = Math.max(RIGHT_MIN, Math.floor(window.innerWidth * 0.6));
    const next = clampRight(layout.rightWidth - dx);
    setLayout({ ...layout, rightWidth: Math.min(next, max) });
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="relative z-10 flex shrink-0 flex-wrap items-center gap-x-2 gap-y-1.5 border-b border-border bg-background/90 px-2 py-1.5 backdrop-blur md:flex-nowrap">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => navigateTo(contextBackPath)}
          className="min-h-11 shrink-0 gap-1 px-2 text-sm font-medium md:min-h-9"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          <span className="max-w-[45vw] truncate">{contextBackLabel}</span>
        </Button>

        {inLesson && activeObjective ? (
          <>
            <span className="inline-flex shrink-0 items-center rounded-full border border-border bg-secondary px-2 py-0.5 text-[10px] font-bold tracking-wide text-muted-foreground uppercase">
              {activeObjective.levelId}
            </span>
            <span className="hidden shrink-0 text-xs font-semibold tracking-wide text-muted-foreground uppercase sm:inline">
              {t("chat.activeLesson")}
            </span>
            <span
              className="min-w-0 grow basis-36 truncate text-sm font-semibold text-foreground md:basis-auto"
              title={activeObjective.title}
            >
              {activeObjective.title}
            </span>
            <span className="ml-auto flex shrink-0 items-center gap-1.5">
              <Button
                type="button"
                size="sm"
                onClick={onFinishLesson}
                className="min-h-11 md:min-h-9"
              >
                {t("chat.finishLesson")}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={clearLesson}
                className="min-h-11 text-muted-foreground md:min-h-9"
              >
                {t("chat.exit")}
              </Button>
            </span>
          </>
        ) : (
          // Práctica libre: atajo directo entre las actividades de APRENDER
          // (la activa queda resaltada y hace de título de la barra).
          <LearnActivitySwitcher active={activeActivity} />
        )}
      </div>

      <div className={`workspace${drawerAnalysis ? " workspace--learn" : ""}`}>
      {showSidebar && (
        <>
          <aside
            className={`pane pane--sidebar${sidebarOpen ? " open" : ""}`}
            style={{ width: layout.sidebarWidth }}
          >
            <button
              type="button"
              className="pane-close"
              onClick={closeSidebar}
              aria-label={t("chat.closeConversations")}
            >
              {t("chat.close")}
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
            aria-label={t("chat.closeConversations")}
            tabIndex={-1}
          />
          <ResizeHandle
            onDrag={handleDragSidebar}
            label={t("chat.resizeConversations")}
            value={layout.sidebarWidth}
            min={SIDEBAR_MIN}
            max={SIDEBAR_MAX}
          />
        </>
      )}

      <main className="pane pane--main">
        {showSidebar && !sidebarOpen && (
          <button
            type="button"
            className="pane__menu-button"
            onClick={() => setSidebarOpen(true)}
            aria-label={t("chat.openConversations")}
            aria-expanded={sidebarOpen}
          >
            <MenuIcon size={18} />
          </button>
        )}

        {isChat && (
          <>
            <div className="chat-scroll">
              <div className="chat-inner">
                {messages.length === 0 && (
                  <div className="empty">
                    <span className="empty-badge" aria-hidden="true">
                      EN
                    </span>
                    <span className="empty-kicker">
                      {t(SECTION_KICKER[section] ?? "kicker.default")}
                    </span>
                    <h2>{t("chat.hello")}</h2>
                    <p>{t("chat.intro")}</p>
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
          <ListeningPractice
            userId={currentUserId}
            onAttempt={onAttempt}
            onNext={onNextBestStart}
          />
        )}

        {section === "reading" && (
          <ReadingPractice
            userId={currentUserId}
            onOpenCourse={onOpenCourse}
            onStartLesson={onStartLesson}
          />
        )}

        {section === "pronunciation" && (
          <PronunciationPractice
            userId={currentUserId}
            onAttempt={onAttempt}
            onNext={onNextBestStart}
          />
        )}
      </main>

      {!drawerAnalysis && (
        <ResizeHandle
          onDrag={handleDragRight}
          label={t("chat.resizeInsights")}
          value={layout.rightWidth}
          min={RIGHT_MIN}
          max={RIGHT_MAX}
        />
      )}

      <aside
        className={`pane pane--insights${insightsOpen ? " open" : ""}`}
        style={{ width: layout.rightWidth }}
      >
        <div className="insights-header">
          <span className="insights-title">{t("panels.analysis")}</span>
          <button
            type="button"
            className="pane-close"
            onClick={() => setInsightsOpen(false)}
            aria-label={t("panels.closeAnalysis")}
          >
            {t("chat.close")}
          </button>
        </div>
        <Suspense
          fallback={
            <div
              role="status"
              aria-busy="true"
              className="flex flex-col items-center justify-center gap-3 py-10 text-muted-foreground"
            >
              <Loader2 className="size-5 animate-spin" aria-hidden="true" />
              <span className="text-sm">{t("common.loading")}</span>
            </div>
          }
        >
          <AnalysisPanel messages={messages} />
        </Suspense>
      </aside>

      {!insightsOpen && (
        <button
          type="button"
          className="insights-toggle"
          onClick={() => setInsightsOpen(true)}
          aria-label={t("panels.openAnalysis")}
          aria-expanded={insightsOpen}
        >
          <PanelIcon />
        </button>
      )}

      <button
        type="button"
        className={`pane-backdrop pane-backdrop--insights${
          insightsOpen ? " open" : ""
        }`}
        onClick={() => setInsightsOpen(false)}
        aria-label={t("panels.closeAnalysis")}
        tabIndex={-1}
      />
      </div>
    </div>
  );
}
