import { getJson, postJson } from "./client";
import { parseSseLine } from "../utils/sse";
import type {
  ChatResponse,
  Message,
  ModelsResponse,
  TutorMode,
} from "../types/api";

interface StreamCallbacks {
  onDelta: (content: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

export function getModels(): Promise<ModelsResponse> {
  return getJson<ModelsResponse>("/api/models");
}

export function sendChat(
  messages: Message[],
  model: string,
  mode: TutorMode,
): Promise<ChatResponse> {
  return postJson<ChatResponse>("/api/chat", { model, messages, mode });
}

export async function streamChat(
  messages: Message[],
  model: string,
  mode: TutorMode,
  callbacks: StreamCallbacks,
): Promise<void> {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, messages, mode }),
  });

  if (!res.ok || !res.body) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const parsed = parseSseLine(line);
      if (!parsed) continue;
      if (parsed.error) {
        await reader.cancel();
        callbacks.onError(parsed.error);
        return;
      }
      if (parsed.done) {
        await reader.cancel();
        callbacks.onDone();
        return;
      }
      if (parsed.content) callbacks.onDelta(parsed.content);
    }
  }

  callbacks.onDone();
}
