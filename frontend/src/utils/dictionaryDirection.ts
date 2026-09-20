/**
 * Color y opciones de la DIRECCIÓN de la consulta del diccionario (V3.75.8).
 *
 * El sentido de la búsqueda se ve de un vistazo por su color: **azul** para
 * inglés→español y **fucsia** para español→inglés. La pintura vive en
 * `styles/legacy.css` (`.dir-*`) y aquí sólo se compone el NOMBRE de la clase,
 * nunca una interpolación de Tailwind: el escaneo de clases purgaría
 * `text-${dir}` y el color desaparecería sin que ningún test se enterara. Es el
 * mismo contrato que `utils/cefr.ts::levelClass` para la rampa de niveles.
 *
 * Los dos colores son complementarios (máximo contraste entre ellos) y no pisan
 * los colores de estado de la app —verde/ámbar/rojo—, que ya significan otra
 * cosa. Su contraste se mide y se vigila en `scripts/contrast_audit.mjs`.
 */
import type { DictionaryDirection } from "../types/api";

/** Clase base del paso: declara `--dir-ink`, `--dir-fill` y `--dir-edge`. */
export function directionClass(direction: DictionaryDirection): string {
  return direction === "es-en" ? "dir-es-en" : "dir-en-es";
}

/** Las dos direcciones del conmutador, en el orden en que se ofrecen. */
export const DIRECTION_OPTIONS: ReadonlyArray<{
  id: DictionaryDirection;
  labelKey: string;
}> = [
  { id: "en-es", labelKey: "dictionary.lookup.direction.en-es" },
  { id: "es-en", labelKey: "dictionary.lookup.direction.es-en" },
];

/** Clave i18n del rótulo de una dirección (la usa la marca del resultado). */
export function directionLabelKey(direction: DictionaryDirection): string {
  return `dictionary.lookup.direction.${direction}`;
}

/**
 * Ejemplos que se ofrecen cuando todavía no hay búsqueda. Son **contenido**, no
 * interfaz: por eso no pasan por i18n. Cada lista vive en la lengua de la que se
 * busca (en ES→EN se escribe en español, que es lo que el alumno teclea).
 */
export const DIRECTION_EXAMPLES: Record<DictionaryDirection, readonly string[]> = {
  "en-es": ["travel", "book", "water", "family"],
  "es-en": ["casa", "viaje", "comida", "tiempo"],
};
