/**
 * V3.39: vista activa del diccionario (pestañas «Personal» / «Consultar»).
 *
 * La elección se persiste en dos capas, mismo patrón doble que la apariencia
 * (`utils/appearance.ts`):
 *
 * 1. `localStorage` — arranque inmediato y sin parpadeo (también sin perfil);
 * 2. settings del backend por usuario (`dictionary_view`) — la preferencia
 *    viaja con el perfil, así que al cambiar de alumno se hidrata.
 *
 * El valor es una cadena simple (`"personal"` | `"lookup"`). Se valida al leer
 * y se cae a `"personal"` si falta o es inválido.
 */

export type DictionaryView = "personal" | "lookup";

export const DEFAULT_DICTIONARY_VIEW: DictionaryView = "personal";

export const DICTIONARY_VIEW_STORAGE_KEY = "english-tutor.dictionary-view";

/** Clave de settings del backend que guarda la última vista del diccionario. */
export const DICTIONARY_VIEW_SETTING_KEY = "dictionary_view";

export function isDictionaryView(value: unknown): value is DictionaryView {
  return value === "personal" || value === "lookup";
}

/**
 * Vista válida a partir del valor persistido en `localStorage`.
 *
 * Tolerante: acepta tanto la cadena simple (`lookup`) como su JSON (`"lookup"`)
 * y cae al valor por defecto ante cualquier cosa rara.
 */
export function parseDictionaryView(
  raw: string | null | undefined,
): DictionaryView {
  if (!raw) return DEFAULT_DICTIONARY_VIEW;
  if (isDictionaryView(raw)) return raw;
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (isDictionaryView(parsed)) return parsed;
  } catch {
    /* no era JSON: ya se probó el valor plano */
  }
  return DEFAULT_DICTIONARY_VIEW;
}

/** Vista activa desde un mapa de settings del backend, o `null` si no consta. */
export function dictionaryViewFromSettings(
  settings: Record<string, string> | undefined,
): DictionaryView | null {
  const value = settings?.[DICTIONARY_VIEW_SETTING_KEY];
  return isDictionaryView(value) ? value : null;
}

/** Campo de settings con el que se persiste la vista activa del diccionario. */
export function dictionaryViewToSettings(
  view: DictionaryView,
): Record<string, string> {
  return { [DICTIONARY_VIEW_SETTING_KEY]: view };
}
