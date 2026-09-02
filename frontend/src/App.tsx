import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useChat } from "./hooks/useChat";
import { useHandsFree } from "./hooks/useHandsFree";
import { useAppearance } from "./hooks/useAppearance";
import { I18nProvider, useLanguage } from "./hooks/useI18n";
import { AppShell } from "./app/AppShell";
import { Header } from "./app/Header";
import { Workspace } from "./app/Workspace";
import type { Route } from "./app/routes";
import { navigateTo, useHashPath } from "./router/hash";
import { pathToRoute, routeToPath } from "./router/routeMap";
import { learnActivityPath } from "./router/paths";
import {
  learnActivityFromPath,
  type LearnActivity,
} from "./router/learnHub";
import { SettingsDialog } from "./components/SettingsDialog";
import { completeSessionStep } from "./api/academy";
import type { Section } from "./utils/sections";
import type { NextBestActivity, SessionStep, TutorMode } from "./types/api";

const SKILL_SECTION: Record<string, Section> = {
  listening: "listening",
  speaking: "speaking",
  reading: "reading",
  writing: "writing",
  grammar: "grammar",
  pronunciation: "pronunciation",
};

// Actividad canónica de APRENDER que abre cada sección de destreza. Las
// destrezas sin tarjeta propia en el hub (writing, reading — D4) caen en
// Conversar, la práctica conversacional con el tutor, para no romper los
// flujos que llegan desde INICIO (plan del día / next-best).
const SECTION_ACTIVITY: Record<Section, LearnActivity> = {
  listening: "listening",
  speaking: "conversar",
  reading: "conversar",
  writing: "conversar",
  grammar: "gramatica",
  pronunciation: "pronunciacion",
};

// Estado (sección/modo) que cada sub-ruta de práctica impone como fuente de
// verdad (deep-links: recargar `/aprender/listening` fuerza la sección aunque
// la preferencia persistida sea otra).
const ACTIVITY_SECTION: Partial<Record<LearnActivity, Section>> = {
  listening: "listening",
  speaking: "speaking",
  pronunciacion: "pronunciation",
  conversar: "speaking",
  gramatica: "grammar",
};

const ACTIVITY_MODE: Partial<Record<LearnActivity, TutorMode>> = {
  speaking: "conversation",
  conversar: "conversation",
  gramatica: "grammar",
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

  const path = useHashPath();
  const route = pathToRoute(path);
  // Sub-ruta de práctica activa dentro de APRENDER (null = hub u otra raíz).
  const learnActivity = learnActivityFromPath(path);
  // Navega desde los handlers internos: la URL (hash) es la fuente de verdad
  // de la ruta, así que "ir a una pantalla" es asignar su ruta canónica.
  const go = useCallback((next: Route) => navigateTo(routeToPath(next)), []);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sessionVersion, setSessionVersion] = useState(0);
  const activeStepKeyRef = useRef<string | null>(null);

  const navigate = useCallback(
    (next: Route) => {
      go(next);
      if (next === "chat") {
        selectSection("speaking");
        selectMode("conversation");
      }
    },
    [go, selectSection, selectMode],
  );

  // La URL manda sobre la preferencia persistida: al entrar (por navegación o
  // deep-link) en una sub-ruta de práctica, alinea sección/modo con la
  // actividad. Al volver al hub (actividad null) no toca las preferencias.
  // useLayoutEffect para que el primer paint de la sub-ruta ya muestre la
  // práctica correcta (sin parpadeo de otra sección persistida).
  useLayoutEffect(() => {
    if (!learnActivity) return;
    const section = ACTIVITY_SECTION[learnActivity];
    const mode = ACTIVITY_MODE[learnActivity];
    if (section !== undefined && section !== chat.section) {
      selectSection(section);
    }
    if (mode !== undefined && mode !== chat.mode) {
      selectMode(mode);
    }
  }, [
    learnActivity,
    chat.section,
    chat.mode,
    selectSection,
    selectMode,
  ]);

  const handleSelectSection = useCallback(
    (next: Section) => {
      selectSection(next);
      if (next === "grammar") selectMode("grammar");
      else if (next === "speaking" || next === "writing") {
        selectMode("conversation");
      }
      navigateTo(learnActivityPath(SECTION_ACTIVITY[next]));
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
      // Las lecciones del curso viven en el workspace conversacional estable:
      // la URL de Conversar. PracticeView oculta el historial mientras hay una
      // lección activa (envoltura de curso → WS7).
      go("chat");
    },
    [go, startLesson, selectSection, selectMode],
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
      else go("chat");
    },
    [go, handleSelectSection, handleStartLesson],
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
      go("chat");
    },
    [go, handleSelectSection, handleStartLesson],
  );

  const handleFinishLesson = useCallback(async () => {
    await completeLesson();
    setSessionVersion((v) => v + 1);
    go("course");
  }, [completeLesson, go]);

  const handleOpenCourse = useCallback(() => go("course"), [go]);

  const handleOpenProgress = useCallback(() => go("progress"), [go]);

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
            handsFreeMicError={handsFree.micError}
            onToggleHandsFree={handsFree.toggle}
            onOpenSettings={() => setSettingsOpen(true)}
          />
        }
      >
        <Workspace
          route={route}
          learnActivity={learnActivity}
          chat={chat}
          onAttempt={onAttempt}
          onNextBestStart={handleNextBestStart}
          onStep={handleSessionStep}
          onStartLesson={handleStartLesson}
          onFinishLesson={handleFinishLesson}
          onOpenCourse={handleOpenCourse}
          onOpenProgress={handleOpenProgress}
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
    </I18nProvider>
  );
}
