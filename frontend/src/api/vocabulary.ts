import { getJson } from "./client";
import type { Lexicon } from "../types/api";

/** Léxico personal del alumno (V2.3): resumen + ítems con estado y recall. */
export function getLexicon(userId: string): Promise<Lexicon> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<Lexicon>(`/api/vocabulary/lexicon?${query}`);
}
