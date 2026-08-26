export type Role = "user" | "assistant";

export type TutorMode = "conversation" | "grammar" | "exercises" | "pronunciation";

export type PronunciationLevel = "good" | "fair" | "needs_practice";

export interface Message {
  id?: string;
  role: Role;
  content: string;
  mode?: TutorMode;
  duration_ms?: number;
  latency_ms?: number;
}

export interface ChatResponse {
  model: string;
  content: string;
}

export interface ModelsResponse {
  models?: string[];
}

export interface User {
  id: string;
  name: string;
  avatar_color?: string;
  avatar_emoji?: string;
  avatar_image?: string;
  created_at: string;
}

export interface Settings {
  [key: string]: string;
}

export interface SettingsResponse {
  settings: Settings;
}

export interface ConversationMeta {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  user_id: string;
}

export interface Conversation extends ConversationMeta {
  messages: Message[];
}

export interface WordSubstitution {
  expected: string;
  heard: string;
}

export interface PronunciationBreakdown {
  correct: string[];
  missing: string[];
  extra: string[];
  substituted: WordSubstitution[];
  total: number;
}

export interface FluencyStats {
  word_count: number;
  duration_seconds: number | null;
  wpm: number | null;
  level: string;
}

export interface PronunciationResponse {
  expected: string;
  heard: string;
  score: number;
  level: PronunciationLevel;
  ok: boolean;
  word_accuracy: number;
  phonetic_score: number;
  breakdown: PronunciationBreakdown;
  fluency: FluencyStats;
}

export interface PronunciationStats {
  attempts: number;
  best: number | null;
  average: number | null;
  last_score: number | null;
  last_level: PronunciationLevel | null;
}

export interface ProgressSummary {
  user_id: string;
  conversations: number;
  messages: number;
  exercises: number;
  corrections: number;
  pronunciation: PronunciationStats;
}

export type EstimatedLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

export interface EstimatedBands {
  vocabulary: string;
  grammar: string;
  pronunciation: string;
  listening: string;
  speaking: string;
  reading: string;
  writing: string;
}

export interface SkillState {
  skill: string;
  band: string;
  score: number;
  confidence: number;
  samples: number;
  stability: number;
  trend: number | null;
  subskills: Record<string, unknown>[];
}

export interface CefrSnapshot {
  id: number;
  level: string;
  numeric: number;
  confidence: number;
  instrument_version: string;
  curriculum_version: string;
  created_at: string;
  skills: SkillState[];
}

export interface GrammarRecurringError {
  rule: string;
  message: string;
  count: number;
  last_example: string;
  last_seen: string;
  first_seen: string;
  confidence: number;
  source: string;
  confirmed: boolean;
  correct_after: number;
  streak: number;
  mastered: boolean;
}

export interface LearningProfile {
  user_id: string;
  current_level: string;
  estimated_level: EstimatedLevel;
  estimated_bands: EstimatedBands;
  estimated_descriptor: string;
  estimated_confidence: number;
  overall_ability: number;
  target_level: string;
  skills: SkillState[];
  readiness: Readiness;
  cefr_history: CefrSnapshot[];
  vocabulary_size: number;
  vocabulary_exposed: number;
  vocabulary_mastered: number;
  top_words: string[];
  recurring_errors: GrammarRecurringError[];
  mastered_errors: GrammarRecurringError[];
  mastered_count: number;
  pronunciation_average: number | null;
  recommendations: string[];
}

export type Bucket = "day" | "week" | "month";

export type LearningEventType =
  | "message"
  | "exercise"
  | "correction"
  | "pronunciation"
  | "conversation";

export interface LearningEvent {
  id: number;
  user_id: string;
  type: LearningEventType;
  detail: string;
  created_at: string;
}

export interface SeriesPoint {
  bucket: string;
  messages: number;
  exercises: number;
  corrections: number;
  pronunciation: number;
}

