import { useCallback, useEffect, useRef, useState } from "react";
import { useChat } from "./hooks/useChat";
import { useHandsFree } from "./hooks/useHandsFree";
import { useAppearance } from "./hooks/useAppearance";
import { I18nProvider, useLanguage } from "./hooks/useI18n";
import { AppShell } from "./app/AppShell";
import { Header } from "./app/Header";
import { Workspace } from "./app/Workspace";
import type { Route } from "./app/routes";
import { SettingsDialog } from "./components/SettingsDialog";
import { HelpDialog } from "./components/HelpDialog";
import { completeSessionStep } from "./api/academy";
import type { Section } from "./utils/sections";
import type { NextBestActivity, SessionStep } from "./types/api";

const SKILL_SECTION: Record<string, Section> = {
  listening: "listening",
  speaking: "speaking",
  reading: "reading",
  writing: "writing",
  grammar: "grammar",
  pronunciation: "pronunciation",
};

export default function App() {
  const chat = useChat();
  const {
    selectModel,
    models,
    favoriteModel,
    makeFavorite,
    selectMode,
    selectSection,
    users,
    currentUserId,
    selectUser,
    addUser,
    editUser,
    refreshHistory,
    refreshEvents,
    startLesson,
    completeLesson,
  } = chat;

  const appearance = useAppearance(currentUserId);
  const handsFree = useHandsFree(chat.sendText);
  const { lang, setLang } = useLanguage(currentUserId);

  const [route, setRoute] = useState<Route>("home");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [sessionVersion, setSessionVersion] = useState(0);
  const activeStepKeyRef = useRef<string | null>(null);

  const navigate = useCallback(
    (next: Route) => {
      setRoute(next);
      if (next === "chat") {
        selectSection("speaking");
        selectMode("conversation");
      }
    },
    [selectSection, selectMode],
  );

  const handleSelectSection = useCallback(
    (next: Section) => {
      selectSection(next);
      if (next === "grammar") selectMode("grammar");
      else if (next === "speaking" || next === "writing") {
        selectMode("conversation");
      }
      setRoute("learn");
    },
    [selectSection, selectMode],
  );

  const handleStartLesson = useCallback(
    (
      objectiveId: string,
      title: string,
      levelId: string,
      skills: string[],
    ) => {
      startLesson(objectiveId, title, levelId, skills);
      selectSection("speaking");
      selectMode("conversation");
      setRoute("learn");
    },
    [startLesson, selectSection, selectMode],
  );

  const handleSessionStep = useCallback(
    (step: SessionStep) => {
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
      else setRoute("chat");
    },
    [handleSelectSection, handleStartLesson],
  );

  const handleNextBestStart = useCallback(
    (nextSection: Section | null, step: NextBestActivity) => {
      activeStepKeyRef.current = step.step_key;
      if (nextSection) {
        handleSelectSection(nextSection);
        return;
      }
      if (step.objective_id && step.level_id) {
        handleStartLesson(step.objective_id, step.title, step.level_id, []);
        return;
      }
      setRoute("chat");
    },
    [handleSelectSection, handleStartLesson],
  );

  const handleFinishLesson = useCallback(async () => {
    await completeLesson();
    setSessionVersion((v) => v + 1);
    setRoute("course");
  }, [completeLesson]);

  const handleOpenCourse = useCallback(() => setRoute("course"), []);

  const completeActiveStep = useCallback(() => {
    const key = activeStepKeyRef.current;
    if (currentUserId && key) {
      activeStepKeyRef.current = null;
      void completeSessionStep(currentUserId, key)
        .then(() => setSessionVersion((v) => v + 1))
        .catch(() => {});
    }
  }, [currentUserId]);

  const onAttempt = useCallback(() => {
    refreshHistory();
    refreshEvents();
    setSessionVersion((v) => v + 1);
    completeActiveStep();
  }, [refreshHistory, refreshEvents, completeActiveStep]);

  // Completa el paso activo cuando el tutor genera una respuesta nueva (evidencia
  // producida por actividades conversacionales: speaking/writing/grammar).
  const assistantCountRef = useRef(0);
  useEffect(() => {
    const count = chat.messages.filter((m) => m.role === "assistant").length;
    if (count > assistantCountRef.current) {
      completeActiveStep();
    }
    assistantCountRef.current = count;
  }, [chat.messages, completeActiveStep]);

  return (
    <I18nProvider lang={lang} setLang={setLang}>
      <AppShell
        route={route}
        onNavigate={navigate}
        header={
          <Header
            route={route}
            onNavigate={navigate}
            users={users}
            currentUserId={currentUserId}
            onSelectUser={selectUser}
            onAddUser={addUser}
            onEditUser={editUser}
            handsFreeEnabled={handsFree.enabled}
            handsFreeStatus={handsFree.status}
            onToggleHandsFree={handsFree.toggle}
            onOpenSettings={() => setSettingsOpen(true)}
          />
        }
      >
        <Workspace
          route={route}
          chat={chat}
          onAttempt={onAttempt}
          onSelectSection={handleSelectSection}
          onNextBestStart={handleNextBestStart}
          onStep={handleSessionStep}
          onStartLesson={handleStartLesson}
          onFinishLesson={handleFinishLesson}
          onOpenCourse={handleOpenCourse}
          refreshKey={sessionVersion}
        />
      </AppShell>

      {settingsOpen && (
        <SettingsDialog
          appearance={appearance.appearance}
          onUpdateAppearance={appearance.update}
          onResetAppearance={appearance.reset}
          lang={lang}
          onSetLang={setLang}
          model={chat.model}
          models={models}
          favoriteModel={favoriteModel}
          onSelectModel={selectModel}
          onFavoriteModel={makeFavorite}
          onClose={() => setSettingsOpen(false)}
        />
      )}

      {helpOpen && <HelpDialog onClose={() => setHelpOpen(false)} />}
    </I18nProvider>
  );
}
