import type { Message } from "../types/api";

export function deriveTitle(messages: Message[]): string {
  const first = messages.find((m) => m.role === "user");
  if (!first) return "Nueva conversación";
  const t = first.content.trim();
  return t.length > 40 ? `${t.slice(0, 40)}…` : t;
}
