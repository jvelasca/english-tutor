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

/** Por qué falló la apertura de sesión (V3.82: login por email + contraseña). */
export type SessionLoginReason =
  // Email o contraseña que no cuadran. El backend **no** distingue los dos casos
  // para no servir de oráculo de qué correos tienen cuenta.
  | "invalid-credentials"
  // La cuenta existe y está autorizada, pero todavía no tiene contraseña: su
  // invitación está esperando en el correo.
  | "not-activated"
  | "disabled"
  | "unenrolled"
  | "throttled";

/**
 * La apertura de sesión no pudo completarse por un motivo **del producto**, no por
 * una avería: credenciales que no cuadran, cuenta sin activar, cuenta fuera de
 * servicio o el freno de intentos. Se separa de un `Error` genérico para que la
 * puerta pueda decir qué pasa sin confundirlo con «el backend no responde».
 */
export class SessionLoginError extends Error {
  readonly reason: SessionLoginReason;
  /** Segundos que faltan cuando el freno de intentos está activo (si no, 0). */
  readonly retryAfterSeconds: number;

  constructor(reason: SessionLoginReason, retryAfterSeconds = 0) {
    super(reason);
    this.name = "SessionLoginError";
    this.reason = reason;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

/**
 * Abre sesión con **email + contraseña** (V3.82).
 *
 * Es el único camino de entrada. Ya no se entra **eligiendo** una cuenta de una
 * lista: eso permitía nombrar a cualquiera y, con las cuentas heredadas sin
 * contraseña, entrar como esa persona. Ahora hay que demostrar la credencial.
 */
export async function openSession(email: string, password: string): Promise<User> {
  try {
    return await postJson<User>("/api/session", { email: email.trim(), password });
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 429 || err.detail === "PASSWORD_THROTTLED") {
        throw new SessionLoginError("throttled", err.retryAfterSeconds);
      }
      if (err.detail === "ACCOUNT_NOT_ACTIVATED") {
        throw new SessionLoginError("not-activated");
      }
      if (err.detail === "PROFILE_DISABLED") {
        throw new SessionLoginError("disabled");
      }
      if (err.detail === "ACCOUNT_UNENROLLED") {
        throw new SessionLoginError("unenrolled");
      }
      if (err.status === 401) {
        throw new SessionLoginError("invalid-credentials");
      }
    }
    throw err;
  }
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
 * Activa la cuenta desde el enlace de **invitación** (V3.82): elige la
 * contraseña y deja la sesión abierta.
 *
 * Los desenlaces que la página tiene que contar: token inválido (400),
 * caducado (400) y contraseña que no cumple la política (400). Se traducen a
 * códigos porque la pantalla dice frases distintas con cada uno.
 */
export type ActivationReason = "invalid" | "expired" | "password-format" | "error";

export class ActivationError extends Error {
  readonly reason: ActivationReason;
  constructor(reason: ActivationReason) {
    super(reason);
    this.name = "ActivationError";
    this.reason = reason;
  }
}

export async function activateAccount(
  token: string,
  password: string,
): Promise<User> {
  try {
    return await postJson<User>("/api/account/activate", { token, password });
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.detail === "ACTIVATION_TOKEN_EXPIRED") {
        throw new ActivationError("expired");
      }
      if (err.detail === "ACTIVATION_TOKEN_INVALID") {
        throw new ActivationError("invalid");
      }
      if (err.detail === "PASSWORD_FORMAT") {
        throw new ActivationError("password-format");
      }
    }
    throw new ActivationError("error");
  }
}

/**
 * «Olvidé mi contraseña» (V3.82). **Responde siempre igual**, exista o no la
 * cuenta: el backend no revela si un correo tiene cuenta, y la pantalla tampoco
 * puede prometer que ha enviado algo que quizá no ha salido (sin SMTP no sale
 * ningún correo, y eso es el modo híbrido declarado).
 */
export function forgotPassword(email: string): Promise<{ sent: boolean }> {
  return postJson<{ sent: boolean }>("/api/account/forgot-password", {
    email: email.trim(),
  });
}

/** Por qué falló el restablecimiento de la contraseña. */
export type ResetReason = "invalid" | "expired" | "password-format" | "error";

export class ResetError extends Error {
  readonly reason: ResetReason;
  constructor(reason: ResetReason) {
    super(reason);
    this.name = "ResetError";
    this.reason = reason;
  }
}

/** Elige contraseña nueva desde el enlace del correo de restablecimiento. */
export async function resetPassword(token: string, password: string): Promise<User> {
  try {
    return await postJson<User>("/api/account/reset-password", { token, password });
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.detail === "RESET_TOKEN_EXPIRED") {
        throw new ResetError("expired");
      }
      if (err.detail === "RESET_TOKEN_INVALID") {
        throw new ResetError("invalid");
      }
      if (err.detail === "PASSWORD_FORMAT") {
        throw new ResetError("password-format");
      }
    }
    throw new ResetError("error");
  }
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
