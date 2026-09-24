import fs from "node:fs";
import path from "node:path";

import type { Page } from "@playwright/test";

/**
 * Perfil estable para tests visuales.
 *
 * Desde V3.52.1 el perfil lo crea UNA sola vez `globalSetup` (en un proceso
 * único, marcado `is_test` e invisible en la app). V3.82 retira esa creación por
 * API (la alta ya no es pública) y la identidad **entera** se resuelve en el
 * navegador: este helper mockea `GET /api/users` con ese único perfil y
 * `GET/POST /api/session`, que es lo que la app consulta al arrancar. Como el
 * login por email retiró el selector, el mock ya no «auto-selecciona» nada: la
 * sesión llega ya abierta y la `ProfileGate` no aparece.
 *
 * V3.75 (Fase 2 del P0 de identidad) añadió la segunda mitad: la app pregunta
 * `GET /api/session` al arrancar y, si no hay sesión, la abre con
 * `POST /api/session` antes de pintar nada (la identidad la firma el servidor en
 * una cookie `et_session` HttpOnly). Por eso se mockea también `/api/session`:
 * sin ello la ProfileGate se queda abierta y **todo** clic acaba interceptado por
 * el `dialog-backdrop` — que es exactamente lo que pasó en la primera ejecución
 * real de CI sobre el commit de V3.75.0.
 *
 * El perfil se lee del fichero de handshake escrito por `globalSetup` (los
 * workers pueden vivir en otro proceso; `process.env` no es fiable) y, si no
 * existe, se degrada al id ficticio de siempre. Un id recién inventado no tiene
 * preferencias en backend, así que el idioma de la UI es el del navegador
 * (inglés) y los tests son deterministas.
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

  // Mock GET /api/users → un único perfil. V3.82: la app ya no lo usa para
  // «auto-seleccionar» a nadie (no hay selector); se mantiene porque el armazón
  // sigue pidiendo la lista para el menú de usuario y sin respuesta se quedaría
  // cargando.
  await page.route("**/api/users", (route) => {
    if (route.request().method() === "GET") {
      void route.fulfill({ json: [user] });
    } else {
      void route.continue();
    }
  });
  await mockIdentitySession(page, user);
  await page.reload();
  await page.waitForTimeout(600);
  return user;
}

/**
 * Mock del ciclo de sesión de identidad (V3.75, Fase 2 del P0 de identidad).
 *
 * La app **no** se fía de nada que pueda escribir el navegador: pregunta
 * `GET /api/session` y, si no hay sesión, la abre con `POST /api/session` antes
 * de pintar un perfil. Esas respuestas las firma el servidor (cookie `et_session`
 * HttpOnly con HMAC), así que el arnés visual —que corre **sin backend** por
 * diseño: esta suite mide layout y responsive— no puede satisfacerlas de verdad.
 *
 * Se resuelven en el navegador, igual que `GET /api/users`, y con el **mismo**
 * perfil que el resto del arnés: así la app arranca con sesión y la puerta de
 * entrada no aparece. Lo que este mock **no** prueba —y no pretende— es que el
 * servidor emita, firme y verifique la sesión: eso vive en
 * `backend/tests/test_sessions.py`, `test_identity_source.py`,
 * `test_users_self_only.py`, `test_public_surface.py` y en
 * `frontend/src/hooks/useChat.test.tsx`. Aquí se fija layout, no identidad.
 *
 * Importante: el `user` debe ser el MISMO objeto que se devuelve en
 * `GET /api/users`; si los ids no coinciden, el menú de usuario y la sesión
 * hablan de personas distintas y los tests dejan de ser deterministas.
 */
export async function mockIdentitySession(
  page: Page,
  user: TesterUser,
): Promise<void> {
  await page.route("**/api/session", (route) => {
    const method = route.request().method();
    if (method === "GET" || method === "POST") {
      void route.fulfill({ json: user });
    } else {
      // DELETE /api/session: la mitad que cierra el ciclo.
      void route.fulfill({ json: { closed: true } });
    }
  });
}
