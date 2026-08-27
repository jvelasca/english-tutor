import { useState } from "react";
import type { ChatApi } from "../hooks/useChat";
import type { NextBestActivity } from "../types/api";
import { AnalysisPanel } from "../components/AnalysisPanel";
import { ChatMessage } from "../components/ChatMessage";
import { Composer } from "../components/Composer";
import { ListeningPractice } from "../features/listening/ListeningPractice";
import { PronunciationPractice } from "../components/PronunciationPractice";
import { ReadingPractice } from "../features/reading/ReadingPractice";
import { ResizeHandle } from "../components/ResizeHandle";
import { Sidebar } from "../components/Sidebar";
import { MenuIcon, PanelIcon } from "../components/Icons";
import { SectionNav } from "../components/SectionNav";
import { clampRight, clampSidebar, RIGHT_MAX, RIGHT_MIN, SIDEBAR_MAX, SIDEBAR_MIN } from "../utils/layout";
import type { Section } from "../utils/sections";
import type { SessionStep } from "../types/api";
import { useI18n } from "../hooks/useI18n";

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
  onAttempt: () => void;
  onSelectSection: (section: Section) => void;
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
  onAttempt,
  onSelectSection,
  onNextBestStart,
  onStep,
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
    history,
    events,
    bucket,
    setBucket,
    profile,
    activeObjective,
    clearLesson,
  } = chat;

  const isChat =
    section === "speaking" || section === "writing" || section === "grammar";
  const showSidebar = route === "chat";

  const closeSidebar = () => setSidebarOpen(false);

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

  return (
    <div className="workspace">
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
        {route === "learn" && (
          <div className="pane__subnav">
            <SectionNav section={section} onSelect={onSelectSection} />
          </div>
        )}

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
                {activeObjective && (
                  <div className="lesson-banner">
                    <span>{t("chat.activeLesson")}</span>
                    <strong>{activeObjective.title}</strong>
                    <button
                      type="button"
                      onClick={onFinishLesson}
                      aria-label={t("chat.finishLesson")}
                    >
                      {t("chat.finishLesson")}
                    </button>
                    <button
                      type="button"
                      onClick={clearLesson}
                      aria-label={t("chat.exit")}
                    >
                      {t("chat.exit")}
                    </button>
                  </div>
                )}

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

      <ResizeHandle
        onDrag={handleDragRight}
        label={t("chat.resizeInsights")}
        value={layout.rightWidth}
        min={RIGHT_MIN}
        max={RIGHT_MAX}
      />

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
        <AnalysisPanel
          messages={messages}
          history={history}
          events={events}
          bucket={bucket}
          onBucketChange={setBucket}
          profile={profile}
          currentUserId={currentUserId}
          onStep={onStep}
          onAttempt={onAttempt}
          onNextBestStart={onNextBestStart}
        />
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
  );
}
