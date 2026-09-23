/**
 * ¿Esta pestaña se abrió **en el propio equipo** que corre la app? (V3.81)
 *
 * Es el espejo de `config.is_admin_loopback_host` en el backend, y existe por un
 * motivo muy concreto: el **registro** de cuentas (`POST /api/users`) está cerrado
 * fuera de loopback, así que la puerta de entrada tiene que saber si puede ofrecer
 * «Crear cuenta» o solo «Pedir una cuenta». Ofrecer el formulario desde la LAN
 * sería ofrecer un botón que el servidor rechaza con un 403 — y una UI que promete
 * lo que el backend niega es peor que una UI que no lo ofrece.
 *
 * Se decide por el **host de la página** y no preguntándole al backend: es la misma
 * señal que ve el servidor (la conexión viene de loopback exactamente cuando el
 * navegador está en el equipo) y no añade una petición al arranque, que es justo el
 * camino que V3.80.2 tuvo que desatascar. Duplicar la lista de hosts es aceptable
 * aquí porque es una decisión de **presentación**: quien manda de verdad es
 * `is_admin_loopback_host`, y si las dos listas se separan, lo peor que pasa es un
 * 403 con su mensaje.
 */
const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

export function isLocalDevice(): boolean {
  try {
    return LOOPBACK_HOSTS.has(window.location.hostname.toLowerCase());
  } catch {
    return false;
  }
}
