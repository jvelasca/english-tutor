import { getJson } from "./client";
import type { VoicesResponse } from "../types/api";

/**
 * Catálogo de voces TTS instaladas + descargables (Configuración → Voces).
 *
 * El perfil activo lo resuelve el servidor desde la sesión firmada: con sesión
 * se devuelve su voz seleccionada (`selected`); sin sesión `selected` es la voz
 * por defecto del sistema.
 */
export function getVoices(_userId?: string | null): Promise<VoicesResponse> {
  return getJson<VoicesResponse>("/api/voices");
}

/** Descarga una voz del catálogo curado desde Hugging Face (~60 MB). */
export async function downloadVoice(
  voiceId: string,
): Promise<{ ok: boolean; error?: string }> {
  const res = await fetch("/api/voices/download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ voice_id: voiceId }),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as { ok: boolean };
}
