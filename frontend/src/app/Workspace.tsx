import type { ChatApi } from "../hooks/useChat";
import type { NextBestActivity, SessionStep } from "../types/api";
import type { Section } from "../utils/sections";
import type { Route } from "./routes";
import { HomeScreen } from "../features/home/HomeScreen";
import { CourseScreen } from "../features/course/CourseScreen";
import { ProgressScreen } from "../features/progress/ProgressScreen";
import { PracticeView } from "./PracticeView";

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
  refreshKey: number;
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
  refreshKey,
}: WorkspaceProps) {
  const { currentUserId, profile, history, users } = chat;
  const userName = users.find((u) => u.id === currentUserId)?.name;

  if (route === "home") {
    return (
      <HomeScreen
        userId={currentUserId}
        profile={profile}
        history={history}
        userName={userName}
        onStart={onNextBestStart}
        refreshKey={refreshKey}
      />
    );
  }

  if (route === "course") {
    return (
      <CourseScreen
        userId={currentUserId}
        profile={profile}
        onStartLesson={onStartLesson}
      />
    );
  }

  if (route === "progress") {
    return <ProgressScreen userId={currentUserId} />;
  }

  return (
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
