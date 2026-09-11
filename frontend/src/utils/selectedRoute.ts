/**
 * V3.48.1: ruta CEFR seleccionada en las pantallas de práctica (APRENDER).
 *
 * A diferencia de una sesión focalizada (`session`), la selección es una
 * preferencia persistente: el nivel elegido gobierna de qué ruta se sirven las
 * preguntas hasta que el alumno cambie de ruta o vuelva al modo automático.
 *
 * Se persiste en dos capas, mismo patrón doble que la vista del diccionario
 * (`utils/dictionaryView.ts`):
 *
 * 1. `localStorage` — arranque inmediato y sin parpadeo (también sin perfil);
 * 2. settings del backend por usuario (`selected_route_level`) — la preferencia
 *    viaja con el perfil, así que al cambiar de alumno se hidrata.
 *
 * `null` significa «Auto»: el nivel lo decide el motor (nivel recomendado).
 */

export const SELECTED_ROUTE_LEVELS = [
  "A1",
  "A2",
  "B1",
  "B2",
  "C1",
  "C2",
] as const;

export type SelectedRouteLevel = (typeof SELECTED_ROUTE_LEVELS)[number];

export const SELECTED_ROUTE_STORAGE_KEY = "english-tutor.selected-route";

/** Clave de settings del backend que guarda la ruta elegida. */
export const SELECTED_ROUTE_SETTING_KEY = "selected_route_level";

export function isSelectedRouteLevel(
  value: unknown,
): value is SelectedRouteLevel {
  return (
    typeof value === "string" &&
    (SELECTED_ROUTE_LEVELS as readonly string[]).includes(value)
  );
}

/**
 * Ruta válida a partir del valor persistido en `localStorage`.
 *
 * Tolerante: acepta tanto la cadena simple (`B1`) como su JSON (`"B1"`) y cae a
 * `null` («Auto») ante cualquier cosa rara o un valor ausente.
 */
export function parseSelectedRouteLevel(
  raw: string | null | undefined,
): SelectedRouteLevel | null {
  if (!raw) return null;
  if (isSelectedRouteLevel(raw)) return raw;
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (isSelectedRouteLevel(parsed)) return parsed;
  } catch {
    /* no era JSON: ya se probó el valor plano */
  }
  return null;
}

/** Ruta activa desde un mapa de settings del backend, o `null` si no consta. */
export function selectedRouteFromSettings(
  settings: Record<string, string> | undefined,
): SelectedRouteLevel | null {
  const value = settings?.[SELECTED_ROUTE_SETTING_KEY];
  return isSelectedRouteLevel(value) ? value : null;
}

/**
 * Campo de settings con el que se persiste la ruta activa. `null` («Auto») se
 * guarda como cadena vacía: la API de settings solo escribe claves, no las
 * borra, y la lectura trata cualquier valor inválido como «Auto».
 */
export function selectedRouteToSettings(
  level: SelectedRouteLevel | null,
): Record<string, string> {
  return { [SELECTED_ROUTE_SETTING_KEY]: level ?? "" };
}

/**
 * Prioridad de nivel para servir preguntas: sesión activa > ruta seleccionada >
 * nivel recomendado por el motor. `null` deja que el backend decida (Auto).
 */
export function resolveRouteLevel(
  sessionLevel: string | null | undefined,
  selectedLevel: SelectedRouteLevel | null,
  recommendedLevel: string | null | undefined,
): string | null {
  return sessionLevel ?? selectedLevel ?? recommendedLevel ?? null;
}
