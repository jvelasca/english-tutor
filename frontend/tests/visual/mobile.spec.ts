import { test, expect } from "@playwright/test";
import { ensureProfile } from "./gateHelper";

/**
 * Flujo LAN/móvil (V1.30 → V3.1): verifica que la ayuda general se abre desde
 * el header (D8: "Conectar dispositivo" ya no es una página; vive en Ajustes →
 * Sistema) y que el test de micrófono se renderiza en el popover del sistema.
 *
 * El backend puede no estar arrancado: la UI debe degradar con estados vacíos
 * sin romperse (la tarjeta de conexión muestra un aviso en lugar del QR).
 */

async function gotoApp(page: import("@playwright/test").Page) {
  await page.goto("/");
  // Si la ProfileGate aparece (varios perfiles sin cookie), entra con el perfil
  // de test estable (V3.5.7).
  await ensureProfile(page);
  await expect(page.getByRole("navigation")).toBeVisible({ timeout: 15_000 });
}

test("móvil: la ayuda general se abre desde el header", async ({ page }) => {
  test.skip(page.viewportSize()!.width >= 1024, "Solo móvil/tablet");

  await gotoApp(page);

  await page.getByRole("button", { name: "Help" }).click();

  await expect(
    page.getByRole("heading", { name: "Help" }),
  ).toBeVisible({ timeout: 15_000 });

  // La ayuda general presenta las tarjetas FAQ, no la página de conexión.
  await expect(
    page.getByRole("heading", { name: "What is English Tutor?" }),
  ).toBeVisible();

  // La guía de conexión vive en el popover del sistema (barra "Ready"):
  // con backend avisa "Local network only…", sin backend (CI) degrada.
  await page.getByRole("button", { name: "Ready" }).click();

  await expect(
    page.getByText(
      /Local network only|Start the app and connect to your local network/,
    ),
  ).toBeVisible();
});

test("móvil: el test de micrófono se renderiza en el estado del sistema", async ({
  page,
}) => {
  test.skip(page.viewportSize()!.width >= 1024, "Solo móvil/tablet");

  await gotoApp(page);

  await page.getByRole("button", { name: "Ready" }).click();

  await expect(
    page.getByRole("button", { name: "Test microphone" }),
  ).toBeVisible({ timeout: 15_000 });
});

test("móvil: permiso denegado muestra el aviso de micrófono no disponible", async ({
  page,
  context,
}) => {
  test.skip(page.viewportSize()!.width >= 1024, "Solo móvil/tablet");

  // Sin permiso concedido, getUserMedia se rechaza y la app debe mostrar un
  // aviso pedagógico en lugar de un error técnico.
  await context.clearPermissions();

  await gotoApp(page);

  await page.getByRole("button", { name: "Ready" }).click();
  await page.getByRole("button", { name: "Test microphone" }).click();

  await expect(
    page.getByText("Microphone unavailable"),
  ).toBeVisible({ timeout: 15_000 });
});
