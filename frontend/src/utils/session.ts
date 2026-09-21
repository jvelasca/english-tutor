import type { User } from "../types/api";
import { resolveInitialUserId } from "./users";

/**
 * Qué hacer al arrancar con la lista de perfiles y la sesión del servidor.
 *
 * Vive aquí, y no dentro del `useEffect` de `useChat`, porque es la decisión que
 * más fácil se rompe en silencio en la Fase 2 del P0 de identidad: si la app pinta
 * un perfil activo **sin** sesión abierta, todo se ve normal y **cada** petición
 * responde 401. Como función pura, la matriz entera se prueba sin navegador.
 *
 * - `adopt`: la sesión ya apunta al perfil resuelto → solo fijarlo en el estado.
 * - `open`: hay perfil resuelto pero **sin** sesión (equipo recién instalado, o
 *   tras `DELETE /api/session`) → hay que abrirla antes de pintar nada.
 * - `pin`: igual que `open`, pero el perfil tiene PIN (V3.76) → **no** se puede
 *   abrir a ciegas: hay que pedirlo antes. Sin este desenlace, el arranque
 *   automático lanzaría un `POST /api/session` condenado a 401 y el error se
 *   tragaría en silencio, dejando la app sin perfil y sin decir por qué.
 * - `none`: nada que hacer (ningún perfil, o varios y ninguno elegido).
 */
export type SessionPlan =
  | { action: "none" }
  | { action: "adopt"; userId: string }
  | { action: "open"; userId: string }
  | { action: "pin"; userId: string };

export function planSession(
  users: readonly User[],
  sessionUserId: string | null,
): SessionPlan {
  const resolved = resolveInitialUserId(users, sessionUserId);
  if (resolved === null) return { action: "none" };
  if (resolved === sessionUserId) return { action: "adopt", userId: resolved };
  // El PIN no se adivina: si el perfil lo tiene, la apertura pasa por la UI.
  // `has_pin` lo sirve `GET /api/users`; nunca viaja el hash.
  const user = users.find((u) => u.id === resolved);
  if (user?.has_pin) return { action: "pin", userId: resolved };
  return { action: "open", userId: resolved };
}
