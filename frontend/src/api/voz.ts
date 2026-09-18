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

/** Reproduce un blob de audio y resuelve cuando termina (o falla). */
function playBlob(blob: Blob): Promise<void> {
  const url = URL.createObjectURL(blob);
  return new Promise<void>((resolve, reject) => {
    const audio = new Audio(url);
    audio.onended = () => {
      URL.revokeObjectURL(url);
      resolve();
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("No se pudo reproducir el audio"));
    };
    audio.play().catch((e) => {
      URL.revokeObjectURL(url);
      reject(e);
    });
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
 */
export async function speak(
  text: string,
  _userId?: string | null,
  language: VoiceLanguage = "en",
  options: SpeakOptions = {},
): Promise<SpeakResult> {
  const timeoutMs = options.timeoutMs ?? TTS_TIMEOUT_MS;
  const controller = new AbortController();
  const abortExternal = () => controller.abort();
  if (options.signal) {
    if (options.signal.aborted) controller.abort();
    else options.signal.addEventListener("abort", abortExternal, { once: true });
  }
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language }),
      signal: controller.signal,
    });
  } catch (e) {
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

  await playBlob(await res.blob());
  return { voice, degraded };
}
