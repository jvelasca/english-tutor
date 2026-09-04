import { test, expect } from "@playwright/test";
import path from "node:path";
import { ensureProfile } from "./gateHelper";

/**
 * Smoke visual V3.1: recorre las rutas principales y captura un screenshot por
 * ruta. Los screenshots se guardan en `tests/visual/screenshots/<proyecto>/<ruta>.png`
 * para su revisión manual (premisa 20: responsive 100% verificado + tests visuales).
 *
 * La navegación raíz de V3.1 tiene solo 3 píldoras (Home / Course / Learn); el
 * resto de pantallas (MI PROGRESO, AYUDA y las sub-rutas de APRENDER como
 * Listening o Conversar) se alcanzan por URL hash. Ya no hay píldoras raíz
 * "Chat", "Progress" ni "Vocabulary" ni un panel Analysis por pestañas.
 */

test("capturar rutas principales", async ({ page }, testInfo) => {
  const project = testInfo.project.name;
  const shot = (name: string) =>
    path.join("tests", "visual", "screenshots", project, `${name}.png`);

  const nav = () => page.getByRole("navigation", { name: "Main navigation" });

  // Home es la ruta inicial.
  await page.goto("/");
  // Selecciona un perfil si la ProfileGate aparece (V3.5.7).
  await ensureProfile(page);
  await expect(nav()).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: shot("home"), fullPage: true });

  // Píldora "Course" (navegación raíz → Formación).
  await nav().getByRole("button", { name: "Course", exact: true }).click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: shot("course"), fullPage: true });

  // Píldora "Learn" (navegación raíz → hub de APRENDER).
  await nav().getByRole("button", { name: "Learn", exact: true }).click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: shot("learn"), fullPage: true });

  // Pantallas que ya no son destino raíz: se navegan directamente por URL hash.
  const deepRoutes = [
    { id: "listening", url: "/#/aprender/listening" },
    { id: "conversar", url: "/#/aprender/conversar" },
    { id: "progress", url: "/#/progreso" },
    { id: "help", url: "/#/ayuda" },
  ] as const;
  for (const route of deepRoutes) {
    // Tras la entrada inicial el perfil queda en cookie: la puerta no reaparece.
    await page.goto(route.url);
    await expect(nav()).toBeVisible({ timeout: 15_000 });
    await page.waitForTimeout(600);
    await page.screenshot({ path: shot(route.id), fullPage: true });

    // V3.6: APRENDER/LISTENING muestra ahora el panel de ruta ("Repasar lo
    // aprendido", "Añadir práctica") al desplegar un nivel; capturamos también
    // esa vista si el backend responde y hay niveles que desplegar.
    if (route.id === "listening") {
      const historyBtn = page
        .getByRole("button", { name: /Level .* history/i })
        .first();
      const visible = await historyBtn.isVisible().catch(() => false);
      if (visible) {
        await historyBtn.click();
        await page
          .getByText(/Review learned|Repasar lo aprendido/i)
          .first()
          .waitFor({ timeout: 10_000 })
          .catch(() => {
            /* backend ausente o perfil sin ítems: se omite la captura */
          });
        await page
          .getByText(/Review learned|Repasar lo aprendido/i)
          .first()
          .scrollIntoViewIfNeeded()
          .catch(() => {
            /* no aplicable */
          });
        await page.waitForTimeout(700);
        await page.screenshot({ path: shot("listening-route") });
      }
    }
  }
});
