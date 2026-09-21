import type { User } from "../types/api";
import { ApiError, deleteJson, getJsonOptional, postJson, putJson } from "./client";

/**
 * Sesión del perfil activo (V3.75, Fase 2 del P0 de identidad).
 *
 * Hasta V3.74 la identidad viajaba en **cada** URL (`?user_id=…`), así que
 * cualquiera que alcanzara la API podía pedir los datos de otro perfil. Ahora la
 * identidad la firma el servidor y viaja en una cookie `et_session` **HttpOnly**:
 * esta capa ya no manda el perfil en cada petición, solo lo **abre** una vez.
 *
 * `getSession()` recupera esa identidad al arrancar: el cliente no puede leer la
 * cookie (es HttpOnly, y ese es justo el punto), así que se la **pregunta** al
 * servidor. Es la razón de que la UI no pueda fiarse de nada guardado en el
 * navegador para saber quién es.
 *
 * V3.76 (Fase 3): un perfil puede tener PIN. Entonces `openSession` exige el
 * segundo argumento y la respuesta sin él deja de ser un 200. Los tres
 * desenlaces posibles llegan aquí como `SessionPinError` tipado y **no** como
 * un `Error` de texto: la puerta de perfil tiene que poder distinguirlos para
 * pintar el paso de PIN, el error de PIN o la cuenta atrás del freno.
 */

/** Por qué falló la apertura de sesión por PIN. */
export type SessionPinReason = "pin-required" | "pin-invalid" | "pin-throttled";

/**
 * La apertura de sesión necesita un PIN (correcto). Es un desenlace **normal**
 * del producto, no una avería: la puerta lo usa para pedir el PIN. Por eso es
 * un error propio y no un `Error` genérico que se confundiría con «backend
 * caído».
 */
export class SessionPinError extends Error {
  readonly reason: SessionPinReason;
  /** Segundos que faltan cuando el freno de intentos está activo (si no, 0). */
  readonly retryAfterSeconds: number;

  constructor(reason: SessionPinReason, retryAfterSeconds = 0) {
    super(reason);
    this.name = "SessionPinError";
    this.reason = reason;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

/** Abre sesión para un perfil existente (404 si no existe). */
export async function openSession(userId: string, pin?: string): Promise<User> {
  try {
    return await postJson<User>("/api/session", {
      user_id: userId,
      ...(pin !== undefined && pin !== "" ? { pin } : {}),
    });
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.detail === "PIN_REQUIRED") {
        throw new SessionPinError("pin-required");
      }
      if (err.detail === "PIN_INVALID") {
        throw new SessionPinError("pin-invalid");
      }
      if (err.detail === "PIN_THROTTLED") {
        throw new SessionPinError("pin-throttled", err.retryAfterSeconds);
      }
    }
    throw err;
  }
}

/**
 * Pone, cambia o retira el PIN del perfil de la sesión actual (V3.76).
 *
 * `currentPin` solo hace falta si el perfil ya tenía PIN. `newPin` vacío lo
 * retira y el perfil vuelve a entrar sin credencial (consecuencia declarada en
 * `docs/audit/PARKED.md`). Devuelve el perfil actualizado, con el `has_pin`
 * nuevo: la UI no necesita adivinar en qué estado quedó.
 */
export function setSessionPin(
  currentPin: string | null,
  newPin: string,
): Promise<User> {
  return putJson<User>("/api/session/pin", {
    current_pin: currentPin,
    new_pin: newPin,
  });
}

/** El perfil de la sesión actual; `null` si no hay sesión (401). */
export function getSession(): Promise<User | null> {
  return getJsonOptional<User>("/api/session");
}

/**
 * Cierra sesión (caduca la cookie en el navegador).
 *
 * La app **no** la llama hoy: cambiar de perfil es `openSession` con otro id (el
 * selector del `Header`), y cerrar sin abrir no aporta nada al alumno —el producto
 * no tiene cuentas ni pantalla de salida—. Se conserva porque es la mitad que
 * falta del ciclo (`POST`/`GET`/`DELETE`) y porque el test de integración de la
 * API la fija: si el endpoint cambia, esto se entera.
 */
export function closeSession(): Promise<{ closed: boolean }> {
  return deleteJson<{ closed: boolean }>("/api/session");
}
