import { useSyncExternalStore } from "react";
import type { SpeakResult, VoiceLanguage } from "../api/voz";

/**
 * Aviso de voz degradada (V3.72, eje RD-04).
 *
 * El backend declara desde V3.71 la voz realmente usada y si hubo degradación
 * (`X-TTS-Voice`/`X-TTS-Degraded`) —p. ej. leer español con la voz inglesa—,
 * pero la UI las tiraba: la degradación seguía siendo invisible para el alumno.
 *
 * El aviso es **global y no bloqueante**: un único `role="status"` en el shell
 * (no uno por cada uno de los ~15 puntos que reproducen audio) que se descarta
 * solo o al pulsar su botón. Se guarda en un store de módulo porque `speak()` se
 * llama desde componentes sin relación entre sí (botones, hooks de voz, bucles).
 */
export interface DegradedVoiceState {
  /** Voz realmente usada por el backend. */
  voice: string;
  /** Idioma que se pidió (para poder decir «no hay voz de X instalada»). */
  language: VoiceLanguage;
}

let current: DegradedVoiceState | null = null;
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Declara que el último TTS usó una voz de otro idioma. */
export function reportDegradedVoice(
  voice: string,
  language: VoiceLanguage,
): void {
  if (current?.voice === voice && current.language === language) return;
  current = { voice, language };
  emit();
}

/** Descarta el aviso (botón del propio aviso, o al cambiar de contexto). */
export function clearDegradedVoice(): void {
  if (current === null) return;
  current = null;
  emit();
}

/** Estado actual, para consumir fuera de React (tests). */
export function getDegradedVoice(): DegradedVoiceState | null {
  return current;
}

/** Registra el resultado de un `speak()` si vino degradado (fail-open). */
export function reportSpeakResult(
  result: SpeakResult | undefined | null,
  language: VoiceLanguage,
): void {
  if (result?.degraded) reportDegradedVoice(result.voice, language);
}

export function useDegradedVoice(): DegradedVoiceState | null {
  return useSyncExternalStore(
    subscribe,
    () => current,
    () => null,
  );
}
