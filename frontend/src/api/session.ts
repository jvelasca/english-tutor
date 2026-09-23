import type { User } from "../types/api";
import { ApiError, deleteJson, getJsonOptional, postJson, putJson } from "./client";

/**
 * Cuenta y sesión del alumno (V3.75, Fase 2 del P0; credencial real en V3.81).
 *
 * Hasta V3.74 la identidad viajaba en **cada** URL (`?user_id=…`), así que
 * cualquiera que alcanzara la API podía pedir los datos de otro perfil. Desde
 * V3.75 la identidad la firma el servidor y viaja en una cookie `et_session`
 * **HttpOnly**: esta capa solo la **abre** una vez.
 *
 * V3.81 añade la mitad que faltaba: la cuenta tiene **contraseña**. Si la tiene,
 * `openSession` la exige y sin ella el backend responde 401 — así que la puerta de
 * perfil deja de ser un «elige un nombre» y pasa a ser un «elige una cuenta y
 * demuestra que es tuya». Los desenlaces llegan tipados (`SessionPasswordError`) y
 * no como texto, porque la puerta tiene que distinguir «falta la contraseña» de
 * «no cuadra» y de «el freno está activo».
 *
 * Lo que **no** hace esta capa: decidir la política de contraseña. La decide el
 * servidor (`services/credentials.py`) y aquí solo se anticipa para no mandar
 * peticiones condenadas.
 */

/** Por qué falló la apertura de sesión. */
export type SessionPasswordReason =
  | "password-required"
  | "password-invalid"
  | "password-throttled";

/**
 * La apertura de sesión necesita una contraseña (correcta). Es un desenlace
 * **normal** del producto, no una avería: la puerta lo usa para pedirla. Por eso es
 * un error propio y no un `Error` genérico que se confundiría con «backend caído».
 */
export class SessionPasswordError extends Error {
  readonly reason: SessionPasswordReason;
  /** Segundos que faltan cuando el freno de intentos está activo (si no, 0). */
  readonly retryAfterSeconds: number;

  constructor(reason: SessionPasswordReason, retryAfterSeconds = 0) {
    super(reason);
    this.name = "SessionPasswordError";
    this.reason = reason;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

/** Abre sesión para una cuenta existente (404 si no existe). */
export async function openSession(
  userId: string,
  password?: string,
): Promise<User> {
  try {
    return await postJson<User>("/api/session", {
      user_id: userId,
      ...(password !== undefined && password !== "" ? { password } : {}),
    });
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.detail === "PASSWORD_REQUIRED") {
        throw new SessionPasswordError("password-required");
      }
      if (err.detail === "PASSWORD_INVALID") {
        throw new SessionPasswordError("password-invalid");
      }
      if (err.detail === "PASSWORD_THROTTLED") {
        throw new SessionPasswordError("password-throttled", err.retryAfterSeconds);
      }
    }
    throw err;
  }
}

/**
 * Registro de una cuenta nueva: nombre, email y contraseña (V3.81).
 *
 * Sustituye al «pide un perfil» de V3.77: cualquier persona puede crear su cuenta
 * desde el equipo, y el email sirve para **verificar** y **recuperar** — no para
 * entrar (la entrada sigue siendo el selector con avatar). El backend solo lo
 * acepta desde el propio equipo; por LAN se sigue **pidiendo**.
 */
export function createAccount(
  name: string,
  email: string,
  password: string,
): Promise<User> {
  // El email se limpia aquí (y el nombre también): lo normal es pegarlo, y un
  // espacio al final es un «ese email no parece válido» que el alumno no ve.
  // La contraseña **no** se toca: los espacios ahí pueden ser parte de la clave.
  return postJson<User>("/api/users", {
    name: name.trim(),
    email: email.trim(),
    password,
  });
}

/**
 * Cambia la contraseña de la cuenta **de la sesión**.
 *
 * `currentPassword` solo hace falta si ya tenía una: pedirla es lo que impide que
 * quien pase por delante de un equipo con la sesión abierta ponga su contraseña y
 * se quede la cuenta. Al cambiarla, el backend sube la época de autenticación: las
 * demás sesiones de esa cuenta mueren en la siguiente petición.
 */
