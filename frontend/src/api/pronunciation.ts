import type { PronunciationResponse } from "../types/api";

export async function checkPronunciation(
  blob: Blob,
  expected: string,
): Promise<PronunciationResponse> {
  const form = new FormData();
  form.append("file", blob, "audio.webm");
  form.append("expected", expected);
  form.append("language", "en");

  const res = await fetch("/api/pronunciation", { method: "POST", body: form });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as PronunciationResponse;
}
