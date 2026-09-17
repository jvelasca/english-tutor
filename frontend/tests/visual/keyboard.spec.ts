import { test, expect } from "@playwright/test";
import { ensureProfile } from "./gateHelper";

/**
 * Cierre GUI pre-V4.0 (V3.73.1), GUI-06: recorrido por teclado.
 *
 * No pretende auditar todas las pantallas (eso es la matriz completa de V4.0.x),
 * sino fijar el contrato del núcleo: el primer Tab revela el enlace de salto y
 * lleva el foco al contenido, y las tarjetas del hub de APRENDER —incluidas las
 * nuevas de Reading/Writing— son botones reales que se activan con Enter.
 */
test("el primer Tab revela el skip link y enfoca el contenido", async ({
  page,
}) => {
  await page.goto("/#/aprender");
  await ensureProfile(page);

  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav.first()).toBeVisible({ timeout: 15_000 });

  const skip = page.getByRole("link", { name: "Skip to content" });

  // Reposado fuera de la vista (translateY(-200%)) hasta que recibe el foco.
  const resting = await skip.boundingBox();
  expect(resting?.y ?? 0).toBeLessThan(0);

  await page.keyboard.press("Tab");
  await expect(skip).toBeFocused();
  // Al enfocarse baja a la vista (el CSS lo trae con translateY(0)).
  await expect
    .poll(async () => (await skip.boundingBox())?.y ?? -1)
    .toBeGreaterThanOrEqual(0);

  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
});

test("las tarjetas del hub (incluido el tutor) se activan con teclado", async ({
  page,
}) => {
  await page.goto("/#/aprender");
  await ensureProfile(page);

  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav.first()).toBeVisible({ timeout: 15_000 });

  // Las 4 actividades y las 2 prácticas con el tutor son botones operables.
  const reading = page.getByRole("button", {
    name: /Reading/,
    exact: false,
  });
  await expect(reading).toBeVisible({ timeout: 15_000 });
  await reading.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#\/chat\/lectura$/, { timeout: 10_000 });

  // El estado del enlace del chat por destreza es recuperable (F4): recargar
  // mantiene la destreza activa en la URL.
  await page.reload();
  await expect(page).toHaveURL(/#\/chat\/lectura$/);

  await page.goto("/#/aprender");
  const writing = page.getByRole("button", { name: /Writing/ });
  await expect(writing).toBeVisible({ timeout: 15_000 });
  await writing.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#\/chat\/escritura$/, { timeout: 10_000 });
});
