import type { LexicalItem, LexicalStatus } from "../../types/api";

// Prioridad de orden: primero lo que necesita atención (weak → learning →
// known → mastered); dentro de cada grupo, menor recall primero.
export const STATUS_PRIORITY: Record<LexicalStatus, number> = {
  weak: 0,
  learning: 1,
  known: 2,
  mastered: 3,
};

export function sortLexicalItems(items: LexicalItem[]): LexicalItem[] {
  return [...items].sort((a, b) => {
    const pa = STATUS_PRIORITY[a.status];
    const pb = STATUS_PRIORITY[b.status];
    if (pa !== pb) return pa - pb;
    return a.recall - b.recall;
  });
}

/** Palabras reconocidas (input) pero nunca producidas: candidatas a micro-drill. */
export function recognizedNotProduced(items: LexicalItem[]): string[] {
  return items
    .filter((it) => it.exposures > 0 && it.appearances === 0)
    .map((it) => it.word);
}

/** Valor 0..1 de la barra CEFR normalizado respecto al nivel con más ítems. */
export function cefrBarValue(count: number, max: number): number {
  if (max <= 0) return 0;
  return count / max;
}
