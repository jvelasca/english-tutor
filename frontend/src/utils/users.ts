import type { User } from "../types/api";

const DEFAULT_NAME = "Usuario";

/**
 * Devuelve un nombre de perfil que no colisiona con los ya existentes,
 * añadiendo un sufijo numérico ("Usuario", "Usuario 2", ...) cuando sea necesario.
 */
export function nextDefaultUserName(existingNames: readonly string[]): string {
  if (!existingNames.includes(DEFAULT_NAME)) return DEFAULT_NAME;
  let n = 2;
  while (existingNames.includes(`${DEFAULT_NAME} ${n}`)) n++;
  return `${DEFAULT_NAME} ${n}`;
}

/**
 * Decide el perfil inicial al abrir la app:
 * - si hay un perfil **de la sesión del servidor** que existe, se selecciona ese;
 * - si no, con exactamente un usuario se selecciona ese;
 * - en cualquier otro caso, null (el usuario elige).
 *
 * El `sessionUserId` ya no viene de una cookie que el navegador pueda reescribir:
 * sale de `GET /api/session` (V3.75, Fase 2 del P0 de identidad), así que aquí es
 * un dato de confianza para **elegir qué pintar**, no una credencial.
 */
export function resolveInitialUserId(
  users: readonly User[],
  sessionUserId: string | null = null,
): string | null {
  if (sessionUserId && users.some((u) => u.id === sessionUserId)) {
    return sessionUserId;
  }
  return users.length === 1 ? users[0].id : null;
}
