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

export interface PhonemeSubstitution {
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

export interface PhonemeBreakdown {
  correct: string[];
  missing: string[];
  extra: string[];
  substituted: PhonemeSubstitution[];
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
  phoneme_accuracy_proxy: number;
  prosody_proxy: number;
  pronunciation_source: string;
  breakdown: PronunciationBreakdown;
  phoneme_breakdown: PhonemeBreakdown;
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

export type EstimatedLevel = "Pre-A1" | "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

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

export interface CompetenceGate {
  score_ok: boolean;
  confidence_ok: boolean;
  evidence_ok: boolean;
  review_due: boolean;
  retention_ok: boolean;
}

/** Estado de competencia de una destreza en el nivel actual (Constitución §2.1):
 *  not_started | developing | functional | demonstrated. */
export interface CompetenceState {
  skill: string;
  level: string;
  state: string;
  demonstrated: boolean;
  estimated_band: string;
  score: number;
  confidence: number;
  evidence_count: number;
  gate: CompetenceGate;
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
  competence_states: CompetenceState[];
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

export type LexicalStatus = "mastered" | "known" | "learning" | "weak";

export interface LexicalItem {
  word: string;
  lemma: string;
  cefr: string;
  kind: string;
  source: string;
  status: LexicalStatus;
  recall: number;
  next_review_days: number;
  exposures: number;
  appearances: number;
}

export interface CefrBucket {
  cefr: string;
  count: number;
}

export interface LexiconSummary {
  total: number;
  known: number;
  learning: number;
  weak: number;
  mastered: number;
  by_cefr: CefrBucket[];
}

// P1 (§3.1): Vocabulary Coverage Indicator receptivo/productivo por nivel.
export interface LexiconCoverageLevel {
  cefr: string;
  total: number;
  receptive: number;
  productive: number;
  mastered: number;
  known: number;
  learning: number;
  weak: number;
  receptive_pct: number | null;
  productive_pct: number | null;
}

export interface LexiconCoverage {
  receptive: number;
  productive: number;
  mastered: number;
  by_level: LexiconCoverageLevel[];
}

export interface Lexicon {
  summary: LexiconSummary;
  items: LexicalItem[];
  coverage?: LexiconCoverage | null;
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
  // Contexto comunicativo del ítem (Listening 2.0); vacío en el banco heredado.
  context: string;
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
  phoneme_accuracy_proxy: number;
  breakdown: Record<string, unknown>;
  reference: string;
  level: string;
  skill: string;
}

export interface ListeningRouteGate {
  passed: boolean;
  total: number;
  mastered: number;
  coverage_pct: number;
  coverage_required_pct: number;
  accuracy: number | null;
  accuracy_required: number;
  topics: number;
  topics_required: number;
  subskills: number;
  subskills_required: number;
  checkpoint: number;
  checkpoint_required: number;
  blockers: string[];
}

// Estado pedagógico de una ruta de listening (Constitución §2.1): la puerta de
// ruta decide `functional` y la retención retardada estable (≥7 días, ratio
// ≥90%) decide `demonstrated`. El backend los expone en cada fila de `levels`.
export type ListeningRouteState =
  | "not_started"
  | "developing"
  | "functional"
  | "demonstrated";

export interface ListeningRouteRetention {
  retention_rate: number | null;
  stable: boolean;
  long_delayed_exposures: number;
}

export interface ListeningLevelProgress {
  level: string;
  total: number;
  mastered: number;
  completed: boolean;
  coverage_pct: number | null;
  accuracy: number | null;
  // Puerta de ruta: qué evidencia falta para certificar el nivel (backend 2.x).
  gate?: ListeningRouteGate | null;
  // Competencia por ruta (P2/H7): functional ≠ demonstrated. Solo `demonstrated`
  // habilita leer "A1 Listening — demonstrated".
  state?: ListeningRouteState;
  retention?: ListeningRouteRetention | null;
}

export interface ListeningStats {
  attempts: number;
  correct: number;
  accuracy: number | null;
  level: string;
  completed: boolean;
  levels: ListeningLevelProgress[];
}

export type ListeningItemState = "unseen" | "failed" | "mastered";

export interface ListeningItem {
  question_id: string;
  level: string;
  script: string;
  topic: string;
  skill: string;
  difficulty: number;
  attempts: number;
  state: ListeningItemState;
}

export interface ListeningLevelItems {
  level: string;
  total: number;
  mastered: number;
  failed: number;
  unseen: number;
  completed: boolean;
  items: ListeningItem[];
  // Puerta de ruta del nivel (backend 2.x); `completed` la refleja.
  gate?: ListeningRouteGate | null;
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

export interface ListeningResilienceDimension {
  dimension: string;
  attempts: number;
  correct: number;
  accuracy: number | null;
}

export interface ListeningResilience {
  dimensions: ListeningResilienceDimension[];
  main_weakness: string | null;
  recommendation: string;
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
  // Indicador de resiliencia auditiva (Listening 2.0).
  resilience: ListeningResilience;
}

// --- Biblioteca de audio humano (gestión en-app) ---

export interface AudioLibraryEntry {
  audio_id: string;
  file: string;
  speaker_id: string;
  accent: string;
  speaker_count: number;
  noise_level: number;
  duration: number;
  transcript: string;
  gender: string;
  age_band: string;
  region: string;
  speech_rate: number | null;
  spontaneity: string;
  recording_environment: string;
  overlap: boolean;
  connected_speech: boolean;
  prosody: string;
  task_type: string;
  cefr: string;
  context: string;
}

export interface AudioLibrarySlot {
  question_id: string;
  audio_id: string;
  level: string;
  skill: string;
  topic: string;
  transcript: string;
  clean_transcript: string;
  speech_rate: number;
  noise_level: number;
  speaker_id: string;
  accent: string;
  duration: number;
  state: "recorded" | "missing" | "empty";
  entry: AudioLibraryEntry | null;
}

export interface AudioLibrarySlotsResponse {
  slots: AudioLibrarySlot[];
}

export interface AudioQualityPanel {
  grade: "PASS" | "WARNING" | "REJECT";
  duration: number;
  channels: number;
  framerate: number;
  sample_width: number;
  peak: number | null;
  peak_dbFS: number | null;
  rms: number | null;
  rms_dbFS: number | null;
  clipping_ratio: number | null;
  dc_offset: number | null;
  silence_ratio: number | null;
  analyzed: boolean;
}

export interface AudioUploadResult extends AudioLibraryEntry {
  quality: AudioQualityPanel;
}

export interface AudioLibraryStatusResponse {
  admin_required: boolean;
  version: string;
}

export interface ContentValidationIssue {
  severity: "error" | "warning" | "info";
  category: string;
  id: string;
  message: string;
}

export interface ContentValidationReport {
  total_items: number;
  recorded: number;
  tts: number;
  issues: ContentValidationIssue[];
  by_severity: Record<string, number>;
  ok: boolean;
  // Métrica única de contenido validado (V2.2): banco + escenarios de speaking.
  total_validated_learning_items?: number;
  stats?: {
    total_validated_learning_items: number;
    listening: {
      total: number;
      corpus: number;
      legacy_tts: number;
      with_audio_id: number;
    };
    speaking_scenarios: number;
    levels: string[];
  };
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
  // Speaking 2.0 (V1.34): true si el score es un proxy (p. ej. pronunciation
  // derivado de similitud fonética de texto, no de análisis acústico real).
  proxy?: boolean;
}

export interface SpeakingTrend {
  recent_mean: number | null;
  prior_mean: number | null;
  delta: number | null;
  direction: string;
}

export interface SpeakingInteractionQuality {
  dimension: string;
  attempts: number;
  mean: number | null;
  recent_score: number | null;
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
  interaction_quality?: SpeakingInteractionQuality[];
}

export interface EnduranceMilestone {
  seconds: number;
  achieved: boolean;
}

export interface ConversationEndurance {
  milestones: EnduranceMilestone[];
  longest_session_seconds: number;
  longest_turn_seconds: number;
  total_speaking_seconds: number;
  turns: number;
  current_goal_seconds: number | null;
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

// --- Speaking Scenarios 3.0 (escenarios comunicativos) ---

export interface SpeakingScenario {
  id: string;
  title: string;
  category: string;
  cefr_target: string;
  task_type: string;
  communicative_objective: string;
  prompt: string;
  metrics: string[];
  difficulty: number;
}

export interface SpeakingScenarios {
  version: string;
  scenarios: SpeakingScenario[];
}

// --- Speaking Mission Performance (V2.9) ---

export interface SpeakingMissionDrill {
  criterion: string;
  title: string;
  instruction: string;
  prompt: string;
}

export interface SpeakingMissionCriterionDelta {
  criterion: string;
  before: number;
  after: number;
  delta: number;
}

export interface SpeakingMissionImprovement {
  before_overall: number | null;
  after_overall: number | null;
  delta: number | null;
  improved: boolean;
  by_criterion: SpeakingMissionCriterionDelta[];
  phase: string;
}

export interface SpeakingMissionEvaluation {
  overall: number | null;
  criteria: Record<string, number | null>;
  observed: Record<string, boolean>;
  weak: string[];
  recommendation: string;
  phase: string;
}

export interface SpeakingMissionAttempt {
  heard: string;
  overall: number | null;
  criteria: Record<string, number | null>;
  observed: Record<string, boolean>;
  duration_seconds: number | null;
}

export interface SpeakingMissionInfo {
  scenario_id: string;
  title: string;
  prompt: string;
  communicative_objective: string;
  cefr_target: string;
  task_type: string;
  metrics: string[];
  difficulty: number | null;
}

export interface SpeakingMissionState {
  session_id: number;
  status: string;
  scenario_id: string;
  mission: SpeakingMissionInfo;
  attempt: SpeakingMissionAttempt | null;
  evaluation: SpeakingMissionEvaluation | null;
  drills: SpeakingMissionDrill[];
  retry: SpeakingMissionAttempt | null;
  improvement: SpeakingMissionImprovement | null;
}

// --- Assessment 2.0 (V2.10) ---

export type AssessmentV2Kind =
  | "formative"
  | "unit"
  | "progress"
  | "level"
  | "retention";

export interface AssessmentV2Item {
  id: string;
  skill: string;
  prompt: string;
  options: string[];
}

export interface AssessmentV2SkillScore {
  correct: number;
  total: number;
  score: number;
}

export interface AssessmentV2Result {
  kind: string;
  overall: number;
  threshold: number;
  passed: boolean;
  correct: number;
  total: number;
  skills: Record<string, AssessmentV2SkillScore>;
  failed_skills: string[];
  phase: string;
}

export interface AssessmentV2RetentionSkill {
  skill: string;
  initial: number | null;
  delayed: number | null;
  delta: number | null;
}

export interface AssessmentV2Retention {
  initial_overall: number;
  delayed_overall: number;
  retention_rate: number | null;
  stable: boolean;
  by_skill: AssessmentV2RetentionSkill[];
  phase: string;
}

export interface AssessmentV2Instrument {
  kind: string;
  title: string;
  objective_id: string;
  unit_id: string;
  unit_ids: string[];
  items: AssessmentV2Item[];
  threshold: number;
  assessment_version: string;
  exam_id?: string | null;
  source_kind?: string | null;
  source_session_id?: number | null;
}

export interface AssessmentV2State {
  session_id: number;
  status: string;
  kind: string;
  level_id: string;
  unit_id: string;
  objective_id: string;
  assessment_version: string;
  instrument: AssessmentV2Instrument;
  result: AssessmentV2Result | null;
  retention: AssessmentV2Retention | null;
  source_session_id: number | null;
}

export interface AssessmentV2Step {
  kind: string;
  available: boolean;
  completed: boolean;
  reason: string;
}

export interface AssessmentV2Readiness {
  ladder_complete: boolean;
  mastery_eligible: boolean;
  mastery_missing: string[];
  next_kind: string | null;
  retention_due: boolean;
  // P1/H5: nivel certificado = peldaño level (examen) + retention reassessment.
  level_certified?: boolean;
}

export interface AssessmentV2MasteryGate {
  met: boolean;
  checks: Record<string, boolean>;
  missing: string[];
  counts: Record<string, number>;
}

export interface AssessmentV2Ladder {
  level_id: string;
  steps: AssessmentV2Step[];
  readiness: AssessmentV2Readiness;
  mastery_gate: AssessmentV2MasteryGate;
  assessment_version: string;
  recent: AssessmentV2State[];
}

// --- FSRS-lite (V2.11) ---

export interface FsrsExplain {
  what: { target_type: string; target_id: string; label: string };
  why: string;
  when: { due_at: string; due: boolean; next_in_days: number };
  how_strong: {
    stability: number;
    retrievability: number;
    difficulty: number;
    state: string;
    reps: number;
    lapses: number;
  };
  last_evidence: {
    at: string | null;
    grade: number | null;
    grade_label: string | null;
  };
  next_evidence: { due_at: string; suggested_interval_days: number };
  fsrs_version: string;
}

export interface FsrsCard {
  target_type: string;
  target_id: string;
  label: string;
  state: string;
  difficulty: number;
  stability: number;
  reps: number;
  lapses: number;
  due_at: string;
  last_review_at: string;
  last_evidence_at: string;
  last_grade: number | null;
  why: string;
  fsrs_version: string;
  explain: FsrsExplain | null;
}

export interface FsrsDue {
  due_count: number;
  cards: FsrsCard[];
  fsrs_version: string;
}

export interface FsrsSummary {
  total: number;
  due_count: number;
  by_state: Record<string, number>;
  by_type: Record<string, number>;
  fsrs_version: string;
}

export interface FsrsReview {
  card: FsrsCard;
  explain: FsrsExplain;
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

export interface CourseObjectiveRef {
  objective_id: string;
  title: string;
  status: AcademyObjectiveStatus;
}

export interface CourseLesson {
  lesson_id: string;
  lesson_title: string;
  lesson_order: number;
  mastered: number;
  total: number;
  progress: number;
  status: "done" | "current" | "locked";
  objectives: CourseObjectiveRef[];
}

export interface CourseUnit {
  module_id: string;
  module_title: string;
  module_order: number;
  unit_id: string;
  unit_title: string;
  unit_order: number;
  mastered: number;
  total: number;
  progress: number;
  status: "done" | "current" | "locked";
  // V2.2: Learning Objectives ("By the end of this unit..."), plantilla de 7
  // secciones con huecos visibles y desglose de Mastery Gates.
  objectives: string[];
  sections: CourseUnitSection[];
  gates: CourseGate[];
  gate_mastered: boolean;
  lessons: CourseLesson[];
}

export interface CourseUnitSection {
  section: string;
  count: number;
  needs_content: boolean;
}

export interface CourseGate {
  section: string;
  label: string;
  value: number;
  required: number;
  met: boolean;
  declared: boolean;
}

export interface CoursePosition {
  level_id: string;
  level: string;
  title: string;
  objective_id: string | null;
  objective_title: string | null;
  objective_order: number;
  module_id: string | null;
  module_title: string | null;
  unit_id: string | null;
  unit_title: string | null;
  lesson_id: string | null;
  lesson_title: string | null;
  unit_index: number;
  unit_count: number;
  mastered: number;
  total: number;
  progress: number;
  complete: boolean;
}

export interface CourseProgress {
  mastered: number;
  total: number;
  progress: number;
}

export interface CourseMap {
  level_id: string;
  level: string;
  title: string;
  description: string;
  units: CourseUnit[];
  position: CoursePosition;
  progress: CourseProgress;
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

export interface Certification {
  required: boolean;
  certified: boolean;
  window_min_days: number;
  min_delayed: number;
  delayed_by_skill: Record<string, number>;
  pending_skills: string[];
  checks: Record<string, boolean>;
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
  // P1/H5: completado (examen aprobado) ≠ certificado (retention retardada).
  certification?: Certification | null;
}

export interface LevelCompletion {
  id: number;
  level_id: string;
  level: string;
  overall: number;
  awarded_at: string;
  certification?: Certification | null;
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
  transfer_required?: number;
  novel_required?: number;
  transfer_count?: number;
  novel_count?: number;
}

export interface Readiness {
  target_level: string;
  skills: ReadinessSkill[];
  overall: number;
  blocking_skills: string[];
  ready: boolean;
  band: string;
}

// Tríada Progress / Mastery / Readiness (V2.2)
export interface Dashboard {
  progress: number;
  mastery: number;
  readiness: {
    overall: number;
    band: string;
  };
}

export interface Reassessment {
  skill: string;
  level: string;
  reason: string;
}

export interface MasteryRecord {
  skill: string;
  score: number;
  confidence: number;
  evidence_count: number;
  last_seen_at: string;
  retention: number;
  stability: number;
  review_due: boolean;
  review_in_days: number | null;
  transfer_count: number;
  novel_count: number;
  stage: string;
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
  mastery: MasteryRecord[];
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

export interface NextBestActivity {
  kind: string;
  step_key: string;
  skill: string | null;
  subskill: string | null;
  objective_id: string | null;
  level_id: string | null;
  title: string;
  reason: string;
  minutes: number;
  priority: number;
  signals?: Record<string, unknown>;
  why?: string;
  because?: string[];
  limiting_factor?: {
    id: string;
    score: number;
    missing?: boolean;
    kind?: string;
  } | null;
  graph_mastery?: number | null;
  can_do?: string | null;
}

// --- Evidence Graph (V2.12) ---

export interface EvidenceGraphDimension {
  id: string;
  kind: string;
  score: number;
  evidence_count: number;
  missing: boolean;
}

export interface EvidenceGraphLimiting {
  id: string;
  score: number;
  missing: boolean;
  kind: string;
}

export interface EvidenceGraphFocus {
  dimension: string | null;
  phase: string;
  reason: string;
}

export interface EvidenceGraphNode {
  objective_id: string;
  can_do: string;
  title: string;
  level_id: string;
  level: string;
  dimensions: EvidenceGraphDimension[];
  limiting_factor: EvidenceGraphLimiting | null;
  mastery: number;
  recommended_focus: EvidenceGraphFocus;
  graph_version: string;
}

export interface EvidenceGraph {
  level_id: string;
  level: string;
  nodes: EvidenceGraphNode[];
  open_count: number;
  mastered_count: number;
  average_mastery: number;
  top_limiting_factor: { id: string; count: number } | null;
  graph_version: string;
}

// --- Escalera CEFR (Curriculum 2.0) ---

export interface CefrDimension {
  id: string;
  label: string;
  state?: "mastered" | "in_progress" | "not_started";
}

export interface CefrBand {
  id: string;
  label: string;
  numeric: number;
  title: string;
  description: string;
  can_do: Record<string, string[]>;
  is_current: boolean;
}

export interface CefrLadder {
  dimensions: CefrDimension[];
  bands: CefrBand[];
  estimated_band: string | null;
  estimated_numeric: number | null;
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
