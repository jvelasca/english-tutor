import { lazy, Suspense } from "react";
import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { ArrowLeft } from "lucide-react";
import { navigateTo } from "../router/hash";
import { FORMATION_PATH, LEARN_PATH } from "../router/paths";
import {
  GRAMMAR_ACTIVITY,
  LISTENING_ACTIVITY,
  PRONUNCIATION_ACTIVITY,
  SPEAKING_ACTIVITY,
  type LearnActivity,
} from "../router/learnHub";
import { Button } from "../components/ui/button";
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
const ConnectHelp = lazy(() =>
  import("../features/help/ConnectHelp").then((m) => ({ default: m.ConnectHelp })),
);
const PracticeView = lazy(() =>
  import("./PracticeView").then((m) => ({ default: m.PracticeView })),
);
const LearnHub = lazy(() =>
  import("../features/learn/LearnHub").then((m) => ({ default: m.LearnHub })),
);
const SpeakingFreePractice = lazy(() =>
  import("../features/speaking/SpeakingFreePractice").then((m) => ({
    default: m.SpeakingFreePractice,
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

/**
 * Envoltura de una práctica del workspace dentro de APRENDER: barra de vuelta
 * fija + contenido que ocupa el resto del alto (la práctica mantiene su
 * layout interno de scroll, el mismo de V3.0).
 */
function PracticeChrome({
  label,
  onBack,
  children,
}: {
  label: string;
  onBack: () => void;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <SubpageHeader label={label} onBack={onBack} />
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </div>
  );
}

/** Prácticas del hub que se sirven desde el workspace (Listening, Pronunciación, Gramática). */
const WORKSPACE_ACTIVITIES: readonly LearnActivity[] = [
  LISTENING_ACTIVITY,
  PRONUNCIATION_ACTIVITY,
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
  const { currentUserId, activeObjective } = chat;
  const userName = chat.users.find((u) => u.id === currentUserId)?.name;

  const backToHub = () => navigateTo(LEARN_PATH);
  const backToFormation = () => navigateTo(FORMATION_PATH);

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
    // Vocabulario es una hoja de APRENDER: barra de vuelta fija + diccionario.
    content = (
      <div className="flex min-h-0 flex-1 flex-col">
        <SubpageHeader label={t("learn.back")} onBack={backToHub} />
        <div className="min-h-0 flex-1 overflow-y-auto">
          <PersonalDictionary userId={currentUserId} />
        </div>
      </div>
    );
  } else if (route === "help") {
    content = <ConnectHelp />;
  } else if (route === "learn") {
    if (!learnActivity || learnActivity === SPEAKING_ACTIVITY) {
      content =
        learnActivity === SPEAKING_ACTIVITY ? (
          <SpeakingFreePractice userId={currentUserId} onBack={backToHub} />
        ) : (
          <LearnHub
            userId={currentUserId}
            onStart={onNextBestStart}
            refreshKey={refreshKey}
          />
        );
    } else if (WORKSPACE_ACTIVITIES.includes(learnActivity)) {
      content = (
        <PracticeChrome label={t("learn.back")} onBack={backToHub}>
          <PracticeView
            route="learn"
            chat={chat}
            onAttempt={onAttempt}
            onNextBestStart={onNextBestStart}
            onStep={onStep}
            onStartLesson={onStartLesson}
            onFinishLesson={onFinishLesson}
            onOpenCourse={onOpenCourse}
          />
        </PracticeChrome>
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
    // retomada desde Formación (el workspace oculta el historial mientras la
    // lección está activa; la envoltura de curso llega en WS7).
    const inLesson = Boolean(activeObjective);
    content = (
      <PracticeChrome
        label={inLesson ? t("nav.formation") : t("learn.back")}
        onBack={inLesson ? backToFormation : backToHub}
      >
        <PracticeView
          route="chat"
          chat={chat}
          onAttempt={onAttempt}
          onNextBestStart={onNextBestStart}
          onStep={onStep}
          onStartLesson={onStartLesson}
          onFinishLesson={onFinishLesson}
          onOpenCourse={onOpenCourse}
        />
      </PracticeChrome>
    );
  }

  return <Suspense fallback={<RouteFallback />}>{content}</Suspense>;
}