export interface Streak {
  current_days: number;
  best_days: number;
  last_active_date: string | null;
}

export interface ErrorMastery {
  active: GrammarRecurringError[];
  resolved: GrammarRecurringError[];
}

export interface Milestone {
  id: string;
  label: string;
  achieved: boolean;
}

export interface ProgressHistory {
  user_id: string;
  bucket: Bucket;
  series: SeriesPoint[];
  streak: Streak;
  mastery: ErrorMastery;
  milestones: Milestone[];
}

export interface RealizationFactor {
  declared: number;
  realized: number;
  verified: boolean;
}

export interface ListeningQuestion {
  id: string;
  level: string;
  skill: string;
  difficulty: number;
  difficulty_vector: Record<string, number>;
  script: string;
  question: string;
  options: string[];
  audio_id: string;
  duration: number;
  speaker_id: string;
  accent: string;
  speech_rate: number;
  transcript: string;
  clean_transcript: string;
  noise_level: number;
  repetition_policy: string;
  topic: string;
  audio_ready: boolean;
  // Modelo de realización (V1.14): tipo de audio servido y separación entre la
  // dificultad declarada y la realmente realizada por el audio.
  audio_type: string;
  realized_difficulty: number;
  realization: Record<string, RealizationFactor>;
  // Escalera de variantes de velocidad (P1.9): slow/normal/fast + variante por
  // defecto servida cuando el usuario no elige (siempre "normal").
  variants: ListeningAudioVariant[];
  default_variant: string;
}

export interface ListeningAudioVariant {
  variant: string;
  speech_rate: number;
  label: string;
}

export interface ListeningAnswerResponse {
  question_id: string;
  correct: boolean;
  correct_index: number;
  level: string;
  skill: string;
  difficulty: number;
  realized_difficulty: number;
}

export interface ListeningProductionRequest {
  question_id: string;
  transcript: string;
}

export interface ListeningProductionResult {
  question_id: string;
  task_type: string;
  correct: boolean;
  score: number;
  word_accuracy: number;
  phonetic_score: number;
  phoneme_accuracy: number;
  breakdown: Record<string, unknown>;
  reference: string;
  level: string;
  skill: string;
}

export interface ListeningLevelProgress {
  level: string;
  total: number;
  mastered: number;
  completed: boolean;
}

export interface ListeningStats {
  attempts: number;
  correct: number;
  accuracy: number | null;
  level: string;
  completed: boolean;
  levels: ListeningLevelProgress[];
}

export interface ListeningSubskillProgress {
  skill: string;
  attempts: number;
  correct: number;
  accuracy: number | null;
  first_pass_accuracy: number | null;
  avg_response_ms: number | null;
  avg_replay_count: number;
  automaticity: number | null;
  review_due: boolean;
  // Media (0..100) del score continuo de las tareas de producción (dictado/
  // shadowing), o null si no hay evidencia de producción.
  mean_score: number | null;
  // True si la evidencia de esta sub-destreza proviene de ítems cuyo audio no
  // realiza el factor que la respalda (p. ej. multiple_speakers con una sola voz).
  realization_gap: boolean;
}

export interface ListeningDifficultyProgress {
  difficulty: number;
  attempts: number;
  correct: number;
  accuracy: number | null;
}

export interface ListeningTopicProgress {
  topic: string;
  attempts: number;
  correct: number;
  accuracy: number | null;
}

export interface ListeningTrend {
  recent_accuracy: number | null;
  prior_accuracy: number | null;
  delta: number | null;
  direction: string;
}

export interface ListeningRecurrence {
  questions_seen: number;
  retried: number;
  recovered: number;
  retry_rate: number | null;
  recovery_rate: number | null;
}

export interface ListeningRetentionBucket {
  bucket: string;
  attempts: number;
  correct: number;
  accuracy: number | null;
}

export interface ListeningRetention {
  total_questions: number;
  immediate_accuracy: number | null;
  delayed_accuracy: number | null;
  retention_rate: number | null;
  by_bucket: ListeningRetentionBucket[];
}

