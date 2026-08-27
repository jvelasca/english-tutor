import { test, expect } from "@playwright/test";

/**
 * Verifica que los paneles del CHAT son redimensionables y que el ancho se
 * persiste por usuario (premisa 20). Usa el teclado (accesible y determinista):
 * ArrowLeft/ArrowRight sobre el asa enfocada. Solo corre en desktop; en
 * móvil/tablet los paneles son drawers y las asas se ocultan.
 */
test("redimensiona el panel Analysis y persiste el ancho por usuario", async ({ page }) => {
  test.skip(page.viewportSize()!.width < 1024, "Solo desktop");

  await page.goto("/");
  await expect(page.getByRole("navigation")).toBeVisible({ timeout: 15_000 });
  // Da tiempo a que se cree/auto-seleccione el usuario antes de persistir.
  await page.waitForTimeout(800);

  // Navega a Chat (sidebar + zona central + Analysis).
  await page.getByRole("navigation").getByRole("button", { name: "Chat", exact: true }).click();
  await page.waitForTimeout(500);

  const insightsHandle = page.getByRole("separator").nth(1);
  const insights = page.locator(".pane--insights");

  // Normaliza al mínimo (RIGHT_MIN) para que el test sea idempotente: ArrowRight
  // reduce el ancho del panel derecho. 24 pulsos cubren todo el rango (680→300).
  await insightsHandle.focus();
  for (let i = 0; i < 24; i++) {
    await insightsHandle.press("ArrowRight");
  }
  await page.waitForTimeout(150);
  const before = (await insights.boundingBox())!.width;

  // Agranda el panel: ArrowLeft aumenta el ancho del panel derecho (+24 por pulso).
  await insightsHandle.press("ArrowLeft");
  await insightsHandle.press("ArrowLeft");
  await insightsHandle.press("ArrowLeft");

  await expect
    .poll(async () => (await insights.boundingBox())!.width, { timeout: 5000 })
    .toBeGreaterThan(before + 50);

  // Persistencia: espera el debounce (400ms) + PUT y recarga.
  await page.waitForTimeout(900);
  await page.reload();
  await expect(page.getByRole("navigation")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("navigation").getByRole("button", { name: "Chat", exact: true }).click();
  await page.waitForTimeout(500);

  await expect
    .poll(async () => (await page.locator(".pane--insights").boundingBox())!.width, {
      timeout: 5000,
    })
    .toBeGreaterThan(before + 50);
});
