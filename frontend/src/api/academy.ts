import { getJson, getJsonNullable, postJson, putJson } from "./client";
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
  MicroReviewResult,
  MicroReviewSession,
  SpeakingScenarios,
  StudentModel,
  StudyPlanStep,
  UnitReviewPlan,
  WritingDiagnostic,
  WritingJourneyOut,
  WritingLevelOut,
} from "../types/api";

export function getLevels(_userId: string): Promise<LevelsResponse> {
  return getJson<LevelsResponse>(`/api/academy/levels`);
}

export function getLevelDetail(
  _userId: string,
  levelId: string,
): Promise<LevelDetail> {
  return getJson<LevelDetail>(
    `/api/academy/levels/${levelId}`,
  );
}

export function getCourseMap(_userId: string, levelId: string): Promise<CourseMap> {
  return getJson<CourseMap>(
    `/api/academy/course/${levelId}`,
  );
}

export function enroll(_userId: string, levelId: string): Promise<Enrollment> {
  return postJson<Enrollment>(`/api/academy/enroll`, {
    level_id: levelId,
  });
}

export function getNextObjective(
  _userId: string,
  levelId: string,
): Promise<NextObjective> {
  const params = new URLSearchParams({ level_id: levelId });
  return getJson<NextObjective>(`/api/academy/next?${params.toString()}`);
}

export function getPlacement(): Promise<Placement> {
  return getJson<Placement>("/api/academy/placement");
}

export function submitPlacement(
  _userId: string,
  answers: Record<string, number>,
): Promise<PlacementResult> {
  return postJson<PlacementResult>(
    `/api/academy/placement/submit`,
    { answers },
  );
}

export function startAdaptivePlacement(_userId: string): Promise<PlacementStart> {
  return postJson<PlacementStart>(
    `/api/academy/placement/start`,
    {},
  );
}

export function nextAdaptivePlacement(
  _userId: string,
  answers: Record<string, number>,
  sessionId: number,
): Promise<PlacementAdaptive> {
  return postJson<PlacementAdaptive>(
    `/api/academy/placement/next`,
    { answers, session_id: sessionId },
  );
}

export function getExam(levelId: string): Promise<Exam> {
  return getJson<Exam>(`/api/academy/exam/${levelId}`);
}

export function submitExam(
  _userId: string,
  levelId: string,
  answers: Record<string, number>,
): Promise<ExamResult> {
  return postJson<ExamResult>(
    `/api/academy/exam/${levelId}/submit`,
    { answers },
  );
}

export function getLevelCompletions(_userId: string): Promise<LevelCompletion[]> {
  return getJson<{ completions: LevelCompletion[] }>(
    `/api/academy/level-completions`,
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
  _userId: string,
  levelId: string,
  objectiveId: string,
  results: AttemptEntry[],
): Promise<AttemptResponse> {
  return postJson<AttemptResponse>(
    `/api/academy/attempts`,
    { level_id: levelId, objective_id: objectiveId, results },
  );
}

export function completeLesson(
  _userId: string,
  levelId: string,
  objectiveId: string,
): Promise<LessonCompleted> {
  return postJson<LessonCompleted>(
    `/api/academy/lessons/complete`,
    { level_id: levelId, objective_id: objectiveId },
  );
}

export function submitObjectiveAssessment(
  _userId: string,
  levelId: string,
  objectiveId: string,
  answers: Record<string, number>,
): Promise<ObjectiveAssessmentResult> {
  return postJson<ObjectiveAssessmentResult>(
    `/api/academy/objective/assessment`,
    { level_id: levelId, objective_id: objectiveId, answers },
  );
}

export function getStudentModel(_userId: string): Promise<StudentModel> {
  return getJson<StudentModel>(`/api/academy/student-model`);
}

export function getCefrLadder(_userId: string): Promise<CefrLadder> {
  return getJson<CefrLadder>(`/api/academy/cefr-ladder`);
}

export function getSpeakingDiagnostic(
  _userId: string,
): Promise<SpeakingDiagnostic> {
  return getJson<SpeakingDiagnostic>(
    `/api/academy/speaking/diagnostic`,
  );
}

export function getSpeakingLevel(_userId: string): Promise<SpeakingLevelOut> {
  return getJson<SpeakingLevelOut>(
    `/api/academy/speaking/level`,
  );
}

export function getSpeakingJourney(
  _userId: string,
): Promise<SpeakingJourneyOut> {
  return getJson<SpeakingJourneyOut>(
    `/api/academy/speaking/journey`,
  );
}

export function getSpeakingEndurance(
  _userId: string,
): Promise<ConversationEndurance> {
  return getJson<ConversationEndurance>(
    `/api/academy/speaking/endurance`,
  );
}

/** Catálogo de escenarios comunicativos (Speaking 3.0): contenido estático. */
export function getSpeakingScenarios(_userId: string): Promise<SpeakingScenarios> {
  return getJson<SpeakingScenarios>(
    `/api/academy/speaking/scenarios`,
  );
}

/** Abre una misión de speaking (V2.9) desde un escenario. */
export function startSpeakingMission(
  _userId: string,
  scenarioId: string,
): Promise<SpeakingMissionState> {
  return postJson<SpeakingMissionState>(
    `/api/academy/speaking/mission/start`,
    { scenario_id: scenarioId },
  );
}

/** Primer intento de la misión → evaluation + drills. */
export function submitSpeakingMissionAttempt(
  _userId: string,
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
    `/api/academy/speaking/mission/attempt`,
    body,
  );
}