export interface ListeningRealizationSummary {
  attempts: number;
  verified: number;
  gap: number;
}

export interface ListeningDiagnostic {
  subskills: ListeningSubskillProgress[];
  weak: string[];
  recommendation: string;
  first_pass_accuracy: number | null;
  automaticity: number | null;
  by_difficulty: ListeningDifficultyProgress[];
  by_topic: ListeningTopicProgress[];
  trend: ListeningTrend;
  recurrence: ListeningRecurrence;
  retention: ListeningRetention;
  bank_version: string;
  realization: ListeningRealizationSummary;
}

// --- Speaking 3.0 (diagnóstico longitudinal por criterio de rúbrica) ---

export interface SpeakingCriterionProgress {
  criterion: string;
  attempts: number;
  mean: number | null;
  min: number | null;
  max: number | null;
  review_due: boolean;
  // Campos longitudinales añadidos en V1.16 (media de la ventana reciente,
  // media histórica, confianza y estabilidad del criterio).
  recent_score?: number | null;
  lifetime_score?: number | null;
  confidence?: number | null;
  stability?: number | null;
}

export interface SpeakingTrend {
  recent_mean: number | null;
  prior_mean: number | null;
  delta: number | null;
  direction: string;
}

export interface SpeakingDiagnostic {
  criteria: SpeakingCriterionProgress[];
  weak: string[];
  recommendation: string;
  attempts: number;
  overall_mean: number | null;
  overall_recent: number | null;
  trend: SpeakingTrend;
  rubric_version: string;
}

// --- Speaking 3.0: nivel continuo y journey (V1.16) ---

export interface SpeakingLevelOut {
  level: string | null;
  numeric: number | null;
  score: number | null;
  confidence: number;
  attempts: number;
}

export interface SpeakingJourneyStep {
  at: string;
  numeric: number;
  level: string;
  confidence: number;
}

export interface SpeakingJourneyOut {
  current_level: string | null;
  current_numeric: number | null;
  current_confidence: number;
  attempts: number;
  steps: SpeakingJourneyStep[];
}

// --- Writing 3.0 (diagnóstico longitudinal por criterio de rúbrica) ---

export interface WritingCriterionProgress {
  criterion: string;
  attempts: number;
  mean: number | null;
  min: number | null;
  max: number | null;
  review_due: boolean;
  // Campos longitudinales añadidos en V1.17 (media de la ventana reciente,
  // media histórica, confianza y estabilidad del criterio).
  recent_score?: number | null;
  lifetime_score?: number | null;
  confidence?: number | null;
  stability?: number | null;
}

export interface WritingTrend {
  recent_mean: number | null;
  prior_mean: number | null;
  delta: number | null;
  direction: string;
}

export interface WritingDiagnostic {
  criteria: WritingCriterionProgress[];
  weak: string[];
  recommendation: string;
  attempts: number;
  overall_mean: number | null;
  overall_recent: number | null;
  trend: WritingTrend;
  rubric_version: string;
}

// --- Writing 3.0: nivel continuo y journey (V1.17) ---

export interface WritingLevelOut {
  level: string | null;
  numeric: number | null;
  score: number | null;
  confidence: number;
  attempts: number;
}

export interface WritingJourneyStep {
  at: string;
  numeric: number;
  level: string;
  confidence: number;
}

export interface WritingJourneyOut {
  current_level: string | null;
  current_numeric: number | null;
  current_confidence: number;
  attempts: number;
  steps: WritingJourneyStep[];
}

// --- Speaking Assessment (V1.17): instrumento de 4 partes + resultado ---

export interface SpeakingAssessmentPartInfo {
  id: string;
  part_index: number;
  title: string;
  task_type: string;
  cefr_target: string;
  duration_target: number;
  prompt: string;
  difficulty: number;
}

