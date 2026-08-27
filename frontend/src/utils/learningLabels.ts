import type { SessionStep } from "../types/api";

// Etiquetas de contenido pedagógico en inglés (el idioma de inmersión durante
// el aprendizaje). La interfaz (chrome) se traduce aparte vía `utils/i18n.ts`.
export const SKILL_LABELS: Record<string, string> = {
  vocabulary: "Vocabulary",
  grammar: "Grammar",
  listening: "Listening",
  speaking: "Speaking",
  reading: "Reading",
  writing: "Writing",
  pronunciation: "Pronunciation",
};

export const KIND_LABELS: Record<string, string> = {
  weakness: "Weakness",
  review: "Review",
  listening: "Listening",
  new: "New",
  easy_wins: "Boost",
};

export const SUBSKILL_LABELS: Record<string, string> = {
  gist: "Main idea",
  detail: "Detail",
  inference: "Inference",
  attitude: "Attitude",
  vocabulary: "Vocabulary",
  numbers: "Numbers",
  speaker_intention: "Intention",
  fast_speech: "Fast speech",
  connected_speech: "Connected speech",
  dictation: "Dictation",
  shadowing: "Shadowing",
  multiple_speakers: "Multiple speakers",
  note_taking: "Note taking",
  prediction: "Prediction",
  sequencing: "Sequencing",
};

export function stepTitle(item: SessionStep): string {
  if (item.kind === "listening" && item.subskill) {
    return SUBSKILL_LABELS[item.subskill] ?? item.subskill;
  }
  if (item.kind === "review") {
    return `Review ${SKILL_LABELS[item.skill ?? ""] ?? item.skill}`;
  }
  if (item.kind === "easy_wins") {
    return `Boost: ${SKILL_LABELS[item.skill ?? ""] ?? item.skill}`;
  }
  return item.title;
}
