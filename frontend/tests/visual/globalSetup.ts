import fs from "node:fs";
import path from "node:path";

/**
 * Perfil estable para los tests visuales.
 *
 * **Lo que hacía y por qué ya no puede hacerlo (V3.82).** Desde V3.52.1 este
 * fichero creaba (o reutilizaba) un perfil real marcado `is_test` contra la API,
 * en un único proceso, para que cada spec no hiciera su propio find-or-create en
 * paralelo y no aparecieran «Visual Tester» duplicados. V3.82 retira
 * `POST /api/users` —el alta ya no es pública— y `GET /api/users` deja de
 * enumerar sin sesión, así que ese ida y vuelta por la API **no existe**.
 *
 * **Por qué no se pierde nada.** El arnés visual corre sin backend por diseño:
 * mide layout y responsive, y `gateHelper.ts` resuelve la identidad entera
 * mockeando `/api/session` y `/api/users` en el navegador. El perfil de la base
 * de datos solo servía para que la app lo «auto-seleccionara» al recargar; con el
 * login por email no hay selección. Lo que queda es lo único que los specs
 * necesitan: un **id estable** compartido entre el proceso de setup y los
 * workers.
 *
 * El handshake sigue siendo un FICHERO (`.tester.json`) y no solo `process.env`:
 * `globalSetup` y los workers pueden vivir en procesos distintos, así que el
 * fichero es lo fiable.
 */
export const VISUAL_TESTER_NAME = "Visual Tester";
export const VISUAL_TESTER_FALLBACK_ID = "u-visual-tester";
export const TESTER_FILE = path.join("tests", "visual", ".tester.json");

export default async function globalSetup(): Promise<void> {
  const profile = {
    id: process.env.VISUAL_TESTER_ID ?? VISUAL_TESTER_FALLBACK_ID,
    name: VISUAL_TESTER_NAME,
  };
  fs.writeFileSync(TESTER_FILE, JSON.stringify(profile), "utf8");
  process.env.VISUAL_TESTER_ID = profile.id;
  process.env.VISUAL_TESTER_NAME = profile.name;
}
