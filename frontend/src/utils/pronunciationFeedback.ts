import type { PronunciationBreakdown } from "../types/api";

/** Une palabras en español: "a", "a y b", "a, b y c". */
export function joinWords(words: string[]): string {
  if (words.length === 0) return "";
  if (words.length === 1) return words[0];
  return `${words.slice(0, -1).join(", ")} y ${words[words.length - 1]}`;
}

/** Avisos de pronunciación: una frase por categoría con errores (sin errores → []). */
export function feedbackHints(breakdown: PronunciationBreakdown): string[] {
  const hints: string[] = [];
  if (breakdown.missing.length > 0) {
    hints.push(`Te faltó: ${joinWords(breakdown.missing)}`);
  }
  if (breakdown.substituted.length > 0) {
    const subs = breakdown.substituted.map((s) => `${s.expected} → ${s.heard}`);
    hints.push(`Sustituiste: ${subs.join(", ")}`);
  }
  if (breakdown.extra.length > 0) {
    hints.push(`Añadiste de más: ${joinWords(breakdown.extra)}`);
  }
  return hints;
}

/** Resumen de aciertos: "4 de 5 palabras correctas". */
export function wordsCorrectLabel(breakdown: PronunciationBreakdown): string {
  return `${breakdown.correct.length} de ${breakdown.total} palabras correctas`;
}
