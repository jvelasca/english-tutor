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
  | {
      ok: false;
      reason: ProfileRequestFailure;
      /**
       * V3.79.0: segundos que el backend pide esperar (`Retry-After`), solo
       * cuando los manda. Sin esto, un 429 por cupo llegaba a la pantalla sin
       * nada que decir salvo «algo falló»: el alumno no sabía si reintentar ya
       * o dentro de un minuto. Se omite cuando vale 0 para que el desenlace
       * normal siga siendo `{ok: false, reason}` y nada más.
       */
      retryAfterSeconds?: number;
    };

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
  | "email-taken"
  | "full"
  | "invalid"
  | "throttled"
  | "offline";

function _outcomeFromError(err: unknown): ProfileRequestOutcome {
  if (err instanceof ApiError) {
    const retryAfter = err.retryAfterSeconds > 0 ? err.retryAfterSeconds : undefined;
    const failure = (reason: ProfileRequestFailure): ProfileRequestOutcome =>
      retryAfter === undefined
        ? { ok: false, reason }
        : { ok: false, reason, retryAfterSeconds: retryAfter };
    if (err.status === 409) {
      // V3.82: un 409 puede ser «ya pediste esto» (duplicado) o «ese email ya
      // tiene cuenta». La respuesta útil es distinta —esperar vs entrar o
      // recuperar la contraseña—, así que no se juntan.
      return failure(err.detail === "EMAIL_TAKEN" ? "email-taken" : "duplicate");
    }
    if (err.status === 422) return failure("invalid");
    if (err.status === 429) {
      // Dos 429 distintos: el del cupo por IP (`RATE_LIMITED`, delimitador de
      // seguridad) y el de la cola llena (solicitudes pendientes de más). El
      // relato para el alumno no es el mismo, así que no se juntan.
      return failure(err.detail === "RATE_LIMITED" ? "throttled" : "full");
    }
  }
  return { ok: false, reason: "offline" };
}

/** El avatar con el que se pide la cuenta (V3.82). Todo opcional. */
export interface RequestedAvatar {
  avatar_color?: string;
  avatar_emoji?: string;
  avatar_image?: string;
}

/**
 * Pide un perfil nuevo. Sin sesión; **no** crea nada.
 *
 * V3.82: la solicitud lleva el email (con el que el webmaster autoriza por
 * correo) y el avatar elegido, para que al aprobarla no haya que teclear ni
 * elegir nada a mano.
 */
export async function requestProfile(
  displayName: string,
  email: string,
  avatar: RequestedAvatar = {},
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
        email: email.trim(),
        note: note.trim(),
        ...(avatar.avatar_color ? { avatar_color: avatar.avatar_color } : {}),
        ...(avatar.avatar_emoji ? { avatar_emoji: avatar.avatar_emoji } : {}),
        ...(avatar.avatar_image ? { avatar_image: avatar.avatar_image } : {}),
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