export interface SpeakingAssessmentPartScores {
  overall: number;
  criteria: Record<string, number | null>;
  observed: Record<string, boolean>;
}

export interface SpeakingAssessmentStart {
  session_id: number;
  assessment_version: string;
  total_parts: number;
  part: SpeakingAssessmentPartInfo | null;
}

export interface SpeakingAssessmentPart {
  session_id: number;
  part_index: number;
  task_type: string;
  cefr_target: string;
  prompt: string;
  part_scores: SpeakingAssessmentPartScores;
  done: boolean;
  next_part: SpeakingAssessmentPartInfo | null;
}

export interface SpeakingAssessmentResult {
  session_id: number;
  level: string | null;
  numeric: number | null;
  score: number | null;
  confidence: number;
  attempts: number;
  criteria: SpeakingCriterionProgress[];
  weak: string[];
  recommendation: string;
  assessment_version: string;
  rubric_version: string;
}

export interface SpeakingAssessmentState {
  session_id: number;
  status: string;
  assessment_version: string;
  total_parts: number;
  next_part_index: number;
  final_result: SpeakingAssessmentResult | null;
}

// --- Academy (currículum CEFR, mastery, evaluación) ---

export type AcademyObjectiveStatus =
  | "locked"
  | "available"
  | "review"
  | "mastered";

export interface CurriculumActivity {
  id: string;
  type: string;
  instruction: string;
  target: string;
}

export interface ObjectiveCheck {
  id: string;
  skill: string;
  prompt: string;
  options: string[];
}

export interface SkillScore {
  skill: string;
  score: number;
  required: number;
  met: boolean;
}

export interface ObjectiveProgress {
  objective_id: string;
  skills: SkillScore[];
  mastered: boolean;
}

export interface CurriculumObjective {
  id: string;
  can_do: string;
  title: string;
  skills: string[];
  concepts: string[];
  vocabulary: string[];
  thresholds: Record<string, number>;
  activities: CurriculumActivity[];
  checks: ObjectiveCheck[];
  module_id: string;
  module_title: string;
  unit_id: string;
  unit_title: string;
  lesson_id: string;
  lesson_title: string;
  order: number;
  status: AcademyObjectiveStatus;
  attempts: number;
  correct: number;
  incorrect: number;
  progress: ObjectiveProgress;
}

export interface ModuleProgress {
  module_id: string;
  title: string;
  order: number;
  mastered: number;
  total: number;
  progress: number;
  correct: number;
  incorrect: number;
  to_review: number;
}

export interface LevelProgress {
  level: string;
  mastered: number;
  total: number;
  progress: number;
  correct: number;
  incorrect: number;
  to_review: number;
}

export interface LevelDetail {
  level_id: string;
  level: string;
  title: string;
  description: string;
  objectives: CurriculumObjective[];
  modules_progress: ModuleProgress[];
  progress: LevelProgress;
}

export interface LevelSummary {
  level_id: string;
  level: string;
  title: string;
  description: string;
  objective_count: number;
  available: boolean;
  unlocked: boolean;
  enrolled: boolean;
  progress: number;
  correct: number;
  incorrect: number;
  to_review: number;
}

export interface LevelsResponse {
  levels: LevelSummary[];
}

export interface Enrollment {
  level_id: string;
  level: string;
  status: string;
  enrolled_at: string;
  updated_at: string;
}

export interface EnrollmentsResponse {
  enrollments: Enrollment[];
}

export interface MasteryLevel {
  level_id: string;
  skills: Record<string, number>;
}

export interface MasteryResponse {
  mastery: MasteryLevel[];
}

export interface NextObjective {
  objective_id: string | null;
  level_id: string;
  reason: string;
}

export interface PlacementItem {
  id: string;
  skill: string;
  difficulty: number;
  prompt: string;
  options: string[];
}

export interface Placement {
  id: string;
  title: string;
  description: string;
  items: PlacementItem[];
}

