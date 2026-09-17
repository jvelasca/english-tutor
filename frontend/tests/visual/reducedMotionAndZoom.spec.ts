import { test, expect } from "@playwright/test";
import { ensureProfile } from "./gateHelper";

/**
 * Cierre GUI pre-V4.0 (V3.73.1): GUI-05 (`prefers-reduced-motion`) y GUI-06
 * (zoom / reflow).
 *
 * - **GUI-05.** El bloque `@media (prefers-reduced-motion: reduce)` de la hoja
 *   solo alcanza las animaciones CSS; las de `motion/react` van por JS. Este
 *   test fija que el contenido no se queda a medio aparecer (opacidad 1 y
 *   visible) con la preferencia activa, que es el modo real de fallo: una
 *   entrada con `opacity: 0` inicial que no llega a completarse.
 * - **GUI-06.** A 200 % de zoom un viewport de escritorio reflowa a ~640px CSS.
 *   Se comprueba, con la fuente en "grande" y uno de los acentos, que las rutas
 *   principales no desbordan horizontalmente.
 */

const APPEARANCE_KEY = "english-tutor.appearance";

test.describe("prefers-reduced-motion (GUI-05)", () => {
  test.use({ reducedMotion: "reduce" });

  test("el hub de APRENDER no deja contenido a medio aparecer", async ({ page }) => {
    await page.goto("/#/aprender");
    await ensureProfile(page);

    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await expect(nav.first()).toBeVisible({ timeout: 15_000 });

    const grid = page.getByTestId("learn-hub-grid");
    await expect(grid).toBeVisible({ timeout: 15_000 });

    const cards = grid.locator("li");
    await expect(cards).toHaveCount(4);
    for (let i = 0; i < 4; i++) {
      // `toHaveCSS` reintenta: si el stagger dejara la tarjeta en opacity 0,
      // el test falla en lugar de pasar por una lectura demasiado temprana.
      await expect(cards.nth(i)).toHaveCSS("opacity", "1");
    }

    // El bloque de práctica con el tutor (Reading/Writing) también aparece.
    const tutor = page.getByTestId("learn-hub-tutor").locator("li");
    await expect(tutor).toHaveCount(2);
    await expect(tutor.nth(0)).toHaveCSS("opacity", "1");
    await expect(tutor.nth(1)).toHaveCSS("opacity", "1");
  });
});

test.describe("zoom 200 % / reflow (GUI-06)", () => {
  // 1280px de escritorio a 200 % de zoom reflowan a ~640px CSS.
  test.use({ viewport: { width: 640, height: 900 } });

  test("las rutas principales no desbordan horizontalmente con fuente grande", async ({
    page,
  }) => {
    await page.addInitScript(
      ([key, value]) => {
        window.localStorage.setItem(key, value);
      },
      [
        APPEARANCE_KEY,
        JSON.stringify({
          theme: "light",
          accent: "amber",
          fontScale: "large",
          density: "comfortable",
        }),
      ],
    );

    await page.goto("/");
    await ensureProfile(page);

    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await expect(nav.first()).toBeVisible({ timeout: 15_000 });

    const routes = [
      "/",
      "/#/aprender",
      "/#/aprender/speaking",
      "/#/progreso",
    ] as const;

    for (const route of routes) {
      await page.goto(route);
      await expect(nav.first()).toBeVisible({ timeout: 15_000 });
      // Espera a que el layout se asiente (fuentes y bloques diferidos).
      await page.waitForTimeout(500);

      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      );
      // 1px de tolerancia por redondeo subpíxel.
      expect(overflow, `desborde horizontal en ${route}`).toBeLessThanOrEqual(1);
    }
  });
});