/** Retry tras el drill → improvement. */
export function submitSpeakingMissionRetry(
  _userId: string,
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
    `/api/academy/speaking/mission/retry`,
    body,
  );
}

export function getSpeakingMission(
  _userId: string,
  sessionId: number,
): Promise<SpeakingMissionState> {
  return getJson<SpeakingMissionState>(
    `/api/academy/speaking/mission/${sessionId}`,
  );
}

/** Escalera Assessment 2.0 (formative → retention). */
export function getAssessmentV2Ladder(
  _userId: string,
  levelId?: string,
): Promise<AssessmentV2Ladder> {
  const params = new URLSearchParams();
  if (levelId) params.set("level_id", levelId);
  const query = params.toString();
  return getJson<AssessmentV2Ladder>(
    `/api/academy/assessment/v2/ladder${query ? `?${query}` : ""}`,
  );
}

export function startAssessmentV2(
  _userId: string,
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
    `/api/academy/assessment/v2/start`,
    body,
  );
}

export function submitAssessmentV2(
  _userId: string,
  sessionId: number,
  answers: Record<string, number>,
): Promise<AssessmentV2State> {
  return postJson<AssessmentV2State>(
    `/api/academy/assessment/v2/submit`,
    { session_id: sessionId, answers },
  );
}

export function getAssessmentV2(
  _userId: string,
  sessionId: number,
): Promise<AssessmentV2State> {
  return getJson<AssessmentV2State>(
    `/api/academy/assessment/v2/${sessionId}`,
  );
}

/** Cola FSRS due (V2.11). */
export function getFsrsDue(
  _userId: string,
  limit = 20,
): Promise<FsrsDue> {
  const params = new URLSearchParams({
    limit: String(limit),
  });
  return getJson<FsrsDue>(`/api/academy/fsrs/due?${params.toString()}`);
}

export function getFsrsSummary(_userId: string): Promise<FsrsSummary> {
  return getJson<FsrsSummary>(
    `/api/academy/fsrs/summary`,
  );
}

export function syncFsrs(_userId: string): Promise<FsrsSummary> {
  return postJson<FsrsSummary>(
    `/api/academy/fsrs/sync`,
    {},
  );
}

export function reviewFsrsCard(
  _userId: string,
  targetType: string,
  targetId: string,
  grade: number,
): Promise<FsrsReview> {
  return postJson<FsrsReview>(
    `/api/academy/fsrs/review`,
    { target_type: targetType, target_id: targetId, grade },
  );
}

// --- Review/SRS por unidad (V3.16) ---

/** Plan de repaso por unidad (V3.16; V3.18/O3: agregado por niveles). */
export function getUnitReviewPlan(_userId: string): Promise<UnitReviewPlan> {
  return getJson<UnitReviewPlan>(
    `/api/academy/review/unit-plan`,
  );
}

/** Sesión de micro-review (checks MC oficiales, sin correct_index). `levelId`
 *  opcional: nivel real donde vive la unidad (anterior al actual, O3). */
export function getUnitMicroReview(
  _userId: string,
  unitId: string,
  windowDays: number,
  levelId?: string,
): Promise<MicroReviewSession> {
  const params = new URLSearchParams({
    window_days: String(windowDays),
  });
  if (levelId) params.set("level_id", levelId);
  return getJson<MicroReviewSession>(
    `/api/academy/review/unit/${encodeURIComponent(unitId)}/micro-review?${params.toString()}`,
  );
}

/** Envía las respuestas del micro-review; el servidor puntúa (premisa 21).
 *  `levelId` opcional: nivel real donde vive la unidad (O3). */
export function submitUnitMicroReview(
  _userId: string,
  unitId: string,
  windowDays: number,
  answers: Record<string, number>,
  levelId?: string,
): Promise<MicroReviewResult> {
  return postJson<MicroReviewResult>(
    `/api/academy/review/unit/${encodeURIComponent(unitId)}/micro-review`,
    {
      window_days: windowDays,
      answers,
      ...(levelId ? { level_id: levelId } : {}),
    },
  );
}

