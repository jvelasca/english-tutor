import fs from "node:fs";
import path from "node:path";

import type { Page } from "@playwright/test";

/**
 * Perfil estable para tests visuales.
 *
 * Desde V3.52.1 el perfil lo crea UNA sola vez `globalSetup` (en un proceso
 * único, marcado `is_test` e invisible en la app) y lo borra `globalTeardown`.
 * Este helper ya NO hace find-or-create: aquel GET+POST no atómico, ejecutado en
 * paralelo por los 9 specs × 3 proyectos contra la base de datos real, era la
 * causa de los perfiles duplicados «Visual Tester». Aquí solo se mockea
 * `GET /api/users` con ese único perfil para que la app lo auto-seleccione y la
 * ProfileGate no aparezca.
 *
 * El perfil se lee del fichero de handshake escrito por `globalSetup` (los
 * workers pueden vivir en otro proceso; `process.env` no es fiable) y, si no
 * existe, se degrada al id ficticio de siempre. Un perfil recién creado no tiene
 * preferencias en backend, así que el idioma de la UI es el del navegador
 * (inglés) y los tests son deterministas. Al ser un perfil real (persistido) la
 * app puede escribir settings (resize.spec persiste el ancho de panel) sin
 * errores.
 */
export const VISUAL_TESTER_NAME =
  process.env.VISUAL_TESTER_NAME ?? "Visual Tester";

const FALLBACK_ID = "u-visual-tester";

// Debe coincidir con `TESTER_FILE` de `globalSetup.ts` (misma ruta relativa al
// cwd, convención que ya usan los specs para `screenshots/`).
const TESTER_FILE = path.join("tests", "visual", ".tester.json");

export interface TesterUser {
  id: string;
  name: string;
}

function testerUser(): TesterUser {
  try {
    const parsed = JSON.parse(fs.readFileSync(TESTER_FILE, "utf8")) as {
      id?: unknown;
      name?: unknown;
    };
    if (parsed && typeof parsed.id === "string" && parsed.id) {
      return {
        id: parsed.id,
        name:
          typeof parsed.name === "string" ? parsed.name : VISUAL_TESTER_NAME,
      };
    }
  } catch {
    /* Sin fichero de handshake: se usa el perfil ficticio. */
  }
  return {
    id: process.env.VISUAL_TESTER_ID ?? FALLBACK_ID,
    name: VISUAL_TESTER_NAME,
  };
}

export async function ensureProfile(page: Page): Promise<TesterUser> {
  const user = testerUser();

  // Mock GET /api/users → un único perfil: la app lo auto-selecciona al recargar
  // y la ProfileGate (que solo aparece con 0 o varios perfiles) no llega a salir.
  await page.route("**/api/users", (route) => {
    if (route.request().method() === "GET") {
      void route.fulfill({ json: [user] });
    } else {
      void route.continue();
    }
  });
  await page.reload();
  await page.waitForTimeout(600);
  return user;
}
