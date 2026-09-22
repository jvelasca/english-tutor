/**
 * Vista activa del diccionario. V3.39 la creó con dos pestañas («Personal» /
 * «Consultar»); V3.78.0 la reorganiza en TRES modos, en el orden en que se usan:
 * consultar una palabra, ver el propio léxico y estudiarlo con tarjetas.
 *
 * La elección se persiste en dos capas, mismo patrón doble que la apariencia
 * (`utils/appearance.ts`):
 *
 * 1. `localStorage` — arranque inmediato y sin parpadeo (también sin perfil);
 * 2. settings del backend por usuario (`dictionary_view`) — la preferencia
 *    viaja con el perfil, así que al cambiar de alumno se hidrata.
 *
 * El valor es una cadena simple (`"lookup"` | `"personal"` | `"flashcards"`). Se
 * valida al leer y se cae al defecto si falta o es inválido.
 *
 * V3.78.0 cambia el DEFECTO a `"lookup"`: el modo que se abre primero es el que
 * responde a la pregunta con la que se entra a un diccionario («¿qué significa
 * esta palabra?»). Un valor persistido de una versión anterior sigue siendo
 * válido y manda sobre el defecto, así que nadie pierde su pestaña.
 */

export type DictionaryView = "lookup" | "personal" | "flashcards";

export const DEFAULT_DICTIONARY_VIEW: DictionaryView = "lookup";

export const DICTIONARY_VIEW_STORAGE_KEY = "english-tutor.dictionary-view";

/** Clave de settings del backend que guarda la última vista del diccionario. */
export const DICTIONARY_VIEW_SETTING_KEY = "dictionary_view";

/**
 * V3.78.0: modos que admite el diccionario INCRUSTADO en la práctica de rutas.
 *
 * El panel no puede hospedar el modo Flashcards: una sesión de estudio tiene su
 * propio recorrido (cola, límites del día, resumen) y no cabe dentro de una
 * pantalla de práctica. Se declara aquí, junto al tipo, para que la restricción
 * sea una sola cosa y no una convención repetida en cada consumidor.
 */
export type PanelDictionaryView = Exclude<DictionaryView, "flashcards">;

export const PANEL_DICTIONARY_VIEWS: readonly PanelDictionaryView[] = [
  "personal",
  "lookup",
];

export function isDictionaryView(value: unknown): value is DictionaryView {
  return value === "lookup" || value === "personal" || value === "flashcards";
}

/**
 * Vista del panel incrustado a partir de un modo del diccionario.
 *
 * El panel NUNCA lee la vista persistida (arranca en el mapa de rutas), pero
 * cuando escribe lo hace en el mismo ajuste compartido que la pantalla dedicada:
 * esta función es la frontera donde un modo de tres se proyecta en uno de dos,
 * y evita que el panel pueda dejar persistido un modo que no sabe mostrar.
 */
export function toPanelView(view: DictionaryView): PanelDictionaryView {
  return view === "flashcards" ? "personal" : view;
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
