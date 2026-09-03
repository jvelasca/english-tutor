import { getJson, postJson, putJson } from "./client";
import type {
  AttemptEntry,
  AttemptResponse,
  CefrLadder,
  ConversationEndurance,
  CourseMap,
  Dashboard,
  Enrollment,
  EvidenceGraph,
  EvidenceGraphNode,
  Exam,
  ExamResult,
  LearningGoal,
  LessonCompleted,
  LevelCompletion,
  LevelDetail,
  LevelsResponse,
  NextBestActivity,
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
  SpeakingMissionState,
  AssessmentV2Ladder,
  AssessmentV2State,
  FsrsDue,
  FsrsReview,
  FsrsSummary,
  SpeakingScenarios,
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

export function getCourseMap(userId: string, levelId: string): Promise<CourseMap> {
  return getJson<CourseMap>(
    `/api/academy/course/${levelId}${userQuery(userId)}`,
  );
}

export function enroll(userId: string, levelId: string): Promise<Enrollment> {
  return postJson<Enrollment>(`/api/academy/enroll${userQuery(userId)}`, {
    level_id: levelId,
  });
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

export function getCefrLadder(userId: string): Promise<CefrLadder> {
  return getJson<CefrLadder>(`/api/academy/cefr-ladder${userQuery(userId)}`);
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

export function getSpeakingEndurance(
  userId: string,
): Promise<ConversationEndurance> {
  return getJson<ConversationEndurance>(
    `/api/academy/speaking/endurance${userQuery(userId)}`,
  );
}

/** Catálogo de escenarios comunicativos (Speaking 3.0): contenido estático. */
export function getSpeakingScenarios(userId: string): Promise<SpeakingScenarios> {
  return getJson<SpeakingScenarios>(
    `/api/academy/speaking/scenarios${userQuery(userId)}`,
  );
}

/** Abre una misión de speaking (V2.9) desde un escenario. */
export function startSpeakingMission(
  userId: string,
  scenarioId: string,
): Promise<SpeakingMissionState> {
  return postJson<SpeakingMissionState>(
    `/api/academy/speaking/mission/start${userQuery(userId)}`,
    { scenario_id: scenarioId },
  );
}

/** Primer intento de la misión → evaluation + drills. */
export function submitSpeakingMissionAttempt(
  userId: string,
  sessionId: number,
  heard: string,
  durationSeconds?: number,
): Promise<SpeakingMissionState> {
  const body: Record<string, unknown> = {
    session_id: sessionId,
    heard,
  };
  if (durationSeconds != null) body.duration_seconds = durationSeconds;
  return postJson<SpeakingMissionState>(
    `/api/academy/speaking/mission/attempt${userQuery(userId)}`,
    body,
  );
}

/** Retry tras el drill → improvement. */
export function submitSpeakingMissionRetry(
  userId: string,
  sessionId: number,
  heard: string,
  durationSeconds?: number,
): Promise<SpeakingMissionState> {
  const body: Record<string, unknown> = {
    session_id: sessionId,
    heard,
  };
  if (durationSeconds != null) body.duration_seconds = durationSeconds;
  return postJson<SpeakingMissionState>(
    `/api/academy/speaking/mission/retry${userQuery(userId)}`,
    body,
  );
}

export function getSpeakingMission(
  userId: string,
  sessionId: number,
): Promise<SpeakingMissionState> {
  return getJson<SpeakingMissionState>(
    `/api/academy/speaking/mission/${sessionId}${userQuery(userId)}`,
  );
}

/** Escalera Assessment 2.0 (formative → retention). */
export function getAssessmentV2Ladder(
  userId: string,
  levelId?: string,
): Promise<AssessmentV2Ladder> {
  const params = new URLSearchParams({ user_id: userId });
  if (levelId) params.set("level_id", levelId);
  return getJson<AssessmentV2Ladder>(
    `/api/academy/assessment/v2/ladder?${params.toString()}`,
  );
}

export function startAssessmentV2(
  userId: string,
  kind: string,
  levelId: string,
  opts?: {
    unitId?: string;
    objectiveId?: string;
    sourceSessionId?: number;
  },
): Promise<AssessmentV2State> {
  const body: Record<string, unknown> = {
    kind,
    level_id: levelId,
  };
  if (opts?.unitId) body.unit_id = opts.unitId;
  if (opts?.objectiveId) body.objective_id = opts.objectiveId;
  if (opts?.sourceSessionId != null) {
    body.source_session_id = opts.sourceSessionId;
  }
  return postJson<AssessmentV2State>(
    `/api/academy/assessment/v2/start${userQuery(userId)}`,
    body,
  );
}

export function submitAssessmentV2(
  userId: string,
  sessionId: number,
  answers: Record<string, number>,
): Promise<AssessmentV2State> {
  return postJson<AssessmentV2State>(
    `/api/academy/assessment/v2/submit${userQuery(userId)}`,
    { session_id: sessionId, answers },
  );
}

export function getAssessmentV2(
  userId: string,
  sessionId: number,
): Promise<AssessmentV2State> {
  return getJson<AssessmentV2State>(
    `/api/academy/assessment/v2/${sessionId}${userQuery(userId)}`,
  );
}

/** Cola FSRS due (V2.11). */
export function getFsrsDue(
  userId: string,
  limit = 20,
): Promise<FsrsDue> {
  const params = new URLSearchParams({
    user_id: userId,
    limit: String(limit),
  });
  return getJson<FsrsDue>(`/api/academy/fsrs/due?${params.toString()}`);
}

export function getFsrsSummary(userId: string): Promise<FsrsSummary> {
  return getJson<FsrsSummary>(
    `/api/academy/fsrs/summary${userQuery(userId)}`,
  );
}

export function syncFsrs(userId: string): Promise<FsrsSummary> {
  return postJson<FsrsSummary>(
    `/api/academy/fsrs/sync${userQuery(userId)}`,
    {},
  );
}

export function reviewFsrsCard(
  userId: string,
  targetType: string,
  targetId: string,
  grade: number,
): Promise<FsrsReview> {
  return postJson<FsrsReview>(
    `/api/academy/fsrs/review${userQuery(userId)}`,
    { target_type: targetType, target_id: targetId, grade },
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

/** Tríada Progress / Mastery / Readiness (V2.2). */
export function getDashboard(userId: string): Promise<Dashboard> {
  return getJson<Dashboard>(`/api/academy/dashboard${userQuery(userId)}`);
}

export function getTodayPlan(userId: string): Promise<TodayPlan> {
  return getJson<TodayPlan>(`/api/academy/today${userQuery(userId)}`);
}

export function getSession(userId: string): Promise<Session> {
  return getJson<Session>(`/api/academy/session${userQuery(userId)}`);
}

export function getNextBestActivity(
  userId: string,
): Promise<NextBestActivity | null> {
  return getJson<NextBestActivity | null>(
    `/api/academy/next-best${userQuery(userId)}`,
  );
}

/** Evidence Graph del nivel (V2.12). */
export function getEvidenceGraph(
  userId: string,
  levelId?: string,
): Promise<EvidenceGraph> {
  const params = new URLSearchParams({ user_id: userId });
  if (levelId) params.set("level_id", levelId);
  return getJson<EvidenceGraph>(
    `/api/academy/evidence-graph?${params.toString()}`,
  );
}

export function getEvidenceGraphNode(
  userId: string,
  objectiveId: string,
  levelId?: string,
): Promise<EvidenceGraphNode> {
  const params = new URLSearchParams({ user_id: userId });
  if (levelId) params.set("level_id", levelId);
  return getJson<EvidenceGraphNode>(
    `/api/academy/evidence-graph/objective/${encodeURIComponent(objectiveId)}?${params.toString()}`,
  );
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
