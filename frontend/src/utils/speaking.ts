import type { SpeakingCriterionProgress } from "../types/api";

/** Niveles CEFR ordenados por su parte entera continua (1..6). */
const CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"] as const;

/**
 * Tipos de tarea de speaking que observan interacción conversacional real
 * (turn-taking). Espejo del `CONVERSATIONAL_TASK_TYPES` del backend.
 */
export const CONVERSATIONAL_TASK_TYPES: ReadonlyArray<string> = [
  "role_play",
  "conversation",
  "discussion",
  "interview",
];

/** ¿La tarea observa interacción conversacional (turn-taking real)? */
export function isConversationalTaskType(taskType: string): boolean {
  return CONVERSATIONAL_TASK_TYPES.includes(taskType);
}

/**
 * Mensaje semilla para el tutor en un role-play: le pide adoptar el otro papel
 * del escenario y mantenerse en personaje. Se envía al LLM como primer mensaje
 * (rol "user") y NO se muestra ni persiste como turno del alumno.
 */
export function rolePlaySetup(scenario: string): string {
  return (
    "Role-play. You are the other speaker in this scenario and must stay in " +
    `character. ${scenario} Start the conversation.`
  );
}

/** Etiqueta legible de cada criterio del rubric de speaking. */
export function criterionLabel(criterion: string): string {
  switch (criterion) {
    case "task_achievement":
      return "Tarea";
    case "grammatical_control":
      return "Gramática";
    case "lexical_resource":
      return "Léxico";
    case "fluency":
      return "Fluidez";
    case "pronunciation":
      return "Pronunciación";
    case "coherence":
      return "Coherencia";
    case "interaction":
      return "Interacción";
    default:
      return criterion;
  }
}

/**
 * Convierte el nivel CEFR continuo a su forma compuesta "A1"…"C2" + décima.
 * La parte entera mapea al nivel (A1=1.x, A2=2.x, B1=3.x, B2=4.x, C1=5.x,
 * C2=6.x) y el decimal es la décima del progreso dentro de ese nivel.
 * Ej.: 3.1 → "B1.1", 2.7 → "A2.7". Se acota a [1, 6] y se redondea a la
 * décima más cercana (con arrastre al nivel siguiente si llega a .10).
 */
export function numericToCefr(numeric: number): string {
  const clamped = Math.min(6, Math.max(1, numeric));
  const totalTenths = Math.round(clamped * 10);
  let whole = Math.floor(totalTenths / 10);
  const tenth = totalTenths % 10;
  if (whole < 1) whole = 1;
  if (whole > 6) whole = 6;
  return `${CEFR_LEVELS[whole - 1]}.${tenth}`;
}

/** Formatea una confianza 0..1 como porcentaje entero; ej. 0.86 → "86%". */
export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

/**
 * Formatea una puntuación 0..1 como porcentaje entero; `null` → "—".
 * Ej.: 0.62 → "62%", null → "—".
 */
export function formatScorePct(score: number | null): string {
  return score == null ? "—" : `${Math.round(score * 100)}%`;
}

/**
 * Formatea una duración objetivo en segundos de forma legible:
 * <60s → "45 s"; >=60s exactos → "1 min"; resto → "1:30".
 */
export function formatDurationTarget(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "—";
  if (seconds < 60) return `${Math.round(seconds)} s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return secs === 0 ? `${mins} min` : `${mins}:${String(secs).padStart(2, "0")}`;
}

/**
 * Formatea una delta de tendencia (media 0..1) como puntos porcentuales con
 * signo; `null` → "—". Ej.: +0.12 → "+12%", -0.05 → "−5%".
 */
export function formatTrendDelta(delta: number | null): string {
  if (delta === null) return "—";
  const pct = Math.round(delta * 100);
  if (pct > 0) return `+${pct}%`;
  if (pct < 0) return `−${Math.abs(pct)}%`;
  return "0%";
}

/** Puntuación efectiva de un criterio: prioriza la ventana reciente. */
function criterionScore(c: SpeakingCriterionProgress): number {
  const score = c.recent_score ?? c.mean;
  return score ?? Number.POSITIVE_INFINITY;
}

/**
 * Devuelve los 1-2 criterios prioritarios a repasar: primero los que tienen
 * `review_due`, y entre los restantes los de menor puntuación (reciente o
 * media). Si no hay evidencia, devuelve una lista vacía.
 */
export function nextFocus(criteria: SpeakingCriterionProgress[]): string[] {
  return criteria
    .filter((c) => c.review_due || c.recent_score != null || c.mean != null)
    .slice()
    .sort((a, b) => {
      const reviewDiff = Number(b.review_due) - Number(a.review_due);
      if (reviewDiff !== 0) return reviewDiff;
      return criterionScore(a) - criterionScore(b);
    })
    .slice(0, 2)
    .map((c) => c.criterion);
}
