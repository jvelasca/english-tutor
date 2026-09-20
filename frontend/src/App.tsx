import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { MotionConfig } from "motion/react";
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
import { chatSkillFromPath, chatSkillPath, isChatSkill } from "./router/chat";
import {
  SPEAKING_ACTIVITY,
  learnActivityFromPath,
  legacySpeakingRedirect,
  type LearnActivity,
} from "./router/learnHub";
import { SettingsDialog } from "./components/SettingsDialog";
import { ProfileGate } from "./components/ProfileGate";
import { DegradedVoiceNotice } from "./components/DegradedVoiceNotice";
import { VoiceDownloadDialog } from "./components/VoiceDownloadDialog";
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
// destrezas sin tarjeta propia en el hub (writing, reading — D4) caen en el
// chat libre (rutas "chat"), al que `handleSelectSection` navega directo por
// su raíz `/chat`; para las que sí tienen tarjeta, la tabla apunta a su
// sub-ruta bajo APRENDER.
const SECTION_ACTIVITY: Partial<Record<Section, LearnActivity>> = {
  listening: "listening",
  speaking: SPEAKING_ACTIVITY,
  grammar: "gramatica",
  // Tras unificar la práctica oral (DISENO-SPEAKING-UNICO F1), la destreza
  // pronunciation abre la página unificada Speaking (el modo Acento se
  // selecciona dentro de la propia página).
  pronunciation: SPEAKING_ACTIVITY,
};

// Secciones sin tarjeta propia en el hub (reading, writing — D4 revisado en
// V3.73.1): su práctica es conversacional con el tutor, pero cada una conserva
// su URL canónica bajo `/chat` (chatSkillPath) para que la sección activa y el
// contexto del tutor se recuperen al recargar o compartir el enlace.

// Estado (sección/modo) que cada sub-ruta de práctica impone como fuente de
// verdad (deep-links: recargar `/aprender/listening` fuerza la sección aunque
// la preferencia persistida sea otra).
const ACTIVITY_SECTION: Partial<Record<LearnActivity, Section>> = {
  listening: "listening",
  speaking: "speaking",
  gramatica: "grammar",
};

const ACTIVITY_MODE: Partial<Record<LearnActivity, TutorMode>> = {
  speaking: "conversation",
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
    usersLoaded,
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
  // Destreza del chat libre activa (`/chat/lectura`, `/chat/escritura`), o null
  // si el chat es el genérico de conversación (V3.73.1, D4).
  const chatSkill = chatSkillFromPath(path);
  // F4: las sub-rutas legadas de las antiguas tarjetas orales redirigen a la
  // página Speaking con su modo activo (decisión a de la decisión abierta nº 2
  // de DISENO-SPEAKING-UNICO): /aprender/pronunciacion -> /aprender/speaking/acento
  // y /aprender/conversar -> /aprender/speaking/dialogo.
  const legacySpeakingTarget = legacySpeakingRedirect(path);
  // useLayoutEffect para que el primer paint ya use la URL canónica (sin que
  // llegue a verse el hub al que degradaban antes).
  useLayoutEffect(() => {
    if (legacySpeakingTarget) navigateTo(legacySpeakingTarget);
  }, [legacySpeakingTarget]);
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
  // El chat libre tiene raíz propia `/chat` (V3.10): siempre conversación.
  // useLayoutEffect para que el primer paint de la sub-ruta ya muestre la
  // práctica correcta (sin parpadeo de otra sección persistida).
  useLayoutEffect(() => {
    if (route === "chat") {
      // La sub-ruta de destreza manda sobre la preferencia persistida: entrar en
      // `/chat/escritura` abre el tutor en modo escritura (y `/chat` a secas,
      // en conversación, como desde V3.10).
      const target = chatSkill ?? "speaking";
      if (chat.section !== target) selectSection(target);
      if (chat.mode !== "conversation") selectMode("conversation");
      return;
    }
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
    route,
    learnActivity,
    chatSkill,
    chat.section,
    chat.mode,
    selectSection,
    selectMode,
  ]);

  const handleSelectSection = useCallback(
    (next: Section) => {
      selectSection(next);
      if (next === "grammar") selectMode("grammar");
      else if (next === "speaking" || next === "writing" || next === "reading") {
        selectMode("conversation");
      }
      // Sin motor propio de rutas (reading/writing — D4 revisado en V3.73.1): la
      // práctica es conversacional, pero cada destreza conserva su URL canónica
      // bajo `/chat` para que el contexto sobreviva a recarga y deep link.
      if (isChatSkill(next)) {
        navigateTo(chatSkillPath(next));
        return;
      }
      const activity = SECTION_ACTIVITY[next];
      if (activity) navigateTo(learnActivityPath(activity));
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

  const handleOpenProgress = useCallback(() => go("progress"), [go]);
  // V3.75.3: el análisis de evolución vive en su propia ruta auxiliar
  // (`/analisis`) y se abre desde la cabecera, junto al usuario.
  const handleOpenAnalysis = useCallback(() => go("analysis"), [go]);

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
      {/* V3.73.1 (GUI-05): las animaciones de `motion/react` no pasan por CSS, así
          que el bloque `@media (prefers-reduced-motion: reduce)` de la hoja no
          las alcanza. `reducedMotion="user"` desactiva en un solo punto las
          animaciones de transform y de layout (incluido el stagger del hub y la
          píldora activa de la navegación) cuando el sistema lo pide. */}
      <MotionConfig reducedMotion="user">
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
              onOpenAnalysis={handleOpenAnalysis}
            />
          }
        >
          <Workspace
            route={route}
            learnActivity={learnActivity}
            chatSkill={chatSkill}
            chat={chat}
            onAttempt={onAttempt}
            onNextBestStart={handleNextBestStart}
            onStep={handleSessionStep}
            onStartLesson={handleStartLesson}
            onFinishLesson={handleFinishLesson}
            onOpenProgress={handleOpenProgress}
            refreshKey={sessionVersion}
          />
        </AppShell>

        {/* V3.72 (RD-04): avisos globales de voz — uno solo para toda la app. El
            aviso de degradación no bloquea nada; el diálogo pide consentimiento
            antes de descargar una voz que falta (~60 MB). */}
        <DegradedVoiceNotice />
        <VoiceDownloadDialog />

        {/* Al arrancar en un navegador nuevo sin ningún perfil definido (sin
            sesión abierta y varios perfiles, o todavía sin perfiles), se pide
            elegir o crear uno antes de usar la app. */}
        {usersLoaded && !currentUserId && (
          <ProfileGate users={users} onSelect={selectUser} onCreate={addUser} />
        )}

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
            userId={currentUserId}
            onClose={() => setSettingsOpen(false)}
          />
        )}
      </MotionConfig>
    </I18nProvider>
  );
}
