/** Idioma (ISO-639-1) admitido por los endpoints de voz usados por la app. */
export type VoiceLanguage = "en" | "es";

/**
 * Resultado de `speak()`. V3.72 (eje RD-04): el backend ya declaraba la voz
 * usada y la degradación en cabeceras (`X-TTS-Voice`/`X-TTS-Degraded`), pero el
 * cliente las tiraba: la UI no podía decir «esto suena con otra voz».
 */
export interface SpeakResult {
  /** Voz realmente usada por el backend; `""` si no la declaró. */
  voice: string;
  /** `true` si el texto se sirvió con una voz de OTRO idioma. */
  degraded: boolean;
}

/** Espera máxima (ms) a que el backend devuelva el audio antes de abortar. */
export const TTS_TIMEOUT_MS = 30_000;

/** Opciones de `speak()` (V3.72: cancelación y timeout configurables). */
export interface SpeakOptions {
  /** Signal externo (p. ej. el desmontaje de un componente o el fin de turno). */
  signal?: AbortSignal;
  /** Espera máxima antes de abortar; `TTS_TIMEOUT_MS` por defecto. */
  timeoutMs?: number;
  /**
   * V3.75.5 (dos acentos): id de la voz Piper con la que leer el texto.
   *
   * Es una petición, no una orden: el backend la acepta solo si está instalada y
   * es del idioma pedido, y declara en `X-TTS-Voice` lo que de verdad sonó. Sin
   * `voice` no se envía nada en el cuerpo (contrato histórico intacto).
   */
  voice?: string;
}

/**
 * Transcribe un audio con faster-whisper. `language` fija el idioma esperado
 * (`"en"` por defecto, el histórico para dictado de inglés; `"es"` lo usa el
 * Traductor al escuchar español).
 */
export async function transcribe(
  blob: Blob,
  language: VoiceLanguage = "en",
): Promise<string> {
  const form = new FormData();
  form.append("file", blob, "audio.webm");
  form.append("language", language);

  const res = await fetch("/api/transcribe", { method: "POST", body: form });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  const data = (await res.json()) as { text: string };
  return data.text;
}

/**
 * Locución en curso (V3.75.6).
 *
 * Hasta V3.75.5 `speak()` creaba un `new Audio()` y lo abandonaba a su suerte:
 * no había forma de **parar** una lectura larga (el alumno pidió un STOP para la
 * repetición del ítem completo). Se guarda la reproducción viva en un registro de
 * módulo —igual que el store de voces— porque el botón de parar está en otro
 * componente que el que la lanzó.
 */
interface Speaking {
  controller: AbortController;
  /** `true` si el alumno ha cortado: la espera resuelve y nada suena. */
  stopped: boolean;
  audio: HTMLAudioElement | null;
  /** Resuelve la espera de `playBlob` al cortar (parar no es un error). */
  interrupt: (() => void) | null;
}

let speaking: Speaking | null = null;

/** ¿Hay una locución sonando (o sintetizándose) ahora mismo? */
export function isSpeaking(): boolean {
  return speaking !== null;
}

/**
 * Corta la locución en curso (STOP). También cancela la síntesis si aún no había
 * llegado el audio: el alumno que pulsa STOP no quiere que suene dos segundos
 * después. La promesa de `speak()` en curso **resuelve** (parar no es un fallo),
 * así el componente que la espera apaga su spinner sin tratar el caso como error.
 */
export function stopSpeaking(): void {
  const active = speaking;
  if (!active) return;
  speaking = null;
  active.stopped = true;
  active.controller.abort();
  active.audio?.pause();
  active.interrupt?.();
}

/** Reproduce un blob de audio y resuelve cuando termina, falla o se corta. */
function playBlob(blob: Blob, playback: Speaking): Promise<void> {
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  playback.audio = audio;
  return new Promise<void>((resolve, reject) => {
    let settled = false;
    const cleanup = () => {
      URL.revokeObjectURL(url);
      if (playback.audio === audio) playback.audio = null;
      playback.interrupt = null;
    };
    const finish = () => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve();
    };
    const fail = (error: Error) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error);
    };
    // El STOP puede llegar mientras suena: se resuelve la espera y se corta.
    playback.interrupt = finish;
    audio.onended = finish;
    audio.onerror = () => fail(new Error("No se pudo reproducir el audio"));
    if (playback.stopped) {
      finish();
      return;
    }
    audio.play().catch(fail);
  });
}

/**
 * Sintetiza y reproduce `text` con Piper. `language` elige la voz del idioma
 * destino (`"en"` por defecto); la sesión firmada decide la voz guardada del
 * perfil activo si es de ese idioma (V3.39, Fase 2).
 *
 * V3.72 (RD-04): devuelve `{voice, degraded}` leyendo las cabeceras que el
 * backend ya enviaba y **aborta** de verdad (`AbortController` + timeout) en vez
 * de dejar la promesa colgada para siempre.
 *
 * V3.75.5 (dos acentos): `options.voice` viaja en el cuerpo solo cuando se pide
 * un acento concreto; si no, la petición es byte a byte la de antes.
 *
 * V3.75.6 (STOP): una sola locución a la vez. Empezar otra corta la anterior
 * —antes se solapaban— y `stopSpeaking()` permite parar la que suena.
 */
export async function speak(
  text: string,
  _userId?: string | null,
  language: VoiceLanguage = "en",
  options: SpeakOptions = {},
): Promise<SpeakResult> {
  stopSpeaking();
  const playback: Speaking = {
    controller: new AbortController(),
    stopped: false,
    audio: null,
    interrupt: null,
  };
  speaking = playback;
  try {
    return await synthesize(text, language, options, playback);
  } finally {
    // Corte por STOP (el registro ya se liberó) o salida normal: se limpia igual.
    if (speaking === playback) speaking = null;
  }
}

/**
 * Cuerpo de `speak()`: síntesis con timeout y reproducción interrumpible.
 *
 * Vive aparte para que el registro de la locución se libere en **un solo**
 * `finally` de `speak()`, salga por donde salga (error HTTP, timeout, STOP).
 */
async function synthesize(
  text: string,
  language: VoiceLanguage,
  options: SpeakOptions,
  playback: Speaking,
): Promise<SpeakResult> {
  const timeoutMs = options.timeoutMs ?? TTS_TIMEOUT_MS;
  const controller = playback.controller;
  const abortExternal = () => controller.abort();
  if (options.signal) {
    if (options.signal.aborted) controller.abort();
    else options.signal.addEventListener("abort", abortExternal, { once: true });
  }
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const stopped: SpeakResult = { voice: "", degraded: false };

  let res: Response;
  try {
    res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        language,
        ...(options.voice ? { voice: options.voice } : {}),
      }),
      signal: controller.signal,
    });
  } catch (e) {
    // Un STOP no es un fallo: se resuelve en silencio (el componente que espera
    // apaga su spinner igual que si hubiera terminado).
    if (playback.stopped) return stopped;
    // Un abort propio (timeout) se explica; el externo se propaga tal cual.
    if (controller.signal.aborted && !options.signal?.aborted) {
      throw new Error(`Timeout (TTS): no response after ${timeoutMs / 1000}s`);
    }
    throw e;
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener("abort", abortExternal);
  }

  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }

  const voice = res.headers?.get("X-TTS-Voice") ?? "";
  const degraded = res.headers?.get("X-TTS-Degraded") === "1";
  const result: SpeakResult = { voice, degraded };

  if (playback.stopped) return result;
  await playBlob(await res.blob(), playback);
  return result;
}
