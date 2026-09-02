import type { Path } from "./hash";
import { parseSegments } from "./hash";
import {
  LEGACY_CHAT_ACTIVITY,
  LEGACY_VOCABULARY_ACTIVITY,
} from "./paths";

/** Identificador de sub-ruta de la tarjeta Listening. */
export const LISTENING_ACTIVITY = "listening";
/** Identificador de sub-ruta de la tarjeta Speaking (práctica oral libre). */
export const SPEAKING_ACTIVITY = "speaking";
/** Identificador de sub-ruta de la tarjeta Pronunciación. */
export const PRONUNCIATION_ACTIVITY = "pronunciacion";
/** Identificador de sub-ruta de la tarjeta Gramática (modo grammar del chat). */
export const GRAMMAR_ACTIVITY = "gramatica";
/** Identificador canónico de la tarjeta Conversar (antes ruta raíz "chat"). */
export const CONVERSATION_ACTIVITY = LEGACY_CHAT_ACTIVITY;
/** Identificador canónico de la tarjeta Vocabulario (antes ruta "vocabulary"). */
export const VOCABULARY_ACTIVITY = LEGACY_VOCABULARY_ACTIVITY;

/**
 * Las 6 actividades del hub de APRENDER (decisión D3): cada una es una
 * sub-ruta canónica bajo `/aprender/<id>`.
 */
export const LEARN_ACTIVITY_IDS = [
  LISTENING_ACTIVITY,
  SPEAKING_ACTIVITY,
  PRONUNCIATION_ACTIVITY,
  CONVERSATION_ACTIVITY,
  VOCABULARY_ACTIVITY,
  GRAMMAR_ACTIVITY,
] as const;

export type LearnActivity = (typeof LEARN_ACTIVITY_IDS)[number];

/**
 * Comprueba si un valor desconocido es uno de los identificadores canónicos de
 * actividad de APRENDER.
 */
export function isLearnActivity(value: unknown): value is LearnActivity {
  return (
    typeof value === "string" &&
    (LEARN_ACTIVITY_IDS as readonly string[]).includes(value)
  );
}

/**
 * Devuelve la actividad canónica a la que corresponde una sub-ruta de
 * APRENDER, o `null` si la ruta no es exactamente `/aprender/<actividad>`:
 * el hub `/aprender`, otras raíces y las sub-rutas desconocidas devuelven
 * `null` (el workspace degrada esas sub-rutas desconocidas al hub). Usa
 * `parseSegments`, de modo que tolera trailing slashes y segmentos
 * percent-encoded.
 */
export function learnActivityFromPath(path: Path): LearnActivity | null {
  const segments = parseSegments(path);
  if (segments.length !== 2 || segments[0] !== "aprender") return null;
  const leaf = segments[1];
  return isLearnActivity(leaf) ? leaf : null;
}
