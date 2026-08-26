import type { WritingCriterionProgress } from "../types/api";

// Reutiliza los formateadores genéricos de speaking (nivel continuo, confianza
// y delta de tendencia) para no duplicar lógica entre destrezas.
export {
  formatConfidence,
  formatScorePct,
  formatTrendDelta,
  numericToCefr,
} from "./speaking";

/** Etiqueta legible de cada criterio del rubric de writing. */
export function writingCriterionLabel(criterion: string): string {
  switch (criterion) {
    case "task_completion":
      return "Task completion";
    case "grammatical_accuracy":
      return "Grammatical accuracy";
    case "lexical_resource":
      return "Lexical resource";
    case "organization":
      return "Organization";
    case "coherence":
      return "Coherence";
    case "register":
      return "Register";
    default:
      return criterion;
  }
}

/** Puntuación efectiva de un criterio: prioriza la ventana reciente. */
function writingCriterionScore(c: WritingCriterionProgress): number {
  const score = c.recent_score ?? c.mean;
  return score ?? Number.POSITIVE_INFINITY;
}

/**
 * Devuelve los 1-2 criterios prioritarios a repasar: primero los que tienen
 * `review_due`, y entre los restantes los de menor puntuación (reciente o
 * media). Si no hay evidencia, devuelve una lista vacía.
 */
export function writingNextFocus(
  criteria: WritingCriterionProgress[],
): string[] {
  return criteria
    .filter((c) => c.review_due || c.recent_score != null || c.mean != null)
    .slice()
    .sort((a, b) => {
      const reviewDiff = Number(b.review_due) - Number(a.review_due);
      if (reviewDiff !== 0) return reviewDiff;
      return writingCriterionScore(a) - writingCriterionScore(b);
    })
    .slice(0, 2)
    .map((c) => c.criterion);
}
