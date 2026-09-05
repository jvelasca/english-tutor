import { lazy, Suspense } from "react";
import { Loader2 } from "lucide-react";
import { navigateTo } from "../router/hash";
import { LEARN_PATH } from "../router/paths";
import {
  CONVERSATION_ACTIVITY,
  GRAMMAR_ACTIVITY,
  LISTENING_ACTIVITY,
  PRONUNCIATION_ACTIVITY,
  SPEAKING_ACTIVITY,
  VOCABULARY_ACTIVITY,
  type LearnActivity,
} from "../router/learnHub";
import type { ChatApi } from "../hooks/useChat";
import type { NextBestActivity, SessionStep } from "../types/api";
import type { Section } from "../utils/sections";
import type { Route } from "./routes";
import { useI18n } from "../hooks/useI18n";

const HomeScreen = lazy(() =>
  import("../features/home/HomeScreen").then((m) => ({ default: m.HomeScreen })),
);
const CourseScreen = lazy(() =>
  import("../features/course/CourseScreen").then((m) => ({ default: m.CourseScreen })),
);
const ProgressScreen = lazy(() =>
  import("../features/progress/ProgressScreen").then((m) => ({ default: m.ProgressScreen })),
);
const HelpScreen = lazy(() =>
  import("../features/help/HelpScreen").then((m) => ({ default: m.HelpScreen })),
);
const PracticeView = lazy(() =>
  import("./PracticeView").then((m) => ({ default: m.PracticeView })),
);
const LearnHub = lazy(() =>
  import("../features/learn/LearnHub").then((m) => ({ default: m.LearnHub })),
);
const SpeakingRoutesPractice = lazy(() =>
  import("../features/speaking/SpeakingRoutesPractice").then((m) => ({
    default: m.SpeakingRoutesPractice,
  })),
);
const PronunciationRoutesPractice = lazy(() =>
  import("../features/pronunciation/PronunciationRoutesPractice").then((m) => ({
    default: m.PronunciationRoutesPractice,
  })),
);
const ConversationRoutesPractice = lazy(() =>
  import("../features/conversation/ConversationRoutesPractice").then((m) => ({
    default: m.ConversationRoutesPractice,
  })),
);
const VocabularyRoutesPractice = lazy(() =>
  import("../features/vocabulary/VocabularyRoutesPractice").then((m) => ({
    default: m.VocabularyRoutesPractice,
  })),
);

interface WorkspaceProps {
  route: Route;
  /** Sub-ruta de práctica activa dentro de APRENDER (null = hub u otra raíz). */
  learnActivity: LearnActivity | null;
  chat: ChatApi;
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
  onOpenProgress: () => void;
  refreshKey: number;
}

function RouteFallback() {
  const { t } = useI18n();
  return (
    <div
      role="status"
      aria-busy="true"
      aria-live="polite"
      className="flex flex-1 flex-col items-center justify-center gap-3 text-muted-foreground"
    >
      <Loader2 className="size-6 animate-spin" aria-hidden="true" />
      <span className="text-sm">{t("common.loading")}</span>
    </div>
  );
}

/** Prácticas del hub que se sirven desde el workspace vía PracticeView. */
const WORKSPACE_ACTIVITIES: readonly LearnActivity[] = [
  LISTENING_ACTIVITY,
  GRAMMAR_ACTIVITY,
];

