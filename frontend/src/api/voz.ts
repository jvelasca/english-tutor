/** Idioma (ISO-639-1) admitido por los endpoints de voz usados por la app. */
export type VoiceLanguage = "en" | "es";

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
 * Sintetiza y reproduce `text` con Piper. `language` elige la voz del idioma
 * destino (`"en"` por defecto); con `userId` el backend respeta su voz guardada
 * si es de ese idioma (V3.39, Fase 2).
 */
export async function speak(
  text: string,
  userId?: string | null,
  language: VoiceLanguage = "en",
): Promise<void> {
  const query = userId
    ? `?${new URLSearchParams({ user_id: userId }).toString()}`
    : "";
  const res = await fetch(`/api/tts${query}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, language }),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  await new Promise<void>((resolve, reject) => {
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
