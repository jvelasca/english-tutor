/**
 * Voces TTS: identidad de una voz, sugerencia de la segunda voz y lectura de un
 * ítem completo (V3.75.5).
 *
 * Hasta V3.75.4 el «...» de la tarjeta de audio solo **mostraba** la voz del
 * perfil y todos los altavoces leían con ella. Como el alumno pidió «oír el
 * mismo ítem con dos acentos», aquí viven las piezas puras que sostienen esa
 * idea: de qué acento es una voz, cuál es la mejor candidata a segunda voz y
 * cómo se compone el texto de una repetición (texto + pregunta + opciones +
 * respuesta correcta, según lo que el perfil haya elegido).
 *
 * Los ids son los de Piper (`en_GB-alan-medium`): el prefijo `en_GB` es la
 * locale y por tanto el acento. Todo se deriva del **id**, no de la etiqueta
 * amigable, porque la etiqueta la traduce el backend y puede cambiar.
 */

import type { VoiceInfo } from "../types/api";

/** Letras de las opciones de un ítem, en orden (A, B, C…). */
const OPTION_LETTERS = "ABCDEFGH";

/** Idioma (ISO-639-1) de una voz Piper: `en_GB-alan-medium` → `en`. */
export function voiceLanguage(voiceId: string): string {
  const prefix = String(voiceId ?? "").split("-")[0] ?? "";
  return prefix.split("_")[0]?.toLowerCase() ?? "";
}

/**
 * Locale de una voz Piper: `en_GB-alan-medium` → `en_GB`; `""` si el id no trae
 * locale (una voz con formato inesperado no debe producir un acento inventado).
 */
export function voiceLocale(voiceId: string): string {
  const prefix = String(voiceId ?? "").split("-")[0] ?? "";
  return /^[a-z]{2}_[A-Za-z]{2}$/.test(prefix) ? prefix : "";
}

/**
 * Clave estable del acento para i18n: `en_GB-alan-medium` → `gb`.
 *
 * Se usa como clave de traducción (`voice.accent.gb`) en vez de devolver el
 * texto, para no meter idioma dentro de una utilidad.
 */
export function voiceAccentKey(voiceId: string): string {
  const locale = voiceLocale(voiceId);
  return locale ? locale.split("_")[1].toLowerCase() : "";
}

/** Nombre derivado del id cuando la etiqueta amigable viene vacía. */
function nameFromId(voiceId: string): string {
  const parts = String(voiceId ?? "").split("-");
  return parts.length > 1 ? parts[1] : (parts[0] ?? "");
}

/**
 * Nombre corto de una voz para listas estrechas: la etiqueta del backend es
 * larga («British English · Alan»), y en un selector de dos columnas solo cabe
 * el nombre propio («Alan»). Si la etiqueta no trae separador se respeta tal
 * cual; si queda vacía se deriva del id.
 */
export function voiceShortLabel(name: string, voiceId = ""): string {
  const raw = String(name ?? "").trim();
  const tail = raw.includes("·") ? (raw.split("·").pop() ?? "") : raw;
  const clean = tail.replace(/\([^)]*\)/g, "").replace(/\s+/g, " ").trim();
  return clean || nameFromId(voiceId);
}

/** Primera letra de cada palabra en mayúscula («alan» → «Alan»). */
function titleCase(text: string): string {
  return text
    .split(" ")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * Etiqueta corta de una voz instalada, lista para el selector.
 *
 * Prefiere el nombre humano del backend («British English · Alan»), pero la
 * etiqueta **derivada** del id («en_GB · alan (medium)») repite el propio id y
 * no sirve en un selector estrecho: en ese caso se compone desde el id.
 */
export function voiceDisplayName(voice: VoiceInfo): string {
  const name = String(voice?.name ?? "").trim();
  if (!name || name.includes("_") || name === voice.id) {
    return titleCase(nameFromId(voice.id).replace(/_/g, " "));
  }
  return voiceShortLabel(name, voice.id);
}

/**
 * Voz candidata a **segunda voz** (B): la misma lengua, con **otra locale** si la
 * hay (`en_US-*` → primera `en_GB-*` y al revés), porque el objetivo es oír el
 * mismo ítem con dos acentos distintos.
 *
 * Si no hay otra locale, cae a cualquier otra voz de la lengua; si solo está la
 * voz principal (o el catálogo está vacío), devuelve `null` — la UI mostrará un
 * solo acento en vez de un botón vacío. Determinista: recorre `installed` en su
 * orden (el backend ya lo devuelve estable, default primero).
 */
export function suggestAltVoice(
  installed: readonly string[],
  primary: string,
): string | null {
  const language = voiceLanguage(primary);
  const others = installed.filter(
    (id) => id !== primary && (!language || voiceLanguage(id) === language),
  );
  if (others.length === 0) return null;
  const locale = voiceLocale(primary);
  const differentLocale = others.find(
    (id) => voiceLocale(id) && voiceLocale(id) !== locale,
  );
  return differentLocale ?? others[0];
}

/** Normaliza un fragmento hablado: espacios colapsados y sin puntuación final. */
function normalizeSpoken(text: string): string {
  return String(text ?? "")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/[.\s]+$/, "");
}

