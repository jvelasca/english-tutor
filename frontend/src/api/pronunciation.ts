import { apiUrl } from "./client";
import type { PronunciationResponse } from "../types/api";

export async function checkPronunciation(
  blob: Blob,
  expected: string,
  userId: string,
): Promise<PronunciationResponse> {
  const form = new FormData();
  form.append("file", blob, "audio.webm");
  form.append("expected", expected);
  form.append("language", "en");

  const query = new URLSearchParams({ user_id: userId }).toString();
  const res = await fetch(apiUrl(`/api/pronunciation?${query}`), {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as PronunciationResponse;
}
