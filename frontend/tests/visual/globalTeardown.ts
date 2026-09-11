import fs from "node:fs";

import { request } from "@playwright/test";

import { TESTER_FILE, VISUAL_TESTER_FALLBACK_ID } from "./globalSetup";

const BASE_URL = "https://localhost:5173";

/**
 * Borra el perfil de prueba (y sus datos) al terminar la suite visual, para no
 * dejar residuos en la base de datos local (V3.52.1). Aunque el perfil está
 * marcado `is_test` y es invisible en la app, se elimina igualmente: el teardown
 * cierra el ciclo. Si el backend no está disponible o se usó el id ficticio no
 * hay nada que limpiar. Siempre borra el fichero de handshake.
 */
export default async function globalTeardown(): Promise<void> {
  let id: string | undefined;
  try {
    const parsed = JSON.parse(fs.readFileSync(TESTER_FILE, "utf8")) as {
      id?: string;
    };
    id = parsed.id;
  } catch {
    /* Sin fichero (setup no llegó a escribir): nada que limpiar. */
  }
  try {
    if (id && id !== VISUAL_TESTER_FALLBACK_ID) {
      const ctx = await request.newContext({
        baseURL: BASE_URL,
        ignoreHTTPSErrors: true,
      });
      try {
        await ctx.delete(`/api/users/${encodeURIComponent(id)}`);
      } finally {
        await ctx.dispose();
      }
    }
  } catch {
    /* Backend caído: nada que limpiar por API. */
  } finally {
    fs.rmSync(TESTER_FILE, { force: true });
  }
}
