import { test, expect } from "@playwright/test";

/**
 * Flujo LAN/móvil (V1.30): verifica que la página de conexión de dispositivos
 * y el test de micrófono se renderizan en viewport móvil, y que el aviso de
 * micrófono no disponible aparece cuando el permiso está denegado.
 *
 * El backend puede no estar arrancado: la UI debe degradar con estados vacíos
 * sin romperse (la tarjeta de conexión muestra un aviso en lugar del QR).
 */

async function gotoApp(page: import("@playwright/test").Page) {
  await page.goto("/");
  await expect(page.getByRole("navigation")).toBeVisible({ timeout: 15_000 });
}

test("móvil: la página de conexión de dispositivos se abre desde el header", async ({
  page,
}) => {
  test.skip(page.viewportSize()!.width >= 1024, "Solo móvil/tablet");

  await gotoApp(page);

  await page.getByRole("button", { name: "Help" }).click();

  await expect(
    page.getByRole("heading", { name: "Connect a device" }),
  ).toBeVisible({ timeout: 15_000 });

  // Con backend: aviso "Local network only…". Sin backend (CI): estado degradado.
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
