import type { SessionStep } from "../types/api";

export const SKILL_LABELS: Record<string, string> = {
  vocabulary: "Vocabulario",
  grammar: "Gramática",
  listening: "Listening",
  speaking: "Speaking",
  reading: "Reading",
  writing: "Escritura",
  pronunciation: "Pronunciación",
};

export const KIND_LABELS: Record<string, string> = {
  weakness: "Debilidad",
  review: "Repaso",
  listening: "Listening",
  new: "Nuevo",
  easy_wins: "Refuerzo",
};

export const SUBSKILL_LABELS: Record<string, string> = {
  gist: "Idea general",
  detail: "Detalles",
  inference: "Inferencia",
  attitude: "Actitud",
  vocabulary: "Vocabulario",
  numbers: "Números",
  speaker_intention: "Intención",
  fast_speech: "Habla rápida",
  connected_speech: "Habla conectada",
  dictation: "Dictado",
  shadowing: "Shadowing",
  multiple_speakers: "Varios hablantes",
  note_taking: "Toma de notas",
  prediction: "Predicción",
  sequencing: "Secuenciación",
};

export function stepTitle(item: SessionStep): string {
  if (item.kind === "listening" && item.subskill) {
    return `Escucha: ${SUBSKILL_LABELS[item.subskill] ?? item.subskill}`;
  }
  if (item.kind === "review") {
    return `Repasa ${SKILL_LABELS[item.skill ?? ""] ?? item.skill}`;
  }
  if (item.kind === "easy_wins") {
    return `Refuerzo: ${SKILL_LABELS[item.skill ?? ""] ?? item.skill}`;
  }
  return item.title;
}
