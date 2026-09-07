import type { Path } from "./hash";
import { joinPath, parseSegments } from "./hash";
import {
  LEGACY_VOCABULARY_ACTIVITY,
  learnActivityPath,
} from "./paths";

/** Identificador de sub-ruta de la tarjeta Listening. */
export const LISTENING_ACTIVITY = "listening";
/** Identificador de sub-ruta de la tarjeta Speaking (práctica oral unificada). */
export const SPEAKING_ACTIVITY = "speaking";
/** Identificador de sub-ruta de la tarjeta Gramática (modo grammar del chat). */
export const GRAMMAR_ACTIVITY = "gramatica";
/** Identificador canónico de la tarjeta Vocabulario (antes ruta "vocabulary"). */
export const VOCABULARY_ACTIVITY = LEGACY_VOCABULARY_ACTIVITY;

/**
 * Las 4 actividades del hub de APRENDER (DISENO-SPEAKING-UNICO, F1): cada una
 * es una sub-ruta canónica bajo `/aprender/<id>`. Pronunciación y Conversación
 * dejaron de ser actividades propias del hub: ahora son modos internos de la
 * página unificada Speaking (`features/speaking/SpeakingRoutesPractice.tsx`).
 */
export const LEARN_ACTIVITY_IDS = [
  LISTENING_ACTIVITY,
  SPEAKING_ACTIVITY,
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

/* ------------------------------------------------------------------ */
/* Modos de la superficie Speaking en la URL (DISENO-SPEAKING-UNICO F4) */
/* ------------------------------------------------------------------ */

/** Modos internos de la superficie oral unificada (F1). */
export type SpeakingMode = "micro" | "accent" | "dialogue";

/** Slug canónico de cada modo bajo `/aprender/speaking` (vocabulario es). */
const SPEAKING_MODE_SLUG: Record<SpeakingMode, string> = {
  micro: "micro",
  accent: "acento",
  dialogue: "dialogo",
};

/**
 * Hojas de APRENDER de profundidad 2 que abren la superficie Speaking: la
 * raíz canónica (speaking = micro-conversación) y las sub-rutas legadas de las
 * antiguas tarjetas orales (pronunciacion → modo Acento; conversar → modo
 * Diálogo guiado). Se resuelven de forma síncrona a su modo para que el
 * deep-link legado abra ya el modo correcto; `legacySpeakingRedirect` además
 * canonicaliza la URL.
 */
const SPEAKING_ROOT_LEAF: Record<string, SpeakingMode> = {
  [SPEAKING_ACTIVITY]: "micro",
  pronunciacion: "accent",
  conversar: "dialogue",
};

/**
 * Hoja aceptada por modo dentro de `/aprender/speaking/<hoja>` (profundidad 3,
 * F4): el slug canónico (acento/dialogo/micro) y su equivalente en inglés,
 * para que los deep links sean tolerantes.
 */
const SPEAKING_MODE_BY_LEAF: Record<string, SpeakingMode> = {
  micro: "micro",
  acento: "accent",
  accent: "accent",
  dialogo: "dialogue",
  dialogue: "dialogue",
};

/**
 * Ruta canónica de la página Speaking con el modo activo, p. ej.:
 * `speakingModePath("accent")` -> "/aprender/speaking/acento". El modo por
 * defecto (micro-conversación) vive en la propia raíz "/aprender/speaking".
 */
export function speakingModePath(mode: SpeakingMode): Path {
  if (mode === "micro") return learnActivityPath(SPEAKING_ACTIVITY);
  return joinPath(
    learnActivityPath(SPEAKING_ACTIVITY),
    SPEAKING_MODE_SLUG[mode],
  );
}

/**
 * Modo oral de Speaking que trae la ruta, o `null` si la ruta no es la página
 * Speaking, una de sus sub-rutas de modo ni una hoja legada que la abra.
 * Profundidad 2: `/aprender/speaking` -> micro, `/aprender/pronunciacion` ->
 * accent y `/aprender/conversar` -> dialogue. Profundidad 3: solo bajo
 * `/aprender/speaking/` con hoja canónica o alias.
 */
export function speakingModeFromPath(path: Path): SpeakingMode | null {
  const segments = parseSegments(path);
  if (segments.length === 0 || segments[0] !== "aprender") return null;
  if (segments.length === 2) return SPEAKING_ROOT_LEAF[segments[1]] ?? null;
  if (segments.length === 3 && segments[1] === SPEAKING_ACTIVITY) {
    return SPEAKING_MODE_BY_LEAF[segments[2]] ?? null;
  }
  return null;
}

/**
 * Devuelve la actividad canónica a la que corresponde una sub-ruta de
 * APRENDER, o `null` si la ruta no es una actividad del hub: el hub
 * `/aprender`, otras raíces y las sub-rutas desconocidas devuelven `null` (el
 * workspace degrada esas sub-rutas desconocidas al hub). Incluye las sub-rutas
 * de modo de Speaking (`/aprender/speaking/acento`, F4) y las hojas legadas de
 * las antiguas tarjetas orales (`pronunciacion`, `conversar`), que abren la
 * superficie Speaking con su modo. Usa `parseSegments`, de modo que tolera
 * trailing slashes y segmentos percent-encoded.
 */
export function learnActivityFromPath(path: Path): LearnActivity | null {
  const segments = parseSegments(path);
  if (segments.length === 0 || segments[0] !== "aprender") return null;
  if (segments.length === 2) {
    const leaf = segments[1];
    if (isLearnActivity(leaf)) return leaf;
    if (SPEAKING_ROOT_LEAF[leaf]) return SPEAKING_ACTIVITY;
    return null;
  }
  if (segments.length === 3 && segments[1] === SPEAKING_ACTIVITY) {
    return speakingModeFromPath(path) ? SPEAKING_ACTIVITY : null;
  }
  return null;
}

/**
 * Destino canónico de las sub-rutas legadas de APRENDER que la unificación
 * oral (F1) convirtió en modos de Speaking, o `null` si la ruta no es una de
 * ellas. F4 (opción a de la decisión abierta nº 2 del documento de diseño):
 * los deep links antiguos se canonicalizan a `/aprender/speaking/acento` y
 * `/aprender/speaking/dialogo` para que refrescos y marcadores usen la URL
 * única; el render ya resuelve el modo de forma síncrona
 * (`speakingModeFromPath`), así que la canonicalización es transparente.
 */
export function legacySpeakingRedirect(path: Path): Path | null {
  const segments = parseSegments(path);
  if (segments.length !== 2 || segments[0] !== "aprender") return null;
  if (segments[1] === "pronunciacion") return speakingModePath("accent");
  if (segments[1] === "conversar") return speakingModePath("dialogue");
  return null;
}
