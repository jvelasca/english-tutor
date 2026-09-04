import type { PronunciationBreakdown } from "../types/api";
import type { Translate } from "./fluency";

/** Une palabras en inglés: "a", "a and b", "a, b and c". */
export function joinWords(words: string[]): string {
  if (words.length === 0) return "";
  if (words.length === 1) return words[0];
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

/** Avisos de pronunciación: una frase por categoría con errores (sin errores → []). */
export function feedbackHints(
  breakdown: PronunciationBreakdown,
  t: Translate,
): string[] {
  const hints: string[] = [];
  if (breakdown.missing.length > 0) {
    hints.push(
      t("pron.hint.missing").replace("{words}", joinWords(breakdown.missing)),
    );
  }
  if (breakdown.substituted.length > 0) {
    const subs = breakdown.substituted.map((s) => `${s.expected} → ${s.heard}`);
    hints.push(
      t("pron.hint.substituted").replace("{items}", subs.join(", ")),
    );
  }
  if (breakdown.extra.length > 0) {
    hints.push(
      t("pron.hint.extra").replace("{words}", joinWords(breakdown.extra)),
    );
  }
  return hints;
}

/** Resumen de aciertos: "4 of 5 words correct". */
export function wordsCorrectLabel(
  breakdown: PronunciationBreakdown,
  t: Translate,
): string {
  return t("pron.wordsCorrect")
    .replace("{correct}", String(breakdown.correct.length))
    .replace("{total}", String(breakdown.total));
}
