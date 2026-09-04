import { test, expect } from "@playwright/test";
import { ensureProfile } from "./gateHelper";

/**
 * Verifica que los paneles del workspace de Conversar son redimensionables y
 * que el ancho se persiste por usuario (premisa 20). Usa el teclado (accesible
 * y determinista): ArrowLeft/ArrowRight sobre el asa enfocada. Solo corre en
 * desktop; en móvil/tablet los paneles son drawers y las asas se ocultan.
 *
 * V3.1: la píldora raíz "Chat" ya no existe. V3.10: el workspace conversacional
 * libre vive en su raíz `/chat` (las rutas guiadas ocupan `/aprender/conversar`)
 * y conserva la misma estructura de paneles (sidebar + zona central + Analysis).
 */
test("redimensiona el panel Analysis y persiste el ancho por usuario", async ({ page }) => {
  test.skip(page.viewportSize()!.width < 1024, "Solo desktop");

  const nav = page.getByRole("navigation", { name: "Main navigation" });

  await page.goto("/");
  // Si la ProfileGate aparece (varios perfiles sin cookie), entra con el perfil
  // de test estable para que la persistencia por usuario funcione (V3.5.7).
  await ensureProfile(page);
  await expect(nav).toBeVisible({ timeout: 15_000 });
  // Da tiempo a que se seleccione el perfil antes de persistir.
  await page.waitForTimeout(800);

  // Navega al chat libre (sidebar + zona central + Analysis).
  await page.goto("/#/chat");
  await expect(nav).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(500);

  // Asa derecha del panel de análisis, localizada por su nombre accesible
  // (chat.resizeInsights) en lugar de su posición ordinal.
  const insightsHandle = page.getByRole("separator", {
    name: "Resize analysis panel",
  });
  const insights = page.locator(".pane--insights");
  await expect(insightsHandle).toBeVisible();

  // Normaliza al mínimo (RIGHT_MIN) para que el test sea idempotente: ArrowRight
  // reduce el ancho del panel derecho. 30 pulsos cubren todo el rango
  // (máximo → 300, incluyendo el tope relativo al viewport).
  await insightsHandle.focus();
  for (let i = 0; i < 30; i++) {
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

  // Persistencia: espera el debounce (400ms) + PUT y recarga. Tras la recarga
  // la URL sigue siendo #/chat y el layout guardado se restaura junto con los
  // paneles del workspace.
  await page.waitForTimeout(900);
  await page.reload();
  await expect(nav).toBeVisible({ timeout: 15_000 });
  await expect(insightsHandle).toBeVisible();
  await page.waitForTimeout(500);

  await expect
    .poll(async () => (await page.locator(".pane--insights").boundingBox())!.width, {
      timeout: 5000,
    })
    .toBeGreaterThan(before + 50);
});
