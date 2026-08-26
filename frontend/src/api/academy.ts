import { getJson, postJson, putJson } from "./client";
import type {
  AttemptEntry,
  AttemptResponse,
  Enrollment,
  Exam,
  ExamResult,
  LearningGoal,
  LessonCompleted,
  LevelCompletion,
  LevelDetail,
  LevelsResponse,
  MasteryLevel,
  NextObjective,
  ObjectiveAssessmentResult,
  Placement,
  PlacementAdaptive,
  PlacementResult,
  PlacementStart,
  Readiness,
  Session,
  SpeakingAssessmentPart,
  SpeakingAssessmentResult,
  SpeakingAssessmentStart,
  SpeakingAssessmentState,
  SpeakingDiagnostic,
  SpeakingJourneyOut,
  SpeakingLevelOut,
  StudentModel,
  StudyPlanStep,
  TodayPlan,
  WritingDiagnostic,
  WritingJourneyOut,
  WritingLevelOut,
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

export function startAdaptivePlacement(userId: string): Promise<PlacementStart> {
  return postJson<PlacementStart>(
    `/api/academy/placement/start${userQuery(userId)}`,
    {},
  );
}

export function nextAdaptivePlacement(
  userId: string,
  answers: Record<string, number>,
  sessionId: number,
): Promise<PlacementAdaptive> {
  return postJson<PlacementAdaptive>(
    `/api/academy/placement/next${userQuery(userId)}`,
    { answers, session_id: sessionId },
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

export function getLevelCompletions(userId: string): Promise<LevelCompletion[]> {
  return getJson<{ completions: LevelCompletion[] }>(
    `/api/academy/level-completions${userQuery(userId)}`,
  ).then((r) => r.completions);
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

export function completeLesson(
  userId: string,
  levelId: string,
  objectiveId: string,
): Promise<LessonCompleted> {
  return postJson<LessonCompleted>(
    `/api/academy/lessons/complete${userQuery(userId)}`,
    { level_id: levelId, objective_id: objectiveId },
  );
}

export function submitObjectiveAssessment(
  userId: string,
  levelId: string,
  objectiveId: string,
  answers: Record<string, number>,
): Promise<ObjectiveAssessmentResult> {
  return postJson<ObjectiveAssessmentResult>(
    `/api/academy/objective/assessment${userQuery(userId)}`,
    { level_id: levelId, objective_id: objectiveId, answers },
  );
}

export function getStudentModel(userId: string): Promise<StudentModel> {
  return getJson<StudentModel>(`/api/academy/student-model${userQuery(userId)}`);
}

export function getSpeakingDiagnostic(
  userId: string,
): Promise<SpeakingDiagnostic> {
  return getJson<SpeakingDiagnostic>(
    `/api/academy/speaking/diagnostic${userQuery(userId)}`,
  );
}

export function getSpeakingLevel(userId: string): Promise<SpeakingLevelOut> {
  return getJson<SpeakingLevelOut>(
    `/api/academy/speaking/level${userQuery(userId)}`,
  );
}

export function getSpeakingJourney(
  userId: string,
): Promise<SpeakingJourneyOut> {
  return getJson<SpeakingJourneyOut>(
    `/api/academy/speaking/journey${userQuery(userId)}`,
  );
}

export function getWritingDiagnostic(
  userId: string,
): Promise<WritingDiagnostic> {
  return getJson<WritingDiagnostic>(
    `/api/academy/writing/diagnostic${userQuery(userId)}`,
  );
}

export function getWritingLevel(userId: string): Promise<WritingLevelOut> {
  return getJson<WritingLevelOut>(
    `/api/academy/writing/level${userQuery(userId)}`,
  );
}

export function getWritingJourney(
  userId: string,
): Promise<WritingJourneyOut> {
  return getJson<WritingJourneyOut>(
    `/api/academy/writing/journey${userQuery(userId)}`,
  );
}

/** Inicia una sesión de Speaking Assessment y devuelve la primera parte. */
export function startSpeakingAssessment(
  userId: string,
): Promise<SpeakingAssessmentStart> {
  return postJson<SpeakingAssessmentStart>(
    `/api/academy/speaking/assessment/start${userQuery(userId)}`,
    {},
  );
}

/**
 * Envía la respuesta hablada de una parte del Speaking Assessment.
 * `durationSeconds` solo se incluye cuando está definida (vía micrófono) y
 * `conversationId` solo cuando la parte fue un role-play en vivo (turn-taking).
 */
export function submitSpeakingAssessmentPart(
  userId: string,
  sessionId: number,
  heard: string,
  durationSeconds?: number | null,
  conversationId?: string | null,
): Promise<SpeakingAssessmentPart> {
  const body: Record<string, unknown> = { session_id: sessionId, heard };
  if (durationSeconds != null) body.duration_seconds = durationSeconds;
  if (conversationId) body.conversation_id = conversationId;
  return postJson<SpeakingAssessmentPart>(
    `/api/academy/speaking/assessment/part${userQuery(userId)}`,
    body,
  );
}

/** Finaliza la sesión y agrega el resultado CEFR continuo del assessment. */
export function finishSpeakingAssessment(
  userId: string,
  sessionId: number,
): Promise<SpeakingAssessmentResult> {
  return postJson<SpeakingAssessmentResult>(
    `/api/academy/speaking/assessment/finish${userQuery(userId)}`,
    { session_id: sessionId },
  );
}

/** Recupera el estado/resultado de una sesión de Speaking Assessment. */
export function getSpeakingAssessment(
  userId: string,
  sessionId: number,
): Promise<SpeakingAssessmentState> {
  return getJson<SpeakingAssessmentState>(
    `/api/academy/speaking/assessment/${sessionId}${userQuery(userId)}`,
  );
}

export function getReadiness(
  userId: string,
  targetLevel = "B1",
): Promise<Readiness> {
  const params = new URLSearchParams({
    user_id: userId,
    target_level: targetLevel,
  });
  return getJson<Readiness>(`/api/academy/readiness?${params.toString()}`);
}

export function getTodayPlan(userId: string): Promise<TodayPlan> {
  return getJson<TodayPlan>(`/api/academy/today${userQuery(userId)}`);
}

export function getSession(userId: string): Promise<Session> {
  return getJson<Session>(`/api/academy/session${userQuery(userId)}`);
}

export function completeSessionStep(
  userId: string,
  stepKey: string,
): Promise<Session> {
  return postJson<Session>(`/api/academy/session/complete${userQuery(userId)}`, {
    step_key: stepKey,
  });
}

export function getGoal(userId: string): Promise<LearningGoal> {
  return getJson<LearningGoal>(`/api/academy/goal${userQuery(userId)}`);
}

export function putGoal(
  userId: string,
  goal: LearningGoal,
): Promise<LearningGoal> {
  return putJson<LearningGoal>(`/api/academy/goal${userQuery(userId)}`, goal);
}
