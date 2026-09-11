import fs from "node:fs";
import path from "node:path";

import { request } from "@playwright/test";

/**
 * Perfil estable para tests visuales.
 *
 * Desde V3.52.1 el perfil se crea (o reutiliza) AQUÍ, en `globalSetup`, que
 * corre en un único proceso: antes cada spec hacía su propio find-or-create
 * contra la base de datos real y, como los 9 specs corren en paralelo sobre 3
 * proyectos, varios workers insertaban a la vez y aparecían perfiles duplicados
 * «Visual Tester» en la app del usuario. El perfil va marcado `is_test`, así que
 * nunca se lista en la app ni en el lanzador, y `globalTeardown` lo borra.
 *
 * El perfil se comparte con los workers por FICHERO (`.tester.json`), no solo por
 * `process.env`: `globalSetup` y los workers pueden vivir en procesos distintos,
 * así que el fichero es el handshake fiable. Si el backend no está disponible
 * (p. ej. CI sin API) se usa un id ficticio y no se escribe nada en ninguna base
 * de datos: la UI degrada igual.
 */
export const VISUAL_TESTER_NAME = "Visual Tester";
export const VISUAL_TESTER_FALLBACK_ID = "u-visual-tester";
export const TESTER_FILE = path.join("tests", "visual", ".tester.json");

const BASE_URL = "https://localhost:5173";

interface TesterRow {
  id?: string;
  name?: string;
  is_test?: boolean;
}

export default async function globalSetup(): Promise<void> {
  let id = VISUAL_TESTER_FALLBACK_ID;
  try {
    const ctx = await request.newContext({
      baseURL: BASE_URL,
      ignoreHTTPSErrors: true,
    });
    try {
      const listRes = await ctx.get("/api/users?include_test=true");
      const users: unknown = listRes.ok() ? await listRes.json() : [];
      const existing = Array.isArray(users)
        ? (users as TesterRow[]).find(
            (u) => u?.is_test === true && u?.name === VISUAL_TESTER_NAME,
          )
        : undefined;
      let found: TesterRow | undefined = existing;
      if (!found) {
        const created = await ctx.post("/api/users", {
          data: { name: VISUAL_TESTER_NAME, is_test: true },
        });
        if (created.ok()) found = (await created.json()) as TesterRow;
      }
      if (found && typeof found.id === "string") {
        id = found.id;
      }
    } finally {
      await ctx.dispose();
    }
  } catch {
    /* Backend no disponible: perfil ficticio, sin escritura en BD. */
  }
  const profile = { id, name: VISUAL_TESTER_NAME };
  fs.writeFileSync(TESTER_FILE, JSON.stringify(profile), "utf8");
  process.env.VISUAL_TESTER_ID = profile.id;
  process.env.VISUAL_TESTER_NAME = profile.name;
}
