import { ApiError, postJson } from "./client";
import type { ProfileRequest } from "../types/api";

/**
 * Solicitudes de perfil (V3.77).
 *
 * La app **no crea ni borra perfiles**: los pide. Es la consecuencia visible de
 * `agentes/v377-perfiles-webmaster.md`: el webmaster no es un rol de la app, es
 * quien ejecuta el lanzador, así que lo único que el alumno puede hacer desde su
 * navegador —su equipo o el móvil de la LAN— es dejar una fila en una cola.
 *
 * `requestProfile` funciona **sin sesión** (quien la usa es justamente quien
 * todavía no tiene perfil), y por eso el backend la acota con lo que sí puede:
 * cupo estrecho por IP, tope de pendientes y una petición por nombre.
 */
export type ProfileRequestOutcome =
  | { ok: true; request: ProfileRequest }
  | { ok: false; reason: ProfileRequestFailure };

/**
 * Motivos por los que una solicitud no llega a registrarse.
 *
 * Se distinguen porque la UI tiene que decir cosas distintas: «ya está pedido» es
 * una espera, «demasiadas pendientes» es un aviso para el webmaster, «nombre no
 * válido» es culpa de quien escribe, y «no se pudo» es red. Un solo `false` para
 * los cuatro obligaría a la pantalla a decir «algo falló» y a nadie le sirve.
 */
export type ProfileRequestFailure =
  | "duplicate"
  | "full"
  | "invalid"
  | "throttled"
  | "offline";

function _outcomeFromError(err: unknown): ProfileRequestOutcome {
  if (err instanceof ApiError) {
    if (err.status === 409) return { ok: false, reason: "duplicate" };
    if (err.status === 422) return { ok: false, reason: "invalid" };
    if (err.status === 429) {
      // Dos 429 distintos: el del cupo por IP (`RATE_LIMITED`, delimitador de
      // seguridad) y el de la cola llena (solicitudes pendientes de más). El
      // relato para el alumno no es el mismo, así que no se juntan.
      return {
        ok: false,
        reason: err.detail === "RATE_LIMITED" ? "throttled" : "full",
      };
    }
  }
  return { ok: false, reason: "offline" };
}

/** Pide un perfil nuevo. Sin sesión; **no** crea nada. */
export async function requestProfile(
  displayName: string,
  note = "",
): Promise<ProfileRequestOutcome> {
  // El nombre se recorta aquí y no se valida más: la forma la decide el backend
  // (colapsa espacios internos y acota la longitud), que es el único que la
  // conoce. Duplicar la regla en el cliente sería tener dos verdades.
  const name = displayName.trim();
  if (!name) return { ok: false, reason: "invalid" };
  try {
    return {
      ok: true,
      request: await postJson<ProfileRequest>("/api/profile-requests", {
        display_name: name,
        note: note.trim(),
      }),
    };
  } catch (err) {
    return _outcomeFromError(err);
  }
}

/** El perfil de la sesión pide que se le borre. Requiere sesión; **no** borra nada. */
export async function requestProfileDelete(
  note = "",
): Promise<ProfileRequestOutcome> {
  try {
    return {
      ok: true,
      request: await postJson<ProfileRequest>("/api/profile-requests/delete", {
        note: note.trim(),
      }),
    };
  } catch (err) {
    return _outcomeFromError(err);
  }
}
