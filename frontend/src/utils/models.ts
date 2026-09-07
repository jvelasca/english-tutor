/**
 * Resolución del modelo conversacional por defecto (V3.21, V20-05).
 *
 * La fuente única es `config.DEFAULT_MODEL` del backend, que `GET /api/models`
 * expone como `default_model` de forma aditiva. Antes de V3.21 cada flujo
 * conversacional duplicaba la constante (`llama3.1:8b`) en el frontend; ahora
 * todos resuelven el modelo por defecto desde este helper compartido:
 *   1. `default_model` del backend si está instalado y utilizable;
 *   2. si no, el primer modelo de la lista ofertada;
 *   3. si el backend no responde, un fallback local de emergencia.
 *
 * La resolución se cachea tras la primera llamada (la oferta de modelos no
 * cambia a mitad de sesión).
 */
import { getModels } from "../api/chat";

// Fallback de emergencia si el backend no está disponible (NO es la fuente de
// verdad; debe coincidir con `config.DEFAULT_MODEL` del backend).
const FALLBACK_CHAT_MODEL = "llama3.1:8b";

let cachePromise: Promise<string> | null = null;

/** Fallback síncrono de emergencia (backend no disponible). */
export function fallbackChatModel(): string {
  return FALLBACK_CHAT_MODEL;
}

/** Resuelve el modelo por defecto consultando `/api/models` (cacheado). */
export function resolveDefaultChatModel(): Promise<string> {
  if (!cachePromise) {
    cachePromise = getModels()
      .then((data) => {
        const list = data.models ?? [];
        const backendDefault = data.default_model ?? "";
        if (backendDefault && list.includes(backendDefault)) {
          return backendDefault;
        }
        return list[0] ?? FALLBACK_CHAT_MODEL;
      })
      .catch(() => FALLBACK_CHAT_MODEL);
  }
  return cachePromise;
}

/** Solo para tests: reinicia la caché de resolución. */
export function resetDefaultModelCache(): void {
  cachePromise = null;
}
