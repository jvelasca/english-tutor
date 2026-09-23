/**
 * Forma de la contraseña (V3.81, Fase 3 del P0 de identidad).
 *
 * Espejo deliberado de `backend/services/credentials.py`: la misma regla a los dos
 * lados de la API. Aquí **no** se reimplementa nada de seguridad —el KDF, la
 * verificación y el freno de intentos viven solo en el backend—; esto es únicamente
 * la validación de forma que la UI necesita para no ofrecer un botón que el
 * servidor va a rechazar, y para poder decir «mínimo 8 caracteres» en un sitio.
 *
 * La lista de contraseñas obvias **no** se duplica: vive en el servidor, que es
 * quien decide. Decirle a la UI que «12345678» es mala sería repetir una lista que
 * se desincroniza; el servidor la rechaza y la UI cuenta lo que diga.
 */

export const PASSWORD_MIN_CHARS = 8;
export const PASSWORD_MAX_CHARS = 128;

/**
 * ¿Tiene forma de contraseña? Mismo criterio de forma que el backend: longitud,
 * sin espacios en los extremos (casi siempre es un pegote al copiar y pegar) y no
 * todo el mismo carácter.
 */
export function isPlausiblePassword(password: string): boolean {
  if (password !== password.trim()) return false;
  if (password.length < PASSWORD_MIN_CHARS) return false;
  if (password.length > PASSWORD_MAX_CHARS) return false;
  return new Set(password).size > 1;
}

/**
 * ¿Tiene forma de email? Deliberadamente laxa, como la del backend: la validación
 * de verdad es **recibirlo**. Solo se descartan los dedazos evidentes.
 */
export function isPlausibleEmail(email: string): boolean {
  const text = email.trim();
  if (text !== email || text.length > 254 || text.length < 3) return false;
  if (text.split("@").length !== 2) return false;
  const [local, domain] = text.split("@");
  return Boolean(local) && domain.includes(".") && !domain.startsWith(".");
}