/**
 * Qué se lee al repetir un ítem ya respondido (V3.75.6).
 *
 * Un ítem tiene hasta cuatro piezas: su **texto** (lo que suena: el script del
 * audio), su **pregunta**, sus **opciones** y su **respuesta correcta**. Las tres
 * lecturas que pidió el gerente son combinaciones de esas piezas, y por eso el
 * selector no ofrece «más o menos audio» sino composiciones distintas:
 *
 * - `"item"` (por defecto): texto + pregunta + respuesta correcta. Vuelve a oír
 *   lo que sonó y confirma la clave, **sin** leer los distractores.
 * - `"withOptions"`: texto + pregunta + opciones + respuesta correcta. Es la
 *   lectura más larga: enumera las alternativas y cierra con la buena.
 * - `"correct"`: pregunta + respuesta correcta. La más corta, para quien solo
 *   quiere confirmar la clave; omite también el texto.
 *
 * Es una preferencia del perfil (`replay_scope`), no del ítem: el mismo altavoz
 * suena distinto según lo que el alumno haya elegido en el «...».
 */
export type ReplayScope = "item" | "withOptions" | "correct";

/**
 * Normaliza el valor guardado.
 *
 * `"all"` fue el único valor de la primera versión (V3.75.5/V3.75.6, «enunciado +
 * opciones»): un perfil que lo eligió conserva lo que pidió. Ausente, vacío o
 * desconocido cae a `"item"`, que es el valor por defecto nuevo.
 */
export function replayScope(value: string | null | undefined): ReplayScope {
  if (value === "correct" || value === "withOptions") return value;
  return value === "all" ? "withOptions" : "item";
}

/** Índice realmente utilizable dentro de `options`. */
function hasOption(
  options: readonly string[],
  index: number | null | undefined,
): index is number {
  return index !== null && index !== undefined && index >= 0 && index < options.length;
}

/** Etiqueta con letra de una opción (`2` → `"C: …"`); `""` si no hay texto. */
function labeledOption(
  options: readonly string[],
  index: number | null | undefined,
): string {
  if (!hasOption(options, index)) return "";
  const letter = OPTION_LETTERS[index] ?? "";
  const text = normalizeSpoken(options[index] ?? "");
  return letter && text ? `${letter}: ${text}` : "";
}

export interface ReplayTextOptions {
  /** Qué se lee; `"item"` por defecto. */
  scope?: ReplayScope;
  /** Índice de la respuesta correcta dentro de `options` (lecturas 1 y 2). */
  correctIndex?: number | null;
  /**
   * **Texto** del ítem: lo que suena en el audio (`question.script` en listening).
   * Opcional porque muchas pantallas solo tienen una frase (una palabra del
   * diccionario, una frase modelo): ahí la pregunta **es** el texto, y una pieza
   * ausente no inventa contenido.
   */
  script?: string;
}

/** Respuesta correcta en texto plano (sin letra), o `""` si no hay índice válido. */
function answerText(
  options: readonly string[],
  correctIndex: number | null | undefined,
): string {
  return hasOption(options, correctIndex)
    ? normalizeSpoken(options[correctIndex] ?? "")
    : "";
}

/**
 * Texto de una **repetición** según el alcance elegido por el perfil.
 *
 * Compone las piezas en el orden en que se oyen —texto del ítem, pregunta,
 * opciones, respuesta correcta— y descarta las que no existan. La respuesta se
 * lee **con su letra** solo cuando las opciones se han leído (`"withOptions"`):
 * en las lecturas que no enumeran alternativas, una letra suelta («B») no
 * situaría nada, así que se lee el texto de la respuesta.
 *
 * Dos salvaguardas que evitan repeticiones rotas:
 *
 * - **Nunca vacía:** si el alcance elegido no dejara nada que decir (p. ej.
 *   `"correct"` en un ítem sin opciones ni pregunta), se cae a la lectura
 *   completa antes que dejar al alumno sin altavoz.
 * - **Sin ecos:** un ítem cuyo texto y pregunta son la misma frase (el script
 *   *es* la pregunta, muy común en listening) se lee una sola vez.
 */
export function buildReplayText(
  prompt: string,
  options: readonly string[] = [],
  { scope = "item", correctIndex = null, script = "" }: ReplayTextOptions = {},
): string {
  const text = normalizeSpoken(script);
  const question = normalizeSpoken(prompt);
  const readsOptions = scope === "withOptions";
  const parts: string[] = [];
  const push = (part: string) => {
    if (part && part !== parts[parts.length - 1]) parts.push(part);
  };

  if (scope !== "correct") push(text);
  push(question);
  if (readsOptions) {
    options.forEach((_, index) => push(labeledOption(options, index)));
  }
  push(
    readsOptions
      ? labeledOption(options, correctIndex)
      : answerText(options, correctIndex),
  );

  // Sin nada que decir: la elección del perfil no puede dejar la repetición muda.
  const spoken = parts.length
    ? parts
    : [text, question, ...options.map((_, index) => labeledOption(options, index))];
  const body = spoken.filter(Boolean).join(". ");
  return body ? `${body}.` : "";
}
