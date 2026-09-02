import { lazy, Suspense } from "react";
import { Loader2 } from "lucide-react";
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
const JourneyScreen = lazy(() =>
  import("../features/journey/JourneyScreen").then((m) => ({ default: m.JourneyScreen })),
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

interface WorkspaceProps {
  route: Route;
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

export function Workspace({
  route,
  chat,
  onAttempt,
  onSelectSection,
  onNextBestStart,
  onStep,
  onStartLesson,
  onFinishLesson,
  onOpenCourse,
  onOpenProgress,
  refreshKey,
}: WorkspaceProps) {
  const { currentUserId, profile, history, users } = chat;
  const userName = users.find((u) => u.id === currentUserId)?.name;

  let content;
  if (route === "home") {
    content = (
      <HomeScreen
        userId={currentUserId}
        profile={profile}
        history={history}
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
        profile={profile}
        onStartLesson={onStartLesson}
      />
    );
  } else if (route === "progress") {
    content = <ProgressScreen userId={currentUserId} />;
  } else if (route === "journey") {
    content = <JourneyScreen userId={currentUserId} />;
  } else if (route === "vocabulary") {
    content = <PersonalDictionary userId={currentUserId} />;
  } else if (route === "help") {
    content = <ConnectHelp />;
  } else {
    content = (
      <PracticeView
        route={route}
        chat={chat}
        onAttempt={onAttempt}
        onSelectSection={onSelectSection}
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
