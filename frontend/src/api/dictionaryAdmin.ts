import { deleteJson, getJson, putJson } from "./client";
import { getAdminPin } from "./audioLibrary";

/**
 * Curación manual del diccionario (V3.95.0).
 *
 * Estas rutas son de ADMINISTRACIÓN: van con la misma cabecera `X-Admin-Pin` que
 * la biblioteca de audio y el backend exige, además, que la petición venga del
 * propio equipo (`require_admin_local`). Una corrección MANDA sobre el glosario
 * curado, los packs temáticos y la caché del modelo, para todos los usuarios.
 */
function adminHeaders(): Record<string, string> {
  const pin = getAdminPin();
  return pin ? { "X-Admin-Pin": pin } : {};
}

export type DictionaryDirection = "en-es" | "es-en";

export interface DictionaryCuratedPayload {
  direction: DictionaryDirection;
  word: string;
  translation: string;
  pos?: string;
  definition?: string;
  situation?: string;
  note?: string;
}

export interface DictionaryCuratedEntry {
  direction: string;
  word: string;
  translation: string;
  pos: string;
  definition: string;
  situation: string;
  note: string;
  created_at: string;
  updated_at: string;
}

export function listCuratedDictionary(
  direction?: DictionaryDirection,
): Promise<{ items: DictionaryCuratedEntry[] }> {
  const query = direction ? `?direction=${encodeURIComponent(direction)}` : "";
  return getJson<{ items: DictionaryCuratedEntry[] }>(
    `/api/admin/dictionary/curated${query}`,
    adminHeaders(),
  );
}

export function saveCuratedDictionary(
  payload: DictionaryCuratedPayload,
): Promise<DictionaryCuratedEntry> {
  return putJson<DictionaryCuratedEntry>(
    "/api/admin/dictionary/curated",
    payload,
    adminHeaders(),
  );
}

export function deleteCuratedDictionary(
  direction: DictionaryDirection,
  word: string,
): Promise<{ deleted: boolean; direction: string; word: string }> {
  return deleteJson<{ deleted: boolean; direction: string; word: string }>(
    `/api/admin/dictionary/curated/${direction}/${encodeURIComponent(word)}`,
    adminHeaders(),
  );
}
