import type { Page } from "@playwright/test";

/**
 * Perfil estable para tests visuales (V3.5.7): se busca o crea por API y luego
 * se mockea `GET /api/users` para que la app vea exactamente un perfil y lo
 * auto-seleccione (la ProfileGate no aparece). Un perfil recién creado no tiene
 * preferencias en backend, así que el idioma de la UI es el del navegador
 * (inglés) y los tests son deterministas.
 *
 * Al usar un perfil real (persistido) la app puede escribir settings
 * (resize.spec persiste el ancho de panel) sin errores.
 */
export const VISUAL_TESTER_NAME = "Visual Tester";

export interface TesterUser {
  id: string;
  name: string;
}

async function findOrCreateTester(page: Page): Promise<TesterUser> {
  const req = page.request;
  try {
    const existing = await req.get("/api/users").then((r) => r.json());
    if (Array.isArray(existing)) {
      const found = existing.find((u: { name: string }) => u.name === VISUAL_TESTER_NAME);
      if (found && typeof found.id === "string") {
        return { id: found.id, name: found.name ?? VISUAL_TESTER_NAME };
      }
    }
    const created = await req
      .post("/api/users", { data: { name: VISUAL_TESTER_NAME } })
      .then((r) => r.json());
    if (created && typeof created === "object" && typeof created.id === "string") {
      return { id: created.id, name: VISUAL_TESTER_NAME };
    }
  } catch {
    /* backend no disponible: se usa un perfil ficticio y la UI degrada */
  }
  return { id: "u-visual-tester", name: VISUAL_TESTER_NAME };
}

export async function ensureProfile(page: Page): Promise<TesterUser> {
  const user = await findOrCreateTester(page);

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
