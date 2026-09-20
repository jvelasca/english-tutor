/**
 * Niveles CEFR: etiqueta, orden canónico y **rampa de color** (V3.75.4).
 *
 * Hasta V3.75.3 el color del nivel se resolvía en **tres tramos**
 * (`cefrTone` → `basic|intermediate|advanced`), así que A1 y A2 se veían
 * idénticos, igual que B1/B2 y C1/C2. Como el alumno pidió «que el nivel se
 * visualice muy fácilmente» y que la rampa sea elegible, cada uno de los siete
 * pasos recibe ahora su propio color de fondo:
 *
 * - `cefrLevelKey` traduce la etiqueta del backend (`"Pre-A1"`…`"C2"`, o `"—"`
 *   cuando no hay dato) a una clave estable;
 * - `levelClass` devuelve la clase **estática** que lleva los tokens
 *   (`--level-<clave>-fg/bg/border`), declarada en `styles/legacy.css` para los
 *   tres esquemas (`data-levels`) y los dos temas. Se usan clases y no estilos en
 *   línea porque el esquema es un atributo del `<html>`: cambiarlo debe repintar
 *   todo sin que ningún componente se vuelva a renderizar.
 * - `bandToLevelKey` cubre las posiciones **numéricas** (escala 0–6 de
 *   `estimated_numeric`), que es como llega la posición cuando no hay etiqueta
 *   (la escalera de Trayectoria, los anillos de Listening).
 */

/** Los siete pasos del MCER, en orden, más el cajón de «sin dato». */
export type LevelKey =
  | "pre-a1"
  | "a1"
  | "a2"
  | "b1"
  | "b2"
  | "c1"
  | "c2"
  | "unknown";

/**
 * Los siete pasos **en orden de dificultad**. Es el orden que usan las vistas
 * previas de Ajustes y el que recorre la rampa de color; `"unknown"` queda fuera
 * a propósito, porque no es un nivel sino la ausencia de uno.
 */
export const LEVEL_KEYS: readonly LevelKey[] = [
  "pre-a1",
  "a1",
  "a2",
  "b1",
  "b2",
  "c1",
  "c2",
];

/** Claves por índice de la escala numérica 0–6 (0 = Pre-A1, 6 = C2). */
const NUMERIC_KEYS: readonly LevelKey[] = LEVEL_KEYS;

/**
 * Clave de nivel a partir de la etiqueta del backend. Tolerante a propósito:
 * acepta `"Pre-A1"`, `"pre a1"` o `"PREA1"` y trata `"—"`, `""` o un valor
 * inesperado como «sin dato» en vez de inventar un nivel. También acepta un
 * **número** (escala 0–6) y lo delega en `bandToLevelKey`, porque la posición
 * puede llegar como estimación continua (`overall_ability`) y no como etiqueta.
 */
export function cefrLevelKey(level: string | number): LevelKey {
  if (typeof level === "number") return bandToLevelKey(level);
  const normalized = String(level ?? "")
    .toLowerCase()
    .replace(/[\s_-]/g, "");
  switch (normalized) {
    case "prea1":
      return "pre-a1";
    case "a1":
      return "a1";
    case "a2":
      return "a2";
    case "b1":
      return "b1";
    case "b2":
      return "b2";
    case "c1":
      return "c1";
    case "c2":
      return "c2";
    default:
      return "unknown";
  }
}

/** Clase estática con los tokens de la rampa para un nivel (`"lv-a2"`). */
export function levelClass(level: string | number): string {
  return `lv-${cefrLevelKey(level)}`;
}

/**
 * Clave de nivel para una posición **numérica** (escala 0–6). Redondea al paso
 * más cercano y recorta fuera de rango, porque el número viene de una estimación
 * continua y aquí solo hace falta el escalón para elegir color.
 */
export function bandToLevelKey(numeric: number): LevelKey {
  if (!Number.isFinite(numeric)) return "unknown";
  const step = Math.min(6, Math.max(0, Math.round(numeric)));
  return NUMERIC_KEYS[step];
}

export function cefrLabel(level: string): string {
  switch (level) {
    case "Pre-A1":
      return "Pre-beginner";
    case "A1":
      return "Beginner";
    case "A2":
      return "Elementary";
    case "B1":
      return "Intermediate";
    case "B2":
      return "Upper-intermediate";
    case "C1":
      return "Advanced";
    case "C2":
      return "Mastery";
    default:
      return level;
  }
}

export function bandLabel(skill: string): string {
  switch (skill) {
    case "vocabulary":
      return "Vocabulary";
    case "grammar":
      return "Grammar";
    case "pronunciation":
      return "Pronunciation";
    case "listening":
      return "Listening";
    case "speaking":
      return "Speaking";
    case "reading":
      return "Reading";
    case "writing":
      return "Writing";
    default:
      return skill;
  }
}
