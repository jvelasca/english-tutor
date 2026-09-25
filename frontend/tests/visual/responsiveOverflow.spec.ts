import { test, expect, type Page } from "@playwright/test";
import { ensureProfile } from "./gateHelper";
import { expectNoHorizontalOverflow } from "./layoutHelper";

/**
 * Barrido RESPONSIVE de la app (V3.84.0).
 *
 * Premisa 20: «responsive 100 % verificado». Hasta ahora solo se fotografiaban
 * las rutas (`smoke.spec.ts`); este spec **mide** que ninguna empuje la página a
 * scroll horizontal, ni siquiera a **320 px**, un ancho que la suite no cubría
 * (el más estrecho en uso real, iPhone SE de 1.ª generación).
 *
 * Las tres rutas de las pestañas del diccionario se miden una a una porque cada
 * una monta una vista distinta (`Consultar` / `Personal` / `Flashcards`): el
 * defecto confirmado vivía en la primera y no se habría visto midiendo solo `/`.
 */

const ROUTES = [
  { id: "home", url: "/" },
  { id: "learn", url: "/#/aprender" },
  { id: "listening", url: "/#/aprender/listening" },
  { id: "speaking", url: "/#/aprender/speaking" },
  { id: "vocabulary", url: "/#/aprender/vocabulario" },
  { id: "grammar", url: "/#/aprender/gramatica" },
  { id: "chat", url: "/#/chat" },
  { id: "progress", url: "/#/progreso" },
  { id: "analysis", url: "/#/analisis" },
  { id: "help", url: "/#/ayuda" },
  { id: "translator", url: "/#/traductor" },
] as const;

const DICTIONARY_TABS = ["Look up", "Personal", "Flashcards"] as const;

async function waitForShell(page: Page) {
  await expect(
    page.getByRole("navigation", { name: "Main navigation" }).first(),
  ).toBeVisible({ timeout: 15_000 });
}

test("ninguna ruta desborda horizontalmente (390 / 768 / 1280)", async ({
  page,
}) => {
  await page.goto("/");
  await ensureProfile(page);
  await waitForShell(page);

  for (const route of ROUTES) {
    await page.goto(route.url);
    await waitForShell(page);
    // Da tiempo al layout diferido (fuentes, bloques que cargan después).
    await page.waitForTimeout(400);
    await expectNoHorizontalOverflow(page, route.id);
  }

  // El diccionario, pestaña a pestaña: cada una es una vista distinta.
  await page.goto("/#/diccionario");
  await waitForShell(page);
  for (const tab of DICTIONARY_TABS) {
    await page.getByRole("tab", { name: tab, exact: true }).click();
    await page.waitForTimeout(400);
    await expectNoHorizontalOverflow(page, `diccionario/${tab}`);
  }
});

test.describe("ancho mínimo 320 px", () => {
  // iPhone SE (1.ª gen) y ventanas muy estrechas. Se mide una sola vez, en el
  // proyecto `mobile`: el resto de proyectos ya cubren 390/768/1280 arriba.
  test.use({ viewport: { width: 320, height: 720 } });

  test("ninguna ruta desborda a 320 px", async ({ page }, testInfo) => {
    test.skip(
      testInfo.project.name !== "mobile",
      "320 px se mide una sola vez (proyecto mobile)",
    );

    await page.goto("/");
    await ensureProfile(page);
    await waitForShell(page);

    for (const route of ROUTES) {
      await page.goto(route.url);
      await waitForShell(page);
      await page.waitForTimeout(400);
      await expectNoHorizontalOverflow(page, `320/${route.id}`);
    }

    await page.goto("/#/diccionario");
    await waitForShell(page);
    for (const tab of DICTIONARY_TABS) {
      await page.getByRole("tab", { name: tab, exact: true }).click();
      await page.waitForTimeout(400);
      await expectNoHorizontalOverflow(page, `320/diccionario/${tab}`);
    }
  });
});
