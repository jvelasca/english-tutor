export async function transcribe(blob: Blob): Promise<string> {
  const form = new FormData();
  form.append("file", blob, "audio.webm");
  form.append("language", "en");

  const res = await fetch("/api/transcribe", { method: "POST", body: form });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  const data = (await res.json()) as { text: string };
  return data.text;
}

export async function speak(text: string): Promise<void> {
  const res = await fetch("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
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
