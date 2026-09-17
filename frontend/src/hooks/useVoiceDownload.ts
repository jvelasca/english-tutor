import { useSyncExternalStore } from "react";
import { downloadVoice, getVoices } from "../api/voices";
import {
  speak,
  type SpeakOptions,
  type SpeakResult,
  type VoiceLanguage,
} from "../api/voz";
import type { DownloadableVoice, VoicesResponse } from "../types/api";
import { clearDegradedVoice, reportSpeakResult } from "./useDegradedVoice";

/**
 * Consentimiento y descarga de voces (V3.72, eje RD-04).
 *
 * Hasta V3.72 el Traductor **descargaba solo** la voz española (~60 MB desde
 * Hugging Face) en cuanto se montaba la pantalla, sin avisar del tamaño ni
 * pedir permiso: una dependencia oculta que gasta Internet del alumno sin que lo
 * sepa. Ahora, antes del primer TTS de un idioma sin voz instalada, se explica el
 * coste y se pide consentimiento; el progreso es **indeterminado** porque el
 * endpoint de descarga es síncrono y bloqueante (no hay porcentaje que mostrar).
 *
 * El estado vive en un store de módulo (no en un contexto React) porque `speak()`
 * se invoca desde componentes y hooks sin relación jerárquica: así el diálogo es
 * **uno solo** para toda la app aunque se disparen varias reproducciones.
 */
export type VoiceDownloadStatus = "ask" | "downloading" | "error";

export interface VoiceDownloadRequest {
  language: VoiceLanguage;
  voice: DownloadableVoice;
  status: VoiceDownloadStatus;
  /** Detalle del fallo (solo con `status === "error"`). */
  error?: string;
}

let request: VoiceDownloadRequest | null = null;
let decide: ((accepted: boolean) => void) | null = null;
const listeners = new Set<() => void>();

/** Idiomas ya resueltos en esta sesión (instalada, rechazada o sin candidata). */
const settled = new Set<VoiceLanguage>();
/** Preguntas en curso: dos TTS simultáneos no abren dos diálogos. */
const asking = new Map<VoiceLanguage, Promise<void>>();

function emit(): void {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Resuelve la decisión **una sola vez** (la promesa no debe colgarse). */
function settle(accepted: boolean): void {
  const resolve = decide;
  decide = null;
  resolve?.(accepted);
}

/** Petición de descarga pendiente, para consumir fuera de React (tests). */
export function getVoiceDownloadRequest(): VoiceDownloadRequest | null {
  return request;
}

export function useVoiceDownloadRequest(): VoiceDownloadRequest | null {
  return useSyncExternalStore(
    subscribe,
    () => request,
    () => null,
  );
}

/** Voz descargable del catálogo curado para un idioma, si existe. */
function downloadableFor(
  data: VoicesResponse | null | undefined,
  language: VoiceLanguage,
): DownloadableVoice | null {
  const options = data?.downloadable ?? [];
  const preferred = data?.defaults?.[language];
  return (
    options.find((voice) => voice.id === preferred) ??
    options.find((voice) => voice.id.startsWith(`${language}_`)) ??
    null
  );
}

/** Abre el diálogo de consentimiento y resuelve con la decisión del alumno. */
export function requestVoiceDownload(
  language: VoiceLanguage,
  voice: DownloadableVoice,
): Promise<boolean> {
  if (request) return Promise.resolve(false); // ya hay una decisión en curso
  request = { language, voice, status: "ask" };
  emit();
  return new Promise<boolean>((resolve) => {
    decide = resolve;
  });
}

/** «Descargar y escuchar»: descarga bloqueante con progreso indeterminado. */
export async function confirmVoiceDownload(): Promise<void> {
  const pending = request;
  if (!pending || pending.status === "downloading") return;
  request = { language: pending.language, voice: pending.voice, status: "downloading" };
  emit();
  try {
    await downloadVoice(pending.voice.id);
    request = null;
    emit();
    settle(true);
  } catch (e) {
    request = {
      language: pending.language,
      voice: pending.voice,
      status: "error",
      error: (e as Error).message,
    };
    emit();
    // El TTS no se queda esperando: se reproduce degradado y el diálogo ofrece
    // reintentar sin volver a preguntar.
    settle(false);
  }
}

/** «Ahora no» / cerrar: no se descarga y no se vuelve a preguntar en la sesión. */
export function dismissVoiceDownload(): void {
  if (!request) return;
  request = null;
  emit();
  settle(false);
}

/**
 * Deja el idioma «resuelto» si ya tiene voz instalada o si no hay nada que
 * ofrecer; si falta, pide consentimiento una sola vez por sesión. **Nunca
 * lanza**: un catálogo caído no puede impedir que se reproduzca el audio.
 */
export async function ensureVoiceForTts(
  language: VoiceLanguage,
  userId?: string | null,
): Promise<void> {
  if (settled.has(language)) return;
  const inFlight = asking.get(language);
  if (inFlight) return inFlight;

  const task = (async () => {
    try {
      const data = await getVoices(userId);
      const installed = data?.voices ?? [];
      if (installed.some((voice) => voice.id.startsWith(`${language}_`))) {
        settled.add(language);
        return;
      }
      const candidate = downloadableFor(data, language);
      if (!candidate) {
        settled.add(language); // nada descargable: no se molesta al alumno
        return;
      }
      await requestVoiceDownload(language, candidate);
      // Se pregunta una sola vez por sesión: si dice «ahora no», el idioma queda
      // resuelto igual (la descarga manual sigue en Ajustes → Voces).
      settled.add(language);
    } catch {
      settled.add(language); // catálogo no disponible: fail-open
    } finally {
      asking.delete(language);
    }
  })();
  asking.set(language, task);
  return task;
}

/** Olvida lo decidido en esta sesión sobre voces (cierre de sesión, tests). */
export function resetVoiceSession(): void {
  settled.clear();
  asking.clear();
  request = null;
  decide = null;
  clearDegradedVoice();
  emit();
}

/**
 * `speak()` con el flujo completo de voz: consentimiento/descarga si falta la
 * voz del idioma, y aviso global si el backend acaba degradando. Es el punto de
 * entrada que deben usar los componentes; `speak()` queda como capa HTTP.
 */
export async function speakWithVoice(
  text: string,
  userId?: string | null,
  language: VoiceLanguage = "en",
  options?: SpeakOptions,
): Promise<SpeakResult> {
  await ensureVoiceForTts(language, userId);
  // Sin opciones se conserva la llamada histórica de 3 argumentos (los mocks de
  // otros tests la verifican así).
  const result = options
    ? await speak(text, userId, language, options)
    : await speak(text, userId, language);
  reportSpeakResult(result, language);
  return result;
}
