import type { User } from "../types/api";
import { resolveInitialUserId } from "./users";

/**
 * Qué hacer al arrancar con la lista de cuentas y la sesión del servidor.
 *
 * Vive aquí, y no dentro del `useEffect` de `useChat`, porque es la decisión que
 * más fácil se rompe en silencio en la Fase 2 del P0 de identidad: si la app pinta
 * una cuenta activa **sin** sesión abierta, todo se ve normal y **cada** petición
 * responde 401. Como función pura, la matriz entera se prueba sin navegador.
 *
 * - `adopt`: la sesión ya apunta a la cuenta resuelta → solo fijarla en el estado.
 * - `open`: hay cuenta resuelta pero **sin** sesión (equipo recién instalado, o
 *   tras «Salir») → hay que abrirla antes de pintar nada. Solo cuando **no** tiene
 *   contraseña: desde V3.81 eso es el caso heredado, no la norma.
 * - `password`: igual que `open`, pero la cuenta tiene contraseña (V3.81) → **no**
 *   se puede abrir a ciegas: hay que pedirla. Sin este desenlace, el arranque
 *   automático lanzaría un `POST /api/session` condenado a 401 y el error se
 *   tragaría en silencio, dejando la app sin cuenta y sin decir por qué.
 * - `none`: nada que hacer (ninguna cuenta, o varias y ninguna elegida).
 */
export type SessionPlan =
  | { action: "none" }
  | { action: "adopt"; userId: string }
  | { action: "open"; userId: string }
  | { action: "password"; userId: string };

export function planSession(
  users: readonly User[],
  sessionUserId: string | null,
): SessionPlan {
  const resolved = resolveInitialUserId(users, sessionUserId);
  if (resolved === null) return { action: "none" };
  if (resolved === sessionUserId) return { action: "adopt", userId: resolved };
  // La contraseña no se adivina: si la cuenta la tiene, la apertura pasa por la UI.
  // `has_password` lo sirve `GET /api/users`; el hash no viaja nunca. Quien decide
  // de verdad es el servidor (401 `PASSWORD_REQUIRED`): esto solo evita mandar una
  // petición que ya se sabe condenada.
  const user = users.find((u) => u.id === resolved);
  if (user?.has_password) return { action: "password", userId: resolved };
  return { action: "open", userId: resolved };
}