export function getWritingDiagnostic(
  _userId: string,
): Promise<WritingDiagnostic> {
  return getJson<WritingDiagnostic>(
    `/api/academy/writing/diagnostic`,
  );
}

export function getWritingLevel(_userId: string): Promise<WritingLevelOut> {
  return getJson<WritingLevelOut>(
    `/api/academy/writing/level`,
  );
}

export function getWritingJourney(
  _userId: string,
): Promise<WritingJourneyOut> {
  return getJson<WritingJourneyOut>(
    `/api/academy/writing/journey`,
  );
}

/** Inicia una sesión de Speaking Assessment y devuelve la primera parte. */
export function startSpeakingAssessment(
  _userId: string,
): Promise<SpeakingAssessmentStart> {
  return postJson<SpeakingAssessmentStart>(
    `/api/academy/speaking/assessment/start`,
    {},
  );
}

/**
 * Envía la respuesta hablada de una parte del Speaking Assessment.
 * `durationSeconds` solo se incluye cuando está definida (vía micrófono) y
 * `conversationId` solo cuando la parte fue un role-play en vivo (turn-taking).
 */
export function submitSpeakingAssessmentPart(
  _userId: string,
  sessionId: number,
  heard: string,
  durationSeconds?: number | null,
  conversationId?: string | null,
): Promise<SpeakingAssessmentPart> {
  const body: Record<string, unknown> = { session_id: sessionId, heard };
  if (durationSeconds != null) body.duration_seconds = durationSeconds;
  if (conversationId) body.conversation_id = conversationId;
  return postJson<SpeakingAssessmentPart>(
    `/api/academy/speaking/assessment/part`,
    body,
  );
}

/** Finaliza la sesión y agrega el resultado CEFR continuo del assessment. */
export function finishSpeakingAssessment(
  _userId: string,
  sessionId: number,
): Promise<SpeakingAssessmentResult> {
  return postJson<SpeakingAssessmentResult>(
    `/api/academy/speaking/assessment/finish`,
    { session_id: sessionId },
  );
}

/** Recupera el estado/resultado de una sesión de Speaking Assessment. */
export function getSpeakingAssessment(
  _userId: string,
  sessionId: number,
): Promise<SpeakingAssessmentState> {
  return getJson<SpeakingAssessmentState>(
    `/api/academy/speaking/assessment/${sessionId}`,
  );
}

export function getReadiness(
  _userId: string,
  targetLevel = "B1",
): Promise<Readiness> {
  const params = new URLSearchParams({
    target_level: targetLevel,
  });
  return getJson<Readiness>(`/api/academy/readiness?${params.toString()}`);
}

/** Tríada Progress / Mastery / Readiness (V2.2). */
export function getDashboard(_userId: string): Promise<Dashboard> {
  return getJson<Dashboard>(`/api/academy/dashboard`);
}

export function getSession(_userId: string): Promise<Session> {
  return getJson<Session>(`/api/academy/session`);
}

export function getNextBestActivity(
  _userId: string,
): Promise<NextBestActivity | null> {
  return getJson<NextBestActivity | null>(
    `/api/academy/next-best`,
  );
}

/** Evidence Graph del nivel (V2.12). */
export function getEvidenceGraph(
  _userId: string,
  levelId?: string,
): Promise<EvidenceGraph> {
  const params = new URLSearchParams();
  if (levelId) params.set("level_id", levelId);
  const query = params.toString();
  return getJson<EvidenceGraph>(
    `/api/academy/evidence-graph${query ? `?${query}` : ""}`,
  );
}

export function getEvidenceGraphNode(
  _userId: string,
  objectiveId: string,
  levelId?: string,
): Promise<EvidenceGraphNode | null> {
  const params = new URLSearchParams();
  if (levelId) params.set("level_id", levelId);
  const query = params.toString();
  return getJsonNullable<EvidenceGraphNode>(
    `/api/academy/evidence-graph/objective/${encodeURIComponent(objectiveId)}${query ? `?${query}` : ""}`,
  );
}

export function completeSessionStep(
  _userId: string,
  stepKey: string,
): Promise<Session> {
  return postJson<Session>(`/api/academy/session/complete`, {
    step_key: stepKey,
  });
}

export function getGoal(_userId: string): Promise<LearningGoal> {
  return getJson<LearningGoal>(`/api/academy/goal`);
}

export function putGoal(
  _userId: string,
  goal: LearningGoal,
): Promise<LearningGoal> {
  return putJson<LearningGoal>(`/api/academy/goal`, goal);
}
