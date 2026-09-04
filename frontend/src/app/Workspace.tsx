import { lazy, Suspense } from "react";
import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { ArrowLeft } from "lucide-react";
import { navigateTo } from "../router/hash";
import { LEARN_PATH } from "../router/paths";
import {
  GRAMMAR_ACTIVITY,
  LISTENING_ACTIVITY,
  PRONUNCIATION_ACTIVITY,
  SPEAKING_ACTIVITY,
  VOCABULARY_ACTIVITY,
  type LearnActivity,
} from "../router/learnHub";
import { Button } from "../components/ui/button";
import { LearnActivitySwitcher } from "../components/LearnActivitySwitcher";
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
const PersonalDictionary = lazy(() =>
  import("../features/vocabulary/PersonalDictionary").then((m) => ({
    default: m.PersonalDictionary,
  })),
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

/**
 * Barra superior compacta de las sub-páginas de APRENDER: botón de vuelta
 * siempre visible (móvil y escritorio), encima del contenido que hace scroll.
 */
function SubpageHeader({
  label,
  onBack,
  children,
}: {
  label: string;
  onBack: () => void;
  children?: ReactNode;
}) {
  return (
    <div className="relative">
      <div className="flex shrink-0 items-center gap-2 border-b border-border bg-background/90 px-2 py-1.5 backdrop-blur">
        <Button
          variant="ghost"
          size="sm"
          className="min-h-9 gap-1 px-2 text-sm font-medium"
          onClick={onBack}
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          {label}
        </Button>
        {children}
      </div>
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
  const { t } = useI18n();
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
    // Vocabulario es una hoja de APRENDER: barra de vuelta fija + atajo de
    // actividades + diccionario.
    content = (
      <div className="flex min-h-0 flex-1 flex-col">
        <SubpageHeader label={t("learn.back")} onBack={backToHub}>
          <LearnActivitySwitcher active={VOCABULARY_ACTIVITY} />
        </SubpageHeader>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <PersonalDictionary userId={currentUserId} />
        </div>
      </div>
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
    // route === "chat": Conversar (práctica libre) o una lección del curso
    // retomada desde Formación. El workspace oculta el historial mientras la
    // lección está activa y la propia barra de contexto de PracticeView
    // distingue el modo lección del modo libre (WS7).
    content = (
      <PracticeView
        route="chat"
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
  }

  return <Suspense fallback={<RouteFallback />}>{content}</Suspense>;
}
