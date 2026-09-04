import { getJson } from "./client";
import type { VoicesResponse } from "../types/api";

/**
 * Catálogo de voces TTS instaladas (Configuración → Voces).
 *
 * `user_id` es opcional: con perfil se devuelve su voz seleccionada (`selected`);
 * sin perfil `selected` es la voz por defecto del sistema.
 */
export function getVoices(userId?: string | null): Promise<VoicesResponse> {
  const query = userId ? new URLSearchParams({ user_id: userId }).toString() : "";
  return getJson<VoicesResponse>(`/api/voices${query ? `?${query}` : ""}`);
}
