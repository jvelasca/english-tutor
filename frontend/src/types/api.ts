export type Role = "user" | "assistant";

export type TutorMode = "conversation" | "grammar" | "exercises" | "pronunciation";

export type PronunciationLevel = "good" | "fair" | "needs_practice";

export interface Message {
  id?: string;
  role: Role;
  content: string;
  /** Modo del turno. `voice` (diálogo guiado, F3) marca un turno hablado: su
   *  telemetría sí computa como tiempo de habla (a diferencia del tecleo
   *  `conversation`, CONV-01 V3.19). */
  mode?: TutorMode | "voice";
  duration_ms?: number;
  latency_ms?: number;
}

export interface ChatResponse {
  model: string;
  content: string;
}

export interface ModelsResponse {
  models?: string[];
  // V3.21 (V20-05): modelo por defecto (fuente única en `config.DEFAULT_MODEL`
  // del backend). `null`/ausente en backends antiguos.
  default_model?: string | null;
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

/** Una voz Piper instalada (id técnico + etiqueta amigable). */
export interface VoiceInfo {
  id: string;
  name: string;
}

/** Voz del catálogo curado que se puede descargar desde la UI. */
export interface DownloadableVoice {
  id: string;
  name: string;
  size_mb: number;
}

/** Catálogo de voces instaladas/descargables y la selección actual. */
export interface VoicesResponse {
  voices: VoiceInfo[];
  downloadable: DownloadableVoice[];
  default: string;
  selected: string;
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
  // V3.21 (V20-14/15): metadatos ASR. Si `asr_status !== "ok"` el intento no se
  // registró como fallo lingüístico (el audio no se reconoció con fiabilidad).
  asr_status?: AsrStatus;
  asr_confidence?: number | null;
}

export type AsrStatus = "ok" | "no_speech" | "unintelligible" | "low_confidence";

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

// V3.21 (V20-16) / V3.22 / V3.23: matriz Recognition/Production/Transfer/
// Retention. V3.23: `retention` exige recuperación DEMORADA (retrieval_days >=
// umbral) y `transfer`/`transfer_contexts` se miden por contexto de actividad
// (`channel:activity`); `spaced_exposure`/`spaced_production` son señales
// espaciadas independientes (informativas, no certifican retención).
export interface LexicalCompetence {
  recognition: boolean;
  production: boolean;
  production_channels: string[];
  transfer_contexts: number;
  transfer: boolean;
  retention: boolean;
  spaced_exposure: boolean;
  spaced_production: boolean;
  retrieval_successes: number;
  retrieval_days: number;
  // V3.34 (Recall 2.0): recuperación de la palabra desde su significado (paso
  // Recall por texto). Señal propia: no acredita producción ni sustituye la
  // recuperación demorada (`retention`).
  cued_recall?: boolean;
  recall_successes?: number;
  // V3.35 (Longitudinal Learning Evidence): INTENTOS de recall (acierto o
  // fallo). Sin intentos no se distingue "no lo intentó" de "falló".
  recall_attempts?: number;
  recall_days?: number;
  production_gap: boolean;
  transfer_gap: boolean;
}

// V3.35 (Longitudinal Learning Evidence): evidencia fina del ledger
// (`learning_evidence`), aditiva a los contadores rápidos de `vocabulary`.
// Cada recuperación/producción es un EVENTO con su intervalo; la retención se
// lee como la cadena evento_n → intervalo → evento_{n+1}.
export interface LexicalEvidence {
  attempts: number;
  successes: number;
  // Días naturales distintos con éxito (dos aciertos el mismo día cuentan uno).
  distinct_success_days: number;
  // Intervalos (días) de los eventos con éxito, en orden CRONOLÓGICO: es la
  // cadena real de repasos, no una lista ordenada por valor.
  intervals: number[];
  // V3.36 (Learning Evidence 2.0): dimensiones del evento.
  success_rate: number;
  // Aciertos sin apoyo (`independent`/`spontaneous`): lo único que podrá pesar
  // en automaticidad.
  independent_successes: number;
  // V3.37 (cues graduados): días distintos con éxito sin apoyo (lo que exige
  // `is_automatic`) y éxitos de recall por peldaño servido.
  independent_success_days: number;
  recall_rungs: Record<string, number>;
  // V3.37.1 (consolidación y regresión): días distintos con éxito por peldaño
  // (lo que exige dar el peldaño por superado) y fallos por peldaño (lo que lee
  // la regresión hacia más apoyo).
  recall_rung_days: Record<string, number>;
  recall_rung_failures: Record<string, number>;
  // V3.38 (P1-03): segmentación por MODALIDAD (`LEXICAL_SKILLS`). La
  // automaticidad deja de ser global: estos histogramas permiten leer en qué
  // modalidad el ítem acumula éxito (y éxito sin apoyo) y en cuáles no.
  skill_successes: Record<string, number>;
  skill_success_days: Record<string, number>;
  skill_independent_successes: Record<string, number>;
  skill_independent_days: Record<string, number>;
  // V3.38.1 (P1-02): intentos y latencia media POR MODALIDAD, para que la
  // fluidez y la ratio de éxito se puedan leer por skill (p. ej. `slow_recall`
  // sobre `recall`) en lugar de sobre una media global que mezcla modalidades.
  skill_attempts: Record<string, number>;
  skill_mean_response_time_ms: Record<string, number>;
  support_levels: Record<string, number>;
  error_types: Record<string, number>;
  // Latencia media declarada (null si ningún evento la midió).
  mean_response_time_ms: number | null;
  // V3.39 (Fase 3C): recencia y distribución de latencia (aditivos). Miran la
  // VENTANA de eventos recientes, no todo el histórico: lo que importa es la
  // confusión que sigue ocurriendo.
  recent_attempts?: number;
  recent_error_rate?: number;
  recent_wrong_word?: number;
  median_response_time_ms?: number | null;
  p75_response_time_ms?: number | null;
  p90_response_time_ms?: number | null;
  recent_response_time_ms?: number | null;
  latency_trend?: number | null;
  // V3.40 (Fase 4): CONTEXTOS del ledger. `situation` es recuperación
  // contextualizada; estos contadores son los que permiten demostrar la
  // transferencia real (éxito en >= 2 contextos distintos).
  contexts?: Record<string, { attempts: number; successes: number }>;
  context_attempts?: number;
  success_contexts?: string[];
  home_context?: string;
  transfer?: boolean;
  // V3.43 (P1-03/P1-04): éxito LIMPIO (sin `semantic_mismatch`), diversidad
  // contextual REAL de esos contextos y estado formalizado del eje de
  // transferencia (`not_ready`→`automatic`). Aditivos.
  clean_successes?: number;
  clean_success_contexts?: string[];
  clean_success_days?: number;
  context_diversity?: ContextDiversity | null;
  transfer_state?: string;
}

// V3.43 (P1-03): diversidad contextual REAL de una colección de contextos. No
// basta con `context_id A != context_id B`: `diverse_dimensions` cuenta cuántas
// dimensiones pedagógicas (topic, goal, discurso…) cambian de verdad.
export interface ContextDiversity {
  distinct_contexts: number;
  dimensions: Record<string, string[]>;
  diverse_dimensions: number;
  score: number;
}

export interface LexicalItem {
  word: string;
  lemma: string;
  cefr: string;
  kind: string;
  source: string;
  status: LexicalStatus;
  recall: number;
  next_review_days: number;
  // V3.25 (F-K7/P2-01/P2-02): contadores canónicos (el histórico
  // appearances/exposures quedó renombrado en el backend). `lexical_unit` es
  // la unidad de análisis (lemma cuando el currículo lo declara); `word` es la
  // forma superficial.
  production_count: number;
  exposure_count: number;
  lexical_unit?: string;
  // V3.19: desglose de producción por destreza (columnas `<channel>_prod`).
  chat_prod: number;
  speaking_prod: number;
  writing_prod: number;
  conversation_prod: number;
  // V3.21 (V20-16): matriz de competencia (puede faltar en respuestas viejas).
  competence?: LexicalCompetence | null;
  // V3.35: historia longitudinal del ítem (puede faltar en respuestas viejas).
  evidence?: LexicalEvidence | null;
}

export interface DrillCandidates {
  words: string[];
}

export interface DrillAttempt {
  word: string;
  produced: boolean;
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
  fluency?: FluencyStats | null;
  // V3.21 (V20-14/15): con `asr_status !== "ok"` produced va False (no se
  // acredita) y la UI no debe interpretarlo como fallo lingüístico.
  asr_status?: AsrStatus;
  asr_confidence?: number | null;
}

// V3.21 (F6.1): paso "Sentence" del micro-drill — repetir la palabra dentro de
// una frase de contexto determinista (banco de rutas o plantilla).
export interface DrillSentenceContext {
  word: string;
  phrase: string;
  source: "route" | "template";
  level: string;
}

export interface DrillSentenceAttempt {
  word: string;
  phrase: string;
  source: "route" | "template";
  /** La palabra objetivo quedó alineada en la transcripción (V20-01). */
  produced: boolean;
  /** La frase COMPLETA superó el umbral del scorer. */
  phrase_ok: boolean;
  /** produced AND phrase_ok: lo que acredita producción por este paso. */
  passed: boolean;
  heard: string;
  score: number;
  level: PronunciationLevel;
  fluency?: FluencyStats | null;
  asr_status?: AsrStatus;
  asr_confidence?: number | null;
}

// V3.33 (eslabón 2 del puente): paso Recognition — MCQ definición ↔ palabra.
// La pregunta es determinista en el servidor (premisa 21): el GET nunca incluye
// la opción correcta y `correct_index` solo llega en la respuesta del intento.
// V3.33.1: `question_id` (nonce por intento) se reenvía en el POST para
// reconstruir la permutación servida y rebarajar la posición de la correcta.
export interface DrillRecognitionQuestion {
  word: string;
  available: boolean;
  options: string[];
  question_id: string;
}

export interface DrillRecognitionAttempt {
  word: string;
  correct: boolean;
  correct_index: number;
  selected_index: number;
}

// V3.34 (Recall 2.0): paso Recall — camino INVERSO a Recognition. El alumno ve
// el SIGNIFICADO (cue: traducción o definición) y teclea la palabra. El GET
// nunca expone la palabra esperada; el POST la revela tras puntuar (premisa
// 21). El acierto deja señal léxica propia (recall + FSRS), nunca producción.
// V3.37 (cues graduados): `cue_kind` admite el tercer peldaño (`cloze`, con la
// frase en blanco como `cue`) y `support_level` declara el apoyo del peldaño
// servido (`cued`/`guided`).
// V3.38: `cue_kind` admite el cuarto peldaño (`situation`, enunciado situacional
// del contrato de contenido de la caché, con hueco `_____`).
export interface DrillRecallPrompt {
  word: string;
  available: boolean;
  cue: string;
  cue_kind: string; // "translation" | "definition" | "cloze" | "situation" | ""
  support_level?: string; // "cued" | "guided" | ""
}

export interface DrillRecallAttempt {
  word: string;
  correct: boolean;
  expected: string;
  delayed: boolean;
  recall_days: number;
  // V3.36: clasificación OBSERVACIONAL del intento
  // (correct/empty/wrong_word/orthographic_error/partial/multiple_word_error).
  // Una errata sigue siendo `correct=false`: no cambia el scoring.
  error_type?: string;
}

// V3.39 (Fase 3): actividad de escritura del drill. El alumno escribe una frase
// PROPIA con la palabra objetivo; el servidor la puntúa (unidad alineada +
// longitud mínima) y acredita la modalidad `written_production`, que cierra el
// hueco `spoken ✓ / written ✗` del motor de tarea óptima.
export interface DrillWriteAttempt {
  word: string;
  text: string;
  used_word: boolean;
  word_count: number;
  passed: boolean;
  // Taxonomía observacional: correct/empty/missing_target/too_short.
  error_type?: string;
}

// V3.40 (Fase 4): actividad de TRANSFERENCIA. El alumno usa la unidad en un
// contexto NUEVO (banco curado de `services.transfer`); el `context_id` es el
// del ledger y es lo que permite demostrar la transferencia real (éxito en >= 2
// contextos distintos). Cierra la modalidad `spontaneous_use`.
export interface DrillTransferContext {
  word: string;
  context_id: string;
  topic: string;
  prompt: string;
  available: boolean;
  // V3.43 (P1-01): consigna sin target; estos campos (aditivos) explican la
  // producción pedida y si el banco ya rotó por completo.
  exhausted?: boolean;
  communicative_goal?: string;
  discourse_type?: string;
}

export interface DrillTransferAttempt {
  word: string;
  text: string;
  context_id: string;
  used_word: boolean;
  word_count: number;
  passed: boolean;
  // Taxonomía observacional: correct/empty/missing_target/too_short/
  // semantic_mismatch (V3.43).
  error_type?: string;
  // V3.43 (P1-02): transfer LÉXICO (alias de `passed`) separado de la
  // adecuación semántica determinista (`semantic_fit`/`adequacy`). `semantic_fit`
  // es null cuando no es determinable (sin POS declarada).
  lexical_transfer?: boolean;
  semantic_fit?: boolean | null;
  adequacy?: "fit" | "suspect" | "unknown" | string;
}

// V3.30: diccionario de consulta con marca de uso/aprendizaje. La consulta es
// SOLO lectura (D3): el backend no registra evidencia. `definition_source`
// distingue contenido cacheado generado por el modelo local ("llm") de su
// ausencia ("none", modelo caído o aún sin generar): en ese caso `definition`
// y `translation` son null y la UI muestra igualmente uso y ejemplo.
export interface DictionaryExample {
  phrase: string;
  source: string;
  level: string;
}

export interface DictionarySurfaceUsage {
  status: LexicalStatus | null;
  mastery: number;
  recall: number;
  next_review_days: number;
  production_count: number;
  exposure_count: number;
  production_channels: string[];
  competence: LexicalCompetence | null;
  last_activity_at: string;
}

export interface DictionaryUnitUsage {
  lexical_unit: string;
  status: LexicalStatus | null;
  mastery: number;
  recall: number;
  surface_count: number;
  mastered_surfaces: number;
  recognized: boolean;
  produced: boolean;
  transfer: boolean;
  production_count: number;
  exposure_count: number;
}

export interface DictionaryUsage {
  tracked: boolean;
  surface: DictionarySurfaceUsage | null;
  unit: DictionaryUnitUsage | null;
}

export interface DictionaryEntry {
  word: string;
  kind: string;
  cefr: string;
  definition_source: "llm" | "none";
  pos: string;
  definition: string | null;
  translation: string | null;
  /**
   * V3.39: dirección servida. En `es-en`, `word` es el término español buscado,
   * `translation` es el equivalente INGLÉS y `alternatives` las otras
   * traducciones encontradas en la inversa instantánea.
   */
  direction: "en-es" | "es-en";
  alternatives: string[];
  /** V3.38: enunciado situacional (4.º peldaño de recall), con hueco `_____`. */
  situation?: string | null;
  example: DictionaryExample | null;
  usage: DictionaryUsage;
}

/** Cuerpo de la consulta al diccionario (V3.30): la palabra tal como la
 * escribe el alumno y una preferencia opcional de modelo local (mismo
 * contrato que `/api/translate`). El backend la normaliza (minúsculas, sin
 * puntuación circundante) y traduce una palabra vacía a 422. V3.39 añade la
 * dirección (`en-es` por defecto). */
export interface DictionaryLookupRequest {
  word: string;
  model?: string;
  direction?: DictionaryDirection;
}

/** V3.39: dirección de búsqueda del diccionario de consulta. */
export type DictionaryDirection = "en-es" | "es-en";

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
  // V3.21 (V20-16) / V3.22 / V3.23: contadores de la matriz de competencia.
  // V3.23: `retention` cuenta recuperaciones demoradas; `spaced_exposure` es el
  // contador informativo de exposición espaciada (señal independiente).
  recognized: number;
  produced: number;
  transfer: number;
  retention: number;
  spaced_exposure: number;
  // V3.34: recuperadas desde el significado en el paso Recall del drill.
  recalled?: number;
  production_gap: number;
  transfer_gap: number;
  // V3.25.1 (P1-02): resumen del agregado por `lexical_unit` (cada unidad
  // cuenta una sola vez). Opcional/aditivo; el contrato por superficie no cambia.
  units?: LexiconUnitSummary | null;
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

// V3.25.1 (P1-02): superficie (surface form) dentro de una unidad léxica
// agregada. Cada forma conserva su propio estado/mastery/recall: dominar "go"
// no domina automáticamente "going"/"went"/"gone".
export interface LexicalUnitSurface {
  word: string;
  lemma: string;
  cefr: string;
  kind: string;
  source: string;
  status: LexicalStatus;
  mastery: number;
  recall: number;
  production_count: number;
  exposure_count: number;
  speaking_prod: number;
  competence?: LexicalCompetence | null;
}

// V3.25.1 (P1-02): unidad léxica agregada (`lexical_unit`) con sus superficies.
export interface LexicalUnit {
  lexical_unit: string;
  kind: string;
  cefr: string;
  lemma: string;
  source: string;
  status: LexicalStatus;
  mastery: number;
  recall: number;
  surface_count: number;
  mastered_surfaces: number;
  recognized: boolean;
  produced: boolean;
  transfer: boolean;
  production_count: number;
  exposure_count: number;
  production_gap: boolean;
  transfer_gap: boolean;
  surfaces: LexicalUnitSurface[];
}

export interface LexiconUnitSummary {
  total: number;
  mastered: number;
  learning: number;
  known: number;
  weak: number;
  by_cefr: CefrBucket[];
  recognized: number;
  produced: number;
  transfer: number;
  production_gap: number;
  transfer_gap: number;
  surface_total: number;
  mastered_surfaces: number;
}

export interface Lexicon {
  summary: LexiconSummary;
  items: LexicalItem[];
  coverage?: LexiconCoverage | null;
  // V3.25.1 (P1-02): agregado por `lexical_unit` (aditivo, contrato intacto).
  units?: LexicalUnit[];
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
  // V3.35: rol del evento (evidence/telemetry/informative) derivado en servidor.
  event_role?: string;
}

// V3.35 (Longitudinal Learning Evidence, P1-2): cola de repaso del léxico.
// Separa el repaso espaciado (FSRS) del speaking micro-drill: cada ítem vencido
// llega con la actividad recomendada por hueco de competencia.
export type ReviewActivity =
  | "recognition"
  | "recall"
  | "sentence"
  | "write"
  | "transfer";

// V3.39 (Fase 3, motor de tarea óptima): la DECISIÓN de tarea del planner
// (`services.planner.select_task`): qué modalidad limita, qué actividad la
// cierra, por qué y con cuánto apoyo se espera el intento.
export interface ReviewTask {
  skill: string;
  activity: ReviewActivity | "";
  reason: string;
  support_level: string;
}

export interface ReviewQueueItem {
  word: string;
  lexical_unit: string;
  cefr: string;
  kind: string;
  due_at: string;
  state: string;
  stability: number;
  retrievability: number | null;
  elapsed_days: number | null;
  activity: ReviewActivity;
  reason: string;
  // V3.37 (cues graduados): peldaño recomendado para `recall` (nombre, nunca el
  // cue) y si el ítem acumula éxito independiente y espaciado.
  recommended_cue?: string;
  automatic?: boolean;
  // V3.38 (planner / Optimal Next Task): prioridad combinada 0..1, señales que
  // la producen, explicación legible y modalidades ya automáticas (P1-03).
  priority?: number;
  signals?: Record<string, unknown> | null;
  why?: string;
  automatic_skills?: string[];
  // V3.39 (Fase 3): modalidad que limita y la tarea óptima que la cierra.
  limiting_skill?: string;
  task?: ReviewTask | null;
  competence?: LexicalCompetence | null;
  // V3.40 (Fase 4): gobierno por unidad léxica. `unit_surfaces` son las formas
  // hermanas (go/went/gone/going) y `transfer`/`success_contexts` la
  // transferencia contextual demostrada.
  unit_surfaces?: string[];
  transfer?: boolean;
  success_contexts?: string[];
  // V3.43 (P1-03/P1-04): estado formalizado y diversidad contextual real.
  transfer_state?: string;
  context_diversity?: ContextDiversity | null;
  evidence?: LexicalEvidence | null;
}

// V3.40 (Fase 4): evidencia agregada por UNIDAD léxica (roll-up aditivo de las
// formas superficiales que la componen).
export interface ReviewUnitEvidence {
  lexical_unit: string;
  surfaces: string[];
  surface_count: number;
  attempts: number;
  successes: number;
  distinct_success_days: number;
  independent_successes: number;
  independent_success_days: number;
  success_rate: number;
  error_types: Record<string, number>;
  skill_successes: Record<string, number>;
  skill_success_days: Record<string, number>;
  skill_independent_successes: Record<string, number>;
  skill_independent_days: Record<string, number>;
  skill_attempts: Record<string, number>;
  automatic: boolean;
  automatic_skills: string[];
  success_contexts: string[];
  transfer: boolean;
}

export interface ReviewQueue {
  due_count: number;
  items: ReviewQueueItem[];
  fsrs_version: string;
  // V3.40 (Fase 4): roll-up por unidad (aditivo).
  units?: ReviewUnitEvidence[];
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
  // Capa cognitiva de la taxonomía (V3.26): recognition/comprehension/inference.
  layer: string | null;
  // Micro-flujo por ítem (V3.27, Listening Engine 4.0): pasos pedagógicos y
  // contrato de revelado de la transcripción servidos por el backend (§3.1 del
  // plan V3.27). El frontend solo los ejecuta, sin reglas pedagógicas propias.
  flow?: ListeningFlowStep[];
  transcriptPolicy?: ListeningTranscriptPolicy;
  // Timings gruesos de frase (V3.28, Bloque D): reparto heurístico de
  // `duration` por frase (`sync: "coarse_heuristic"`), para el resaltado de la
  // frase activa con `currentTime`. Presentes solo cuando el ítem trae flow y
  // declara `duration`; vacío no rompe a consumidores antiguos.
  sentenceTimings?: SentenceTiming[];
  // Timings por palabra (V3.29, Fase 3): karaoke palabra a palabra servido
  // desde el sidecar `word_alignment_proxy` del audio (señal ASR, voz default
  // y variante `normal`). `sentence` es el índice de la frase que contiene la
  // palabra en `sentenceTimings` (-1 sin frases/duration). Vacío ⇒ la UI
  // degrada al sync de frase (`CoarseTranscript`).
  wordTimings?: ListeningWordTiming[];
}

export interface ListeningWordTiming {
  index: number;
  text: string;
  start: number;
  end: number;
  sentence: number;
}

export interface SentenceTiming {
  index: number;
  start: number;
  end: number;
  text: string;
  sync: string;
}

export interface ListeningFlowStep {
  stage: ListeningFlowStage;
  task: string;
  transcript_state_inicial: ListeningTranscriptState;
  allow_skip: boolean;
  requires_audio: boolean;
}

export type ListeningFlowStage = "pre" | "while1" | "while2" | "post" | "shadowing";

export type ListeningTranscriptState = "hidden" | "partial" | "full";

export interface ListeningTranscriptPolicy {
  revelation:
    | "on_first_fail"
    | "on_second_fail"
    | "on_finish"
    | "never_before_post";
  max_attempts_per_stage: number;
  allow_manual_reveal: boolean;
  shadowing_optional: boolean;
}

export interface ListeningAudioVariant {
  variant: string;
  speech_rate: number;
  label: string;
}

// Evidencia ampliada por intento (V3.27): apoyo con el que se respondió.
// `layer` es informativo (el backend lo recalcula del skill).
export interface ListeningSupportMetadata {
  layer?: string;
  speedUsed?: string;
  stage?: string;
  transcriptUsed?: string;
  segmentsReplayed?: number;
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
  stage?: string;
  transcript_used?: string;
  speed_used?: string;
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
  // Práctica extra generada (V3.6): `total`/`mastered` del anillo incluyen los
  // ítems extra activados; `base_total`/`base_mastered` son el banco curado
  // oficial (el único que decide la puerta, `completed` y `state`). `extras`
  // son los ítems generados activados y `extras_mastered` los ya acertados.
  base_total?: number;
  base_mastered?: number;
  extras?: number;
  extras_mastered?: number;
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
  // "base" = banco curado oficial; "generated" = práctica extra generada.
  source?: "base" | "generated";
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

/** Trabajo de generación de práctica extra en segundo plano (V3.6). */
export interface ListeningExtrasJob {
  job_id: string;
  status: "running" | "done" | "error";
  level: string;
  requested: number;
  added: string[];
  error: string;
}

/** Ítems extra activados en una ruta (V3.6). */
export interface ListeningRouteExtras {
  level: string;
  total: number;
  question_ids: string[];
}

// --- Speaking por rutas (V3.8) ----------------------------------------------
// Mismas mecánicas que listening (mapa CEFR con anillos, repaso de falladas/
// aprendidas, práctica extra generada) pero con tarjetas de micro-conversación
// guiada: situación + rol + línea del interlocutor (con voz modelo); el alumno
// responde hablando y tras la evaluación se revela la respuesta modelo. El
// estado `functional` es el techo de la ruta (práctica); demostrar el nivel
// exige el Speaking Assessment y evidencia formal, no la ruta.

export type SpeakingRouteState = "not_started" | "developing" | "functional";

export interface SpeakingRouteGate {
  passed: boolean;
  total: number;
  mastered: number;
  coverage_pct: number;
  coverage_required_pct: number;
  accuracy: number | null;
  accuracy_required: number;
  topics: number;
  topics_required: number;
  checkpoint: number;
  checkpoint_required: number;
  blockers: string[];
}

export interface SpeakingLevelProgress {
  level: string;
  total: number;
  mastered: number;
  completed: boolean;
  coverage_pct: number | null;
  accuracy: number | null;
  gate?: SpeakingRouteGate | null;
  state?: SpeakingRouteState;
  base_total?: number;
  base_mastered?: number;
  extras?: number;
  extras_mastered?: number;
}

export interface SpeakingStats {
  attempts: number;
  passed: number;
  accuracy: number | null;
  level: string;
  completed: boolean;
  levels: SpeakingLevelProgress[];
}

export type SpeakingItemState = "unseen" | "failed" | "mastered";

export interface SpeakingItem {
  phrase_id: string;
  level: string;
  app_line: string;
  topic: string;
  difficulty: number;
  attempts: number;
  state: SpeakingItemState;
  source?: "base" | "generated";
}

export interface SpeakingLevelItems {
  level: string;
  total: number;
  mastered: number;
  failed: number;
  unseen: number;
  completed: boolean;
  items: SpeakingItem[];
  gate?: SpeakingRouteGate | null;
}

/** Tarjeta de micro-conversación: contexto + rol + línea del interlocutor. */
export interface SpeakingPhrase {
  id: string;
  level: string;
  setup: string;
  you: string;
  app_line: string;
  topic: string;
  difficulty: number;
  difficulty_vector?: Record<string, number>;
  audio_ready: boolean;
}

export interface SpeakingAttempt {
  phrase_id: string;
  level: string;
  app_line: string;
  heard: string;
  model_response: string;
  overall: number;
  passed: boolean;
  criteria: Record<string, number | null>;
  observed: Record<string, boolean>;
  topic: string;
  difficulty: number;
  // V3.21 (V20-14/15): con `asr_status !== "ok"` el turno NO se evaluó ni se
  // persiste como fallo (audio no reconocido): la UI ofrece repetir.
  asr_status?: AsrStatus;
  asr_confidence?: number | null;
}

/** Trabajo de generación de práctica extra de speaking en segundo plano (V3.7). */
export interface SpeakingExtrasJob {
  job_id: string;
  status: "running" | "done" | "error";
  level: string;
  requested: number;
  added: string[];
  error: string;
}

/** Frases extra activadas en una ruta de speaking (V3.7). */
export interface SpeakingRouteExtras {
  level: string;
  total: number;
  phrase_ids: string[];
}

// --- Rutas de Pronunciation (V3.9) -------------------------------------------
// Misma filosofía que speaking/listening: la ruta mide práctica (read-aloud
// determinista sobre el banco oficial) y su estado `functional` es el techo;
// demostrar el nivel exige el Speaking Assessment y evidencia formal, no la ruta.

export type PronunciationRouteState = "not_started" | "developing" | "functional";

export interface PronunciationRouteGate {
  passed: boolean;
  total: number;
  mastered: number;
  coverage_pct: number;
  coverage_required_pct: number;
  accuracy: number | null;
  accuracy_required: number;
  topics: number;
  topics_required: number;
  checkpoint: number;
  checkpoint_required: number;
  blockers: string[];
}

export interface PronunciationLevelProgress {
  level: string;
  total: number;
  mastered: number;
  completed: boolean;
  coverage_pct: number | null;
  accuracy: number | null;
  gate?: PronunciationRouteGate | null;
  state?: PronunciationRouteState;
}

export interface PronunciationStats {
  attempts: number;
  passed: number;
  accuracy: number | null;
  level: string;
  completed: boolean;
  levels: PronunciationLevelProgress[];
}

export type PronunciationItemState = "unseen" | "failed" | "mastered";

export interface PronunciationItem {
  phrase_id: string;
  level: string;
  script: string;
  topic: string;
  difficulty: number;
  attempts: number;
  state: PronunciationItemState;
}

export interface PronunciationLevelItems {
  level: string;
  total: number;
  mastered: number;
  failed: number;
  unseen: number;
  completed: boolean;
  items: PronunciationItem[];
  gate?: PronunciationRouteGate | null;
}

/** Frase modelo de read-aloud de una ruta de pronunciation. */
export interface PronunciationPhrase {
  id: string;
  level: string;
  script: string;
  topic: string;
  difficulty: number;
  difficulty_vector?: Record<string, number>;
}

export interface PronunciationAttempt {
  phrase_id: string;
  level: string;
  script: string;
  heard: string;
  score: number;
  grade: PronunciationLevel;
  passed: boolean;
  word_accuracy: number;
  phonetic_score: number;
  phoneme_accuracy_proxy: number;
  prosody_proxy: number;
  pronunciation_source: string;
  breakdown: PronunciationBreakdown;
  phoneme_breakdown: PhonemeBreakdown;
  fluency: FluencyStats;
  topic: string;
  difficulty: number;
  // V3.21 (V20-14/15): con `asr_status !== "ok"` el intento NO se persiste como
  // fallo (audio no reconocido): la UI avisa y ofrece reintentar.
  asr_status?: AsrStatus;
  asr_confidence?: number | null;
}

// V3.10 — Conversation por rutas: mini-diálogos guiados multi-turno A1-C2. Misma
// filosofía: la ruta mide práctica (diálogos dominados sobre el banco oficial) y
// su estado `functional` es el techo; demostrar el nivel exige el Speaking
// Assessment y evidencia formal, no la ruta.

export type ConversationRouteState = "not_started" | "developing" | "functional";

export interface ConversationRouteGate {
  passed: boolean;
  total: number;
  mastered: number;
  coverage_pct: number;
  coverage_required_pct: number;
  accuracy: number | null;
  accuracy_required: number;
  topics: number;
  topics_required: number;
  checkpoint: number;
  checkpoint_required: number;
  blockers: string[];
}

export interface ConversationLevelProgress {
  level: string;
  total: number;
  mastered: number;
  completed: boolean;
  coverage_pct: number | null;
  accuracy: number | null;
  gate?: ConversationRouteGate | null;
  state?: ConversationRouteState;
}

export interface ConversationStats {
  attempts: number;
  passed: number;
  accuracy: number | null;
  level: string;
  completed: boolean;
  levels: ConversationLevelProgress[];
}

export type ConversationItemState = "unseen" | "failed" | "mastered";

export interface ConversationItem {
  dialogue_id: string;
  level: string;
  opening_line: string;
  topic: string;
  attempts: number;
  state: ConversationItemState;
}

export interface ConversationLevelItems {
  level: string;
  total: number;
  mastered: number;
  failed: number;
  unseen: number;
  completed: boolean;
  items: ConversationItem[];
  gate?: ConversationRouteGate | null;
}

/** Mini-diálogo guiado multi-turno servido para practicar una ruta. */
export interface ConversationDialogue {
  id: string;
  level: string;
  topic: string;
  context: string;
  student_role: string;
  tutor_role: string;
  opening_line: string;
  communicative_goals: string[];
}

export interface ConversationAttempt {
  dialogue_id: string;
  level: string;
  opening_line: string;
  heard: string;
  overall: number;
  passed: boolean;
  criteria: Record<string, number | null>;
  observed: Record<string, boolean>;
  interaction_quality?: Record<string, number | null>;
  topic: string;
  communicative_goals: string[];
}

// --- Rutas de Vocabulary (V3.11) ---------------------------------------------
// Misma filosofía que speaking/listening/pronunciation/conversation: la ruta
// mide práctica (checks MC de vocabulary del currículo, evaluación determinista)
// y su estado `functional` es el techo; demostrar el nivel exige los exámenes y
// la escalera de evaluaciones formales del curso, nunca la ruta.

export type VocabularyRouteState = "not_started" | "developing" | "functional";

export interface VocabularyRouteGate {
  passed: boolean;
  total: number;
  mastered: number;
  coverage_pct: number;
  coverage_required_pct: number;
  accuracy: number | null;
  accuracy_required: number;
  topics: number;
  topics_required: number;
  checkpoint: number;
  checkpoint_required: number;
  /** Banco corto (< 12 ítems): la puerta adapta el checkpoint (nota honesta). */
  short_bank: boolean;
  /** Claim honesto de V3.13: profundidad de la práctica (low/medium). */
  practice_depth?: string;
  blockers: string[];
}

export interface VocabularyLevelProgress {
  level: string;
  total: number;
  mastered: number;
  completed: boolean;
  coverage_pct: number | null;
  accuracy: number | null;
  gate?: VocabularyRouteGate | null;
  state?: VocabularyRouteState;
  /** Tamaño del banco oficial del nivel (claim honesto V3.13). */
  bank_size?: number;
  /** Lectura honesta de la práctica: "low" para bancos cortos (V3.13). */
  evidence_depth?: string;
}

export interface VocabularyStats {
  attempts: number;
  passed: number;
  accuracy: number | null;
  level: string;
  completed: boolean;
  levels: VocabularyLevelProgress[];
}

export type VocabularyItemState = "unseen" | "failed" | "mastered";

export interface VocabularyItem {
  check_id: string;
  level: string;
  topic: string;
  prompt: string;
  attempts: number;
  state: VocabularyItemState;
}

export interface VocabularyLevelItems {
  level: string;
  total: number;
  mastered: number;
  failed: number;
  unseen: number;
  completed: boolean;
  items: VocabularyItem[];
  gate?: VocabularyRouteGate | null;
}

/**
 * Un check MC servido para practicar (sin la respuesta correcta: se oculta
 * hasta el POST /attempt para que el alumno elija sin pistas).
 */
export interface VocabularyQuestion {
  check_id: string;
  level: string;
  topic: string;
  prompt: string;
  options: string[];
}

export interface VocabularyAttempt {
  check_id: string;
  level: string;
  topic: string;
  prompt: string;
  options: string[];
  /** Respuesta correcta revelada solo tras responder (feedback). */
  correct_index: number;
  selected_index: number;
  passed: boolean;
  score: number;
}

// --- Rutas de Grammar (V3.12) ------------------------------------------------
// Misma filosofía y mismas formas que Vocabulary: los checks MC del currículo
// con skill "grammar" se sirven con el mismo motor quiz y el mismo contrato de
// red, así que los tipos se reutilizan por alias para nombrarlos por destreza
// en los componentes de Grammar.

export type GrammarRouteState = VocabularyRouteState;
export type GrammarRouteGate = VocabularyRouteGate;
export type GrammarLevelProgress = VocabularyLevelProgress;
export type GrammarStats = VocabularyStats;
export type GrammarItemState = VocabularyItemState;

/** Tipo de ítem del banco de grammar (V3.13 P1). */
export type GrammarItemType = "mcq" | "controlled_production";

/** ítem de grammar (MC o producción controlada). */
export interface GrammarItem extends VocabularyItem {
  type?: GrammarItemType;
}

export type GrammarLevelItems = VocabularyLevelItems;

/**
 * ítem de grammar servido para practicar (sin la respuesta correcta). `type`
 * distingue el formato: "mcq" pide elegir una opción; "controlled_production"
 * (V3.13 P1) pide escribir la respuesta (las `accepted_answers` se ocultan).
 */
export interface GrammarQuestion extends VocabularyQuestion {
  type?: GrammarItemType;
}

export interface GrammarAttempt extends VocabularyAttempt {
  type?: GrammarItemType;
  /** En producción controlada: la respuesta escrita por el alumno. */
  typed_answer?: string;
  /** En producción controlada: respuestas esperadas reveladas en el feedback. */
  expected_answers?: string[];
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

export interface ListeningAuditoryProfile {
  /** Capa objetivo que el perfil recomienda trabajar; null sin perfil. */
  layer: "recognition" | "comprehension" | "inference" | null;
  intervention:
    | "bottom_up_path"
    | "comprehension_path"
    | "top_down_path"
    | "connected_speech_path"
    | null;
  reason: string;
  needs_min_attempts: boolean;
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
  // Perfil auditivo (V3.27, Listening Engine 4.0): capa e intervención
  // recomendada (casos A-D). Null en respuestas antiguas sin perfil.
  profile?: ListeningAuditoryProfile | null;
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
  // F-C4 (V3.26): el gate retrocedió al conteo de filas para familiar/transfer
  // (sin contextos conocidos — evidencia legacy sin `context_id`).
  legacy_fallback?: boolean;
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

// --- Review/SRS por unidad (V3.16) ---

export type UnitReviewWindowState =
  | "upcoming"
  | "due_now"
  | "passed"
  | "failed";

export interface UnitReviewWindow {
  window_days: number;
  due_at: string;
  state: UnitReviewWindowState;
}

export interface UnitReviewPlanUnit {
  level_id: string;
  unit_id: string;
  module_id: string;
  module_title: string;
  title: string;
  objectives_total: number;
  objectives_mastered: number;
  completed: boolean;
  anchor: string | null;
  windows: UnitReviewWindow[];
}

export interface UnitReviewPlan {
  /** Niveles del plan agregado (V3.18/O3): nivel actual + anteriores
   *  matriculados que tengan unidades completadas o con plan activo. */
  levels: UnitReviewLevel[];
  /** Total global de unidades con ventana repasable (due_now/failed). */
  due_count: number;
}

export interface UnitReviewLevel {
  level_id: string;
  level: string;
  due_count: number;
  units: UnitReviewPlanUnit[];
}

export interface MicroReviewItem {
  item_id: string;
  objective_id: string;
  objective_title: string;
  skill: string;
  prompt: string;
  options: string[];
}

export interface MicroReviewSession {
  level_id: string;
  unit_id: string;
  unit_title: string;
  window_days: number;
  items: MicroReviewItem[];
}

export interface UnitReviewObjectiveResult {
  objective_id: string;
  title: string;
  correct: number;
  total: number;
  accuracy: number;
  grade: number;
  next_due_at: string;
}

export interface MicroReviewItemAudit {
  item_id: string;
  objective_id: string;
  objective_title: string;
  skill: string;
  prompt: string;
  options: string[];
  selected_index: number;
  correct_index: number;
  correct: boolean;
}

export interface MicroReviewResult {
  unit_id: string;
  window_days: number;
  correct: number;
  total: number;
  accuracy: number;
  passed: boolean;
  per_objective: UnitReviewObjectiveResult[];
  items: MicroReviewItemAudit[];
  plan: UnitReviewPlanUnit | null;
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

// --- Registro cross-skill por estructura (V3.13 P1.2 → v3.14 A1–C2) ----------
// Solo lectura: por cada estructura gramatical del nivel, la matriz de
// instrumentos ofrecidos por destreza y la evidencia real del usuario.

export type CrossSkillChannelKey =
  | "recognition"
  | "production"
  | "listening"
  | "speaking"
  | "transfer";

export interface CrossSkillChannel {
  offered: boolean;
  evidence: number;
}

export interface CrossSkillStructure {
  structure_id: string;
  name: string;
  can_do: string;
  channels: Record<CrossSkillChannelKey, CrossSkillChannel>;
}

export interface CrossSkillMatrix {
  level_id: string;
  level: string;
  structures: CrossSkillStructure[];
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
  // V3.25: soporte por emisor y experiencias distintas por evidence_kind.
  evidence_by_kind?: Record<string, number>;
  distinct_contexts_by_kind?: Record<string, number>;
  support_levels?: Record<string, number>;
  independent_count?: number;
  production_count?: number;
  generalized_score?: number | null;
  // F-C4 (V3.26): evidencia legacy sin `context_id` en la destreza.
  legacy_context_rows?: number;
  legacy_context_used?: boolean;
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
  // F-C3 (V3.26): motivo de bloqueo de una destreza evaluada y no lista.
  blocked_by?: string[];
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
  /** V3.25 (Fase 5, F-L3): mayor nivel CEFR demostrado (examen + retención
   * certificable por destreza); null hasta la primera certificación. */
  demonstrated_level: string | null;
  /** Progreso 0..1 dentro del nivel actual (overall del tramo en curso), no
   * confundir con el eje CEFR absoluto de `estimated_numeric`. */
  level_progress: number;
  estimated_level: string;
  estimated_numeric: number;
  confidence: number;
  target_level: string;
  skills: SkillProfile[];
  critical_skills: string[];
  readiness: Readiness;
  reassessment: Reassessment | null;
  mastery: MasteryRecord[];
  // F-C4 (V3.26): el perfil contiene evidencia legacy sin `context_id`.
  legacy_context_evidence?: boolean;
  legacy_context_rows?: number;
}

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
  // V3.17 (D1b): pasos con objetivo y nodo del Evidence Graph. Opcionales:
  // un paso sin objetivo o sin nodo (D7) los trae null/vacíos.
  can_do?: string | null;
  limiting_factor?: {
    id: string;
    score: number;
    missing?: boolean;
    kind?: string;
  } | null;
  graph_mastery?: number | null;
  because?: string[];
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
