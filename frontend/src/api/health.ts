import { getJson } from "./client";

export interface HealthInfo {
  status: string;
  service: string;
  version: string;
}

export interface DependencyStatus {
  api: string;
  database: string;
  ollama: string;
  stt: string;
  tts: string;
  audio_library: string;
}

export function getHealth(): Promise<HealthInfo> {
  return getJson<HealthInfo>("/api/health");
}

export function getDependencies(): Promise<DependencyStatus> {
  return getJson<DependencyStatus>("/api/health/dependencies");
}

/**
 * Dependencias que deciden si la app es UTILIZABLE (V3.71, eje RC).
 *
 * Son exactamente las que gatean `/api/health/ready` en el backend. La
 * biblioteca de audio queda fuera a propósito: es opcional por diseño (el corpus
 * usa TTS; ver `docs/audit/PARKED.md`), así que no debe teñir el estado global.
 */
export const CORE_DEPENDENCIES = ["database", "ollama", "stt", "tts"] as const;

export type ConnectionState = "connected" | "degraded" | "disconnected";

/**
 * Resume el estado REAL de la app (V3.71, eje RC).
 *
 * Antes el indicador de cabecera preguntaba a `/api/health`, que responde 200
 * siempre que el proceso esté vivo: con Ollama o la base de datos caídos seguía
 * diciendo «Conectado». Aquí «conectado» significa «la app puede trabajar».
 */
export function connectionState(deps: DependencyStatus | null): ConnectionState {
  if (!deps) return "disconnected";
  const healthy = CORE_DEPENDENCIES.every(
    (key) => deps[key] === "ok" || deps[key] === "ready",
  );
  return healthy ? "connected" : "degraded";
}
