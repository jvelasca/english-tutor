/**
 * Forma del PIN opcional por perfil (V3.76, Fase 3 del P0 de identidad).
 *
 * Espejo deliberado de `backend/services/pins.py`: la misma regla a los dos
 * lados de la API. Aquí **no** se reimplementa nada de seguridad —el hash, la
 * verificación y el freno de intentos viven solo en el backend—; esto es
 * únicamente la validación de forma que la UI necesita para no ofrecer un botón
 * que el servidor va a rechazar, y para poder decir «4-6 dígitos» sin duplicar
 * el número en cada componente.
 */

export const PIN_MIN_DIGITS = 4;
export const PIN_MAX_DIGITS = 6;

/** ¿Tiene forma de PIN? 4-6 dígitos, sin espacios ni signos. */
export function isValidPin(pin: string): boolean {
  return /^\d{4,6}$/.test(pin);
}

/**
 * Filtra lo que se teclea: solo dígitos y como mucho `PIN_MAX_DIGITS`. Evita
 * validar «1234abc» cuando lo que hace falta es no dejar escribir la letra.
 */
export function sanitizePinInput(value: string): string {
  return value.replace(/\D/g, "").slice(0, PIN_MAX_DIGITS);
}

/**
 * Resultado de poner/cambiar/retirar el PIN. Es un desenlace **de producto**
 * (el PIN actual no cuadra, el freno está activo), no un mensaje: quien lo pinte
 * decide el idioma.
 */
export type SetPinOutcome = "ok" | "pin-invalid" | "pin-throttled" | "error";
