import { test, expect } from "@playwright/test";

/**
 * Panel de análisis (ANALYSIS) en la vista Learn/Chat: las pestañas deben verse
 * todas (sin scroll oculto) y, en desktop, el panel debe poder ensancharse más
 * allá del antiguo tope de 680px. En móvil/tablet el panel es un drawer a pantalla
 * completa y las pestañas se envuelven en varias filas.
 */

const TAB_LABELS = [
  "Your progress",
  "Today's plan",
  "Your profile",
  "Speaking",
  "Writing",
  "Speaking assessment",
  "Tutor quality",
];

async function gotoLearn(page: import("@playwright/test").Page) {
  await page.goto("/");
  await expect(page.getByRole("navigation")).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(800);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Learn", exact: true })
    .click();
}

test("desktop: muestra todas las pestañas de Analysis y se puede ensanchar", async ({
  page,
}) => {
  test.skip(page.viewportSize()!.width < 1024, "Solo desktop");

  await gotoLearn(page);

  const tablist = page.getByRole("tablist", { name: "Analysis" });
  await expect(tablist).toBeVisible({ timeout: 15_000 });

  const tabs = tablist.getByRole("tab");
  await expect(tabs).toHaveCount(7);
  for (const label of TAB_LABELS) {
    await expect(tablist.getByRole("tab", { name: label })).toBeVisible();
  }

  // Ensancha el panel hasta el tope (ArrowLeft aumenta el ancho del panel derecho).
  const handle = page.getByRole("separator", { name: "Resize analysis panel" });
  await handle.focus();
  for (let i = 0; i < 30; i++) {
    await handle.press("ArrowLeft");
  }

  await expect
    .poll(async () => (await page.locator(".pane--insights").boundingBox())!.width, {
      timeout: 5000,
    })
    .toBeGreaterThan(680);
});

test("móvil: abre el panel de análisis y muestra todas las pestañas", async ({
  page,
}) => {
  test.skip(page.viewportSize()!.width >= 1024, "Solo móvil/tablet");

  await gotoLearn(page);

  await page.getByRole("button", { name: "Open analysis panel" }).click();
  await expect(page.locator(".pane--insights")).toHaveClass(/open/);

  const tablist = page.getByRole("tablist", { name: "Analysis" });
  await expect(tablist).toBeVisible({ timeout: 15_000 });

  const tabs = tablist.getByRole("tab");
  await expect(tabs).toHaveCount(7);
  for (const label of TAB_LABELS) {
    await expect(tablist.getByRole("tab", { name: label })).toBeVisible();
  }
});