export function changePassword(
  currentPassword: string | null,
  newPassword: string,
): Promise<User> {
  return putJson<User>("/api/session/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

/**
 * Cambia el email de la cuenta **de la sesión**. Exige la contraseña aunque ya
 * haya sesión: apuntar la verificación a otro correo es la forma de quedarse una
 * cuenta. El email nuevo nace **sin verificar** (el sello era del anterior).
 */
export function changeEmail(password: string, email: string): Promise<User> {
  return putJson<User>("/api/session/email", { password, email: email.trim() });
}

/**
 * Baja autoservicio: la cuenta deja de operar y **no se borra nada**.
 *
 * Exige la contraseña (una baja que se puede provocar desde fuera no es un derecho
 * del alumno). El borrado definitivo es otra cosa: lo decide el webmaster desde la
 * consola, con copia previa y confirmación por nombre.
 */
export function unenrollAccount(password: string): Promise<{
  unenrolled: boolean;
  user: User;
}> {
  return postJson<{ unenrolled: boolean; user: User }>("/api/account/unenroll", {
    password,
  });
}

/**
 * Reenvía el enlace de verificación. **Sin SMTP no envía nada** y lo dice
 * (`sent: false`): el modo híbrido, contado en la respuesta en vez de fingiendo un
 * correo que no ha salido. Entonces la verificación la sella el webmaster.
 */
export function resendVerification(): Promise<{
  sent: boolean;
  reason: string;
}> {
  return postJson<{ sent: boolean; reason: string }>(
    "/api/account/resend-verification",
    {},
  );
}

/**
 * Confirma el email con el token del enlace. **Sin sesión**: el enlace puede
 * abrirse en otro navegador, y lo que autoriza no es la cookie sino un token de un
 * solo uso con caducidad.
 */
export function verifyEmail(token: string): Promise<User> {
  return postJson<User>("/api/account/verify", { token });
}

/**
 * La cuenta de la sesión actual; `null` si no hay sesión (401).
 *
 * V3.80.2: un **404** o un **403** tampoco son averías, y tratarlos como tales
 * colgaba la app. El 404 significa que la cookie es válida pero apunta a una cuenta
 * que ya no existe (la purgó el webmaster desde la consola) y el 403
 * (`PROFILE_DISABLED`, `ACCOUNT_UNENROLLED`) que está fuera de servicio: en los dos
 * casos **no hay sesión que valga**, y la respuesta honesta es la misma que un 401.
 * Antes, el 404 llegaba como excepción, tumbaba el `Promise.all` del arranque y
 * dejaba la puerta de perfil con la lista vacía y sin salida.
 *
 * La cookie muerta se retira en el mismo paso: es lo que hace que el arreglo dure,
 * porque si no el fallo se reproduce en cada recarga. El `DELETE` es best-effort
 * (si el backend no responde, se ignora: el cliente ya decidió que no hay sesión).
 *
 * V3.81: `401 SESSION_STALE` (la contraseña cambió en otro sitio, o el webmaster
 * forzó la baja) entra por el mismo camino: es un 401 y significa «vuelve a
 * entrar».
 */
export function getSession(): Promise<User | null> {
  return getJsonOptional<User>("/api/session").catch((err: unknown) => {
    if (err instanceof ApiError && (err.status === 404 || err.status === 403)) {
      void closeSession().catch(() => {});
      return null;
    }
    throw err;
  });
}

/**
 * Cierra sesión (caduca la cookie en el navegador).
 *
 * Ya se usa (V3.81): el menú de cuenta tiene **Salir**, que es lo que faltaba en un
 * producto donde la puerta es un selector de cuentas compartido en casa. El token
 * es autocontenido y caduca solo, así que basta con retirar la cookie.
 */
export function closeSession(): Promise<{ closed: boolean }> {
  return deleteJson<{ closed: boolean }>("/api/session");
}
