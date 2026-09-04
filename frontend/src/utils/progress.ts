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

/** Traduce el bucket de agrupación ("day" → "Day"/"Día"). */
export function bucketLabel(
  bucket: Bucket,
  t: (key: string) => string,
): string {
  switch (bucket) {
    case "day":
      return t("progress.bucket.day");
    case "week":
      return t("progress.bucket.week");
    case "month":
      return t("progress.bucket.month");
  }
}

/** Traduce el tipo de evento de actividad ("message" → "Message"/"Mensaje"). */
export function eventLabel(
  type: LearningEventType,
  t: (key: string) => string,
): string {
  switch (type) {
    case "message":
      return t("progress.event.message");
    case "exercise":
      return t("progress.event.exercise");
    case "correction":
      return t("progress.event.correction");
    case "pronunciation":
      return t("progress.event.pronunciation");
    case "conversation":
      return t("progress.event.conversation");
  }
}
