import type { Bucket, LearningEventType, PronunciationLevel } from "../types/api";

/** Redondea una puntuación a texto, p. ej. 95 → "95"; `null` → "—". */
export function formatScore(value: number | null): string {
  return value === null ? "—" : String(Math.round(value));
}

/** Formatea una media con hasta un decimal, omitiendo el ".0" innecesario. */
export function formatAverage(value: number | null): string {
  if (value === null) return "—";
  const rounded = Math.round(value * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

/** Traduce el nivel de pronunciación a una etiqueta legible; `null` → "—". */
export function pronunciationLevelLabel(level: PronunciationLevel | null): string {
  switch (level) {
    case "good":
      return "Good";
    case "fair":
      return "Fair";
    case "needs_practice":
      return "Needs practice";
    case null:
      return "—";
  }
}

export function bucketLabel(bucket: Bucket): string {
  switch (bucket) {
    case "day":
      return "Day";
    case "week":
      return "Week";
    case "month":
      return "Month";
  }
}

export function eventLabel(type: LearningEventType): string {
  switch (type) {
    case "message":
      return "Message";
    case "exercise":
      return "Exercise";
    case "correction":
      return "Correction";
    case "pronunciation":
      return "Pronunciation";
    case "conversation":
      return "Conversation";
  }
}
