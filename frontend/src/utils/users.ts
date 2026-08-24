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
 * Decide si auto-seleccionar un perfil al abrir la app:
 * - con exactamente un usuario se selecciona ese;
 * - con varios no se auto-selecciona ninguno (null), para que el usuario elija
 *   y evitar entrar accidentalmente en el perfil equivocado.
 */
export function resolveInitialUserId(users: readonly User[]): string | null {
  return users.length === 1 ? users[0].id : null;
}
