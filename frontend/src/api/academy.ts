import { getJson, postJson } from "./client";
import type {
  AttemptEntry,
  AttemptResponse,
  Certificate,
  Enrollment,
  Exam,
  ExamResult,
  LevelDetail,
  LevelsResponse,
  MasteryLevel,
  NextObjective,
  Placement,
  PlacementResult,
  StudyPlanStep,
} from "../types/api";

function userQuery(userId: string): string {
  return `?${new URLSearchParams({ user_id: userId }).toString()}`;
}

export function getLevels(userId: string): Promise<LevelsResponse> {
  return getJson<LevelsResponse>(`/api/academy/levels${userQuery(userId)}`);
}

export function getLevelDetail(
  userId: string,
  levelId: string,
): Promise<LevelDetail> {
  return getJson<LevelDetail>(
    `/api/academy/levels/${levelId}${userQuery(userId)}`,
  );
}

export function enroll(userId: string, levelId: string): Promise<Enrollment> {
  return postJson<Enrollment>(`/api/academy/enroll${userQuery(userId)}`, {
    level_id: levelId,
  });
}

export function getMastery(userId: string): Promise<MasteryLevel[]> {
  return getJson<{ mastery: MasteryLevel[] }>(
    `/api/academy/mastery${userQuery(userId)}`,
  ).then((r) => r.mastery);
}

export function getNextObjective(
  userId: string,
  levelId: string,
): Promise<NextObjective> {
  const params = new URLSearchParams({ user_id: userId, level_id: levelId });
  return getJson<NextObjective>(`/api/academy/next?${params.toString()}`);
}

export function getPlacement(): Promise<Placement> {
  return getJson<Placement>("/api/academy/placement");
}

export function submitPlacement(
  userId: string,
  answers: Record<string, number>,
): Promise<PlacementResult> {
  return postJson<PlacementResult>(
    `/api/academy/placement/submit${userQuery(userId)}`,
    { answers },
  );
}

export function getExam(levelId: string): Promise<Exam> {
  return getJson<Exam>(`/api/academy/exam/${levelId}`);
}

export function submitExam(
  userId: string,
  levelId: string,
  answers: Record<string, number>,
): Promise<ExamResult> {
  return postJson<ExamResult>(
    `/api/academy/exam/${levelId}/submit${userQuery(userId)}`,
    { answers },
  );
}

export function getCertificates(userId: string): Promise<Certificate[]> {
  return getJson<{ certificates: Certificate[] }>(
    `/api/academy/certificates${userQuery(userId)}`,
  ).then((r) => r.certificates);
}

export function getStudyPlan(
  startLevel: string,
  targetLevel: string,
  weeks: number,
): Promise<StudyPlanStep[]> {
  return postJson<{ steps: StudyPlanStep[] }>("/api/academy/study-plan", {
    start_level: startLevel,
    target_level: targetLevel,
    weeks,
  }).then((r) => r.steps);
}

export function recordAttempts(
  userId: string,
  levelId: string,
  objectiveId: string,
  results: AttemptEntry[],
): Promise<AttemptResponse> {
  return postJson<AttemptResponse>(
    `/api/academy/attempts${userQuery(userId)}`,
    { level_id: levelId, objective_id: objectiveId, results },
  );
}
