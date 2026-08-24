// Utilidades de cookies (mínimas y con guardas para SSR/tests sin `document`).

const USER_ID_COOKIE = "et_user_id";

export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  const row = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  if (!row) return null;
  return decodeURIComponent(row.slice(prefix.length));
}

export function writeCookie(name: string, value: string, days = 365): void {
  if (typeof document === "undefined") return;
  const expires = new Date(Date.now() + days * 86_400_000).toUTCString();
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
}

export function deleteCookie(name: string): void {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax`;
}

export function readUserIdCookie(): string | null {
  return readCookie(USER_ID_COOKIE);
}

export function writeUserIdCookie(userId: string): void {
  writeCookie(USER_ID_COOKIE, userId);
}