export function Workspace({
  route,
  learnActivity,
  chat,
  onAttempt,
  onNextBestStart,
  onStep,
  onStartLesson,
  onFinishLesson,
  onOpenCourse,
  onOpenProgress,
  refreshKey,
}: WorkspaceProps) {
  const { currentUserId } = chat;
  const userName = chat.users.find((u) => u.id === currentUserId)?.name;

  const backToHub = () => navigateTo(LEARN_PATH);

  let content;
  if (route === "home") {
    content = (
      <HomeScreen
        userId={currentUserId}
        profile={chat.profile}
        history={chat.history}
        userName={userName}
        onStart={onNextBestStart}
        onStep={onStep}
        onOpenProgress={onOpenProgress}
        refreshKey={refreshKey}
      />
    );
  } else if (route === "course") {
    content = (
      <CourseScreen
        userId={currentUserId}
        profile={chat.profile}
        onStartLesson={onStartLesson}
        onOpenProgress={onOpenProgress}
      />
    );
  } else if (route === "progress") {
    content = (
      <ProgressScreen userId={currentUserId} refreshKey={refreshKey} />
    );
  } else if (route === "journey") {
    // Sub-ruta legada #/progreso/trayectoria: la misma pantalla MI PROGRESO
    // abriendo directamente la pestaña Trayectoria (UI_V3.1 §4.4).
    content = (
      <ProgressScreen
        userId={currentUserId}
        refreshKey={refreshKey}
        initialTab="journey"
      />
    );
  } else if (route === "vocabulary") {
    // Vocabulario (V3.11) es una hoja de APRENDER: página única de rutas A1-C2
    // (checks MC del currículo) con el diccionario personal accesible desde la
    // propia página y el acceso a los instrumentos formales del curso.
    content = (
      <VocabularyRoutesPractice
        userId={currentUserId}
        active={VOCABULARY_ACTIVITY}
        onBack={backToHub}
        onAttempt={onAttempt}
        onNext={onNextBestStart}
      />
    );
  } else if (route === "help") {
    content = <HelpScreen />;
  } else if (route === "learn") {
    if (!learnActivity || learnActivity === SPEAKING_ACTIVITY) {
      content =
        learnActivity === SPEAKING_ACTIVITY ? (
          <SpeakingRoutesPractice
            userId={currentUserId}
            active={learnActivity}
            onBack={backToHub}
            onAttempt={onAttempt}
            onNext={onNextBestStart}
          />
        ) : (
          <LearnHub
            userId={currentUserId}
            onStart={onNextBestStart}
            refreshKey={refreshKey}
          />
        );
    } else if (learnActivity === PRONUNCIATION_ACTIVITY) {
      content = (
        <PronunciationRoutesPractice
          userId={currentUserId}
          active={learnActivity}
          onBack={backToHub}
          onAttempt={onAttempt}
          onNext={onNextBestStart}
        />
      );
    } else if (learnActivity === CONVERSATION_ACTIVITY) {
      // Conversar por rutas guiadas (V3.10): mini-diálogos multi-turno + mapa
      // A1-C2. El chat libre con el tutor vive ahora en su raíz `/chat`.
      content = (
        <ConversationRoutesPractice
          userId={currentUserId}
          active={learnActivity}
          onBack={backToHub}
          onAttempt={onAttempt}
          onNext={onNextBestStart}
        />
      );
    } else if (WORKSPACE_ACTIVITIES.includes(learnActivity)) {
      // La barra de contexto (lección del curso vs práctica libre) vive dentro
      // de PracticeView (WS7): las prácticas del hub se sirven aquí directas.
      content = (
        <PracticeView
          route="learn"
          chat={chat}
          activeActivity={learnActivity}
          onAttempt={onAttempt}
          onNextBestStart={onNextBestStart}
          onStep={onStep}
          onStartLesson={onStartLesson}
          onFinishLesson={onFinishLesson}
          onOpenCourse={onOpenCourse}
        />
      );
    } else {
      // Actividad desconocida bajo /aprender: degrada al hub.
      content = (
        <LearnHub
          userId={currentUserId}
          onStart={onNextBestStart}
          refreshKey={refreshKey}
        />
      );
    }
  } else {
    // route === "chat": práctica libre con el tutor (raíz `/chat` desde
    // V3.10) o una lección del curso retomada desde Formación. El workspace
    // oculta el historial mientras la lección está activa y la propia barra de
    // contexto de PracticeView distingue el modo lección del modo libre (WS7).
    // Al llegar por URL el chat libre no trae sub-actividad: se marca Conversar
    // en el atajo de actividades de la franja superior.
    content = (
      <PracticeView
        route="chat"
        chat={chat}
        activeActivity={learnActivity ?? CONVERSATION_ACTIVITY}
        onAttempt={onAttempt}
        onNextBestStart={onNextBestStart}
        onStep={onStep}
        onStartLesson={onStartLesson}
        onFinishLesson={onFinishLesson}
        onOpenCourse={onOpenCourse}
      />
    );
  }

  return <Suspense fallback={<RouteFallback />}>{content}</Suspense>;
}
