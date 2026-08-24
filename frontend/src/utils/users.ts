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
 * - si hay un perfil recordado (cookie) que existe, se selecciona ese;
 * - si no, con exactamente un usuario se selecciona ese;
 * - en cualquier otro caso, null (el usuario elige).
 */
export function resolveInitialUserId(
  users: readonly User[],
  rememberedId: string | null = null,
): string | null {
  if (rememberedId && users.some((u) => u.id === rememberedId)) {
    return rememberedId;
  }
  return users.length === 1 ? users[0].id : null;
}
