import type { SessionStep } from "../types/api";
import type { Translate } from "./fluency";

// Etiquetas de contenido pedagógico en inglés (el idioma de inmersión durante
// el aprendizaje): los nombres de destreza quedan en inglés también en la UI en
// español (decisión V3.6.1). La interfaz (chrome) se traduce aparte vía
// `utils/i18n.ts` con las claves `today.kind.*` y `today.kindPhrase.*`.
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

/** Clave i18n de la píldora de tipo de paso ("review" → "today.kind.review"). */
export function kindKey(kind: string): string | null {
  switch (kind) {
    case "weakness":
      return "today.kind.weakness";
    case "review":
      return "today.kind.review";
    case "listening":
      return "skill.listening";
    case "new":
      return "today.kind.new";
    case "easy_wins":
      return "today.kind.easy_wins";
    default:
      return null;
  }
}

/** Nombre de destreza en inglés (idioma de inmersión) para frases del plan. */
function skillLabel(item: SessionStep): string {
  const skill = item.skill ?? "";
  return SKILL_LABELS[skill] ?? skill;
}

/** Título legible de un paso: el verbo/tipo se traduce, la destreza no. */
export function stepTitle(item: SessionStep, t: Translate): string {
  if (item.kind === "listening" && item.subskill) {
    return SUBSKILL_LABELS[item.subskill] ?? item.subskill;
  }
  if (item.kind === "review") {
    return `${t("today.kindPhrase.review")} ${skillLabel(item)}`;
  }
  if (item.kind === "easy_wins") {
    return `${t("today.kindPhrase.easy_wins")}: ${skillLabel(item)}`;
  }
  return item.title;
}
