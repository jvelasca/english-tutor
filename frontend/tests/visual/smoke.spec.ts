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
    // V3.10: el chat libre tiene raíz propia /#/chat; las rutas guiadas de
    // Conversation viven en /#/aprender/conversar (se revisan en
    // conversationRoutesReview.spec.ts con mocks).
    { id: "chat", url: "/#/chat" },
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
    // V3.6.1: las prácticas de APRENDER muestran un atajo de actividades en la
    // franja superior; pulsar otro atajo navega a su hoja (la activa queda
    // resaltada). Solo en listening (pantalla de práctica de Aprender).
    if (route.id === "listening") {
      const switcher = page.getByRole("group", { name: "Switch activity" });
      if (await switcher.isVisible().catch(() => false)) {
        await switcher.getByRole("button", { name: "Vocabulary" }).click();
        await expect(page).toHaveURL(/#\/aprender\/vocabulario/, {
          timeout: 10_000,
        });
        // Vuelve a la ruta original para que el recorrido siga estable.
        await page.goto(route.url);
        await expect(nav()).toBeVisible({ timeout: 15_000 });
      }
    }
  }
});
