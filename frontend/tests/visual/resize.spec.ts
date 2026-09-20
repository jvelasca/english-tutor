import { test, expect } from "@playwright/test";
import { ensureProfile } from "./gateHelper";

/**
 * Verifica que el panel de conversaciones del workspace de Conversar es
 * redimensionable y que su ancho se persiste por usuario (premisa 20). Usa el
 * teclado (accesible y determinista): ArrowLeft/ArrowRight sobre el asa enfocada.
 * Solo corre en desktop; en móvil/tablet el panel es un drawer y el asa se oculta.
 *
 * V3.75.3: el asa del panel de análisis (derecha) se retiró junto con el panel —
 * su contenido vive en MI PROGRESO y el análisis de evolución se abre desde la
 * cabecera (`/analisis`)—. Este test fija ahora el invariante que sobrevive, y
 * con el mismo criterio: el ancho se guarda por usuario y se restaura al recargar.
 */
test("redimensiona el panel de conversaciones y persiste el ancho por usuario", async ({ page }) => {
  test.skip(page.viewportSize()!.width < 1024, "Solo desktop");

  const nav = page.getByRole("navigation", { name: "Main navigation" });

  await page.goto("/");
  // Si la ProfileGate aparece (varios perfiles sin cookie), entra con el perfil
  // de test estable para que la persistencia por usuario funcione (V3.5.7).
  await ensureProfile(page);
  await expect(nav).toBeVisible({ timeout: 15_000 });
  // Da tiempo a que se seleccione el perfil antes de persistir.
  await page.waitForTimeout(800);

  // Navega al chat libre (sidebar + zona central).
  await page.goto("/#/chat");
  await expect(nav).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(500);

  // Asa del panel de conversaciones, localizada por su nombre accesible
  // (chat.resizeConversations) en lugar de su posición ordinal.
  const sidebarHandle = page.getByRole("separator", {
    name: "Resize conversations panel",
  });
  const sidebar = page.locator(".pane--sidebar");
  await expect(sidebarHandle).toBeVisible();

  // Normaliza al mínimo (SIDEBAR_MIN) para que el test sea idempotente: en el
  // panel izquierdo ArrowLeft reduce el ancho. 30 pulsos cubren todo el rango
  // (máximo → 200, incluyendo el tope relativo al viewport).
  await sidebarHandle.focus();
  for (let i = 0; i < 30; i++) {
    await sidebarHandle.press("ArrowLeft");
  }
  await page.waitForTimeout(150);
  const before = (await sidebar.boundingBox())!.width;

  // Agranda el panel: ArrowRight aumenta el ancho del panel izquierdo (+24 por pulso).
  await sidebarHandle.press("ArrowRight");
  await sidebarHandle.press("ArrowRight");
  await sidebarHandle.press("ArrowRight");

  await expect
    .poll(async () => (await sidebar.boundingBox())!.width, { timeout: 5000 })
    .toBeGreaterThan(before + 50);

  // Persistencia: espera el debounce (400ms) + PUT y recarga. Tras la recarga
  // la URL sigue siendo #/chat y el layout guardado se restaura junto con los
  // paneles del workspace.
  await page.waitForTimeout(900);
  await page.reload();
  await expect(nav).toBeVisible({ timeout: 15_000 });
  await expect(sidebarHandle).toBeVisible();
  await page.waitForTimeout(500);

  await expect
    .poll(async () => (await page.locator(".pane--sidebar").boundingBox())!.width, {
      timeout: 5000,
    })
    .toBeGreaterThan(before + 50);
});