export interface PlacementResult {
  level: string;
  confidence: number;
  answered: number;
  correct: number;
}

export interface PlacementStart {
  session_id: number;
  next_item: PlacementItem | null;
  placement_version: string;
}

export interface PlacementAdaptive {
  session_id: number | null;
  next_item: PlacementItem | null;
  theta: number;
  standard_error: number | null;
  answered: number;
  done: boolean;
  result: PlacementResult | null;
}

export interface ExamItem {
  id: string;
  skill: string;
  prompt: string;
  options: string[];
}

export interface Exam {
  id: string;
  title: string;
  min_per_skill: number;
  skills: string[];
  items: ExamItem[];
}

export interface ExamSkillResult {
  correct: number;
  total: number;
  score: number;
  passed: boolean;
}

export interface ExamResult {
  overall: number;
  passed: boolean;
  failed_skills: string[];
  skills: Record<string, ExamSkillResult>;
  remediation: Record<string, string[]>;
}

export interface LevelCompletion {
  id: number;
  level_id: string;
  level: string;
  overall: number;
  awarded_at: string;
}

export interface LevelCompletionsResponse {
  completions: LevelCompletion[];
}

export interface StudyPlanStep {
  level: string;
  weeks: number;
  next_level_id: string | null;
}

export interface StudyPlanResponse {
  steps: StudyPlanStep[];
}

export type AttemptResult = "correct" | "incorrect";

export interface AttemptEntry {
  skill: string;
  result: AttemptResult;
}

export interface AttemptResponse {
  recorded: number;
}

export interface LessonCompleted {
  level_id: string;
  objective_id: string;
  recorded: boolean;
}

export interface ObjectiveSkillResult {
  correct: number;
  total: number;
  score: number;
}

export interface ObjectiveAssessmentResult {
  level_id: string;
  objective_id: string;
  overall: number;
  correct: number;
  total: number;
  skills: Record<string, ObjectiveSkillResult>;
  mastery: Record<string, number>;
}

// --- Student Model 2.0 (núcleo adaptativo) ---

export interface SkillProfile {
  skill: string;
  score: number;
  confidence: number;
  evidence_count: number;
  last_evidence: string;
  review_due: boolean;
  stability: number;
  trend: number | null;
  subskills: Record<string, unknown>[];
}

export interface ReadinessSkill {
  skill: string;
  score: number;
  confidence: number;
  evidence_count: number;
  minimum: number;
  ready: boolean;
}

export interface Readiness {
  target_level: string;
  skills: ReadinessSkill[];
  overall: number;
  blocking_skills: string[];
  ready: boolean;
}

export interface Reassessment {
  skill: string;
  level: string;
  reason: string;
}

export interface StudentModel {
  level_id: string;
  current_level: string;
  estimated_level: string;
  estimated_numeric: number;
  confidence: number;
  target_level: string;
  skills: SkillProfile[];
  critical_skills: string[];
  readiness: Readiness;
  reassessment: Reassessment | null;
}

export interface TodayItem {
  kind: string;
  skill: string | null;
  objective_id: string | null;
  title: string;
  reason: string;
  minutes: number;
}

export interface TodayPlan {
  items: TodayItem[];
  total_minutes: number;
}

// --- Session Engine (sesión diaria accionable) ---

export interface SessionStep {
  kind: string;
  step_key: string;
  skill: string | null;
  subskill: string | null;
  objective_id: string | null;
  level_id: string | null;
  skills: string[];
  title: string;
  reason: string;
  minutes: number;
}

export interface Session {
  items: SessionStep[];
  total_minutes: number;
  review_count: number;
  practice_count: number;
}

// --- Objetivo personal de aprendizaje ---

export type LearningGoalType =
  | "general"
  | "travel"
  | "work"
  | "interview"
  | "exam";

export interface LearningGoal {
  goal_type: LearningGoalType;
  minutes_per_day: number;
  days_per_week: number;
  target_level: EstimatedLevel;
}
