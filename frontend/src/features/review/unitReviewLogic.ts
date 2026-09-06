import type {
  UnitReviewPlanUnit,
  UnitReviewWindowState,
} from "../../types/api";

/**
 * Lógica pura del repaso por unidad (V3.16) — separada del componente para
 * poder testearla sin DOM (la suite vitest corre en entorno node).
 */

/** Estados de ventana que admiten repaso (micro-review). */
export const REVIEWABLE_WINDOW_STATES: ReadonlyArray<UnitReviewWindowState> = [
  "due_now",
  "failed",
];

/** ¿La ventana está pendiente de superar (se puede repasar ahora)? */
export function isReviewableWindowState(
  state: UnitReviewWindowState,
): boolean {
  return REVIEWABLE_WINDOW_STATES.includes(state);
}

/**
 * ¿La unidad tiene alguna ventana repasable? Sin masterizar nunca hay ventanas
 * (el plan solo lista unidades completadas), así que `false` por defecto.
 */
export function hasReviewableWindow(unit: UnitReviewPlanUnit): boolean {
  return unit.windows.some((w) => isReviewableWindowState(w.state));
}

/**
 * Tono de la tarjeta de estado (mapea a clases de color en el componente):
 * `passed`→verde, `due_now`→ámbar, `failed`→rojo, resto→neutro.
 */
export function windowStateTone(
  state: UnitReviewWindowState,
): "passed" | "due_now" | "failed" | "muted" {
  switch (state) {
    case "passed":
      return "passed";
    case "due_now":
      return "due_now";
    case "failed":
      return "failed";
    default:
      return "muted";
  }
}

/** Porcentaje legible a partir de una fracción 0..1 (0.7 → "70%"). */
export function formatPercent(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}

/** Letra de opción de un check MC (0 → "A", 1 → "B", …). */
export function optionLetter(index: number): string {
  return String.fromCharCode(65 + index);
}

/** Total de unidades del plan con ventanas repasables (para el contador). */
export function countReviewableUnits(
  units: ReadonlyArray<UnitReviewPlanUnit>,
): number {
  return units.filter(hasReviewableWindow).length;
}
