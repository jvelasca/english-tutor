import type { User } from "../types/api";

export const AVATAR_COLORS = [
  "#6366f1",
  "#8b5cf6",
  "#ec4899",
  "#f43f5e",
  "#f59e0b",
  "#10b981",
  "#0ea5e9",
  "#64748b",
  "#14b8a6",
  "#d946ef",
];

export const AVATAR_EMOJIS = [
  "😀",
  "😎",
  "🤓",
  "🦊",
  "🐱",
  "🐶",
  "🦁",
  "🐼",
  "🐸",
  "🦉",
  "🌵",
  "🍀",
  "🎧",
  "🎸",
  "⚽",
  "🚀",
  "🌈",
  "🍕",
  "☕",
  "🧠",
];

/** Iniciales (1-2 letras) para el avatar cuando no hay imagen ni emoji. */
export function initials(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return "?";
  const words = trimmed.split(/\s+/);
  const first = words[0]?.charAt(0) ?? "";
  const second = words.length > 1 ? words[words.length - 1].charAt(0) : "";
  return (first + second).toUpperCase();
}

/** Hash determinista (para asignar color por defecto de forma estable). */
export function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

/** Color del avatar: el elegido por el usuario o uno estable derivado del id. */
export function avatarColor(user: User): string {
  if (user.avatar_color) return user.avatar_color;
  return AVATAR_COLORS[hashString(user.id) % AVATAR_COLORS.length];
}
