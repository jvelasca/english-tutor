import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import { ensureProfile } from "./gateHelper";

/**
 * Cotas del diálogo de perfil (V3.79.0).
 *
 * El fallo del alumno —«al editar un perfil, el cuadro de selección de icono se
 * sale de pantalla por arriba»— ocurría cuando el viewport útil era más bajo que
 * el `max-height` del diálogo: al centrarlo con flexbox, la mitad superior caía
 * fuera del área desplazable y el asa de cerrar se volvía inalcanzable.
 *
 * Honestidad sobre lo que esto mide: en el Chrome de escritorio `vh` y `dvh`
 * valen lo mismo, así que **no** se reproduce el recorte de la barra de un móvil.
 * Lo que se fija es la COTA que lo hace imposible —el diálogo nunca sobresale del
 * viewport, por bajo que sea— y que la cabecera y el pie siguen alcanzables. La
 * invariante del CSS, que es donde vive la decisión, se fija además en
 * `src/styles/dialogLayout.test.ts`.
 */

/** Abre el diálogo de edición del perfil de la sesión. */
async function openProfileDialog(page: Page) {
  await page.goto("/");
  await ensureProfile(page);
  // El disparador del menú se localiza por su contrato accesible (`aria-haspopup`)
  // y no por su texto: su nombre accesible es el del perfil, que cambia.
  await page.locator('button[aria-haspopup="menu"]').click();
  await page.getByRole("button", { name: "Edit profile" }).click();
  await expect(page.getByRole("dialog", { name: "Edit profile" })).toBeVisible();
}

test("el diálogo de perfil no se sale por arriba en un viewport bajo", async ({
  page,
}) => {
  await openProfileDialog(page);

  // Viewport deliberadamente bajo: la parrilla de iconos y colores más la sección
  // de baja hacen que el contenido no quepa.
  await page.setViewportSize({ width: 520, height: 300 });
  await page.waitForTimeout(150);

  const dialog = page.getByRole("dialog", { name: "Edit profile" });
  const box = await dialog.boundingBox();
  expect(box).not.toBeNull();
  // La cota que rompía el centrado con flexbox: el borde superior empieza DENTRO
  // de la pantalla. Con el CSS viejo, `y` era negativo.
  expect(box!.y).toBeGreaterThanOrEqual(0);
  // Y el borde inferior también: el pie con «Guardar» no puede quedar fuera.
  expect(box!.y + box!.height).toBeLessThanOrEqual(300 + 1);

  // El asa de cerrar sigue siendo alcanzable —era justo lo que se perdía—.
  const close = page.getByRole("button", { name: "Close" });
  await expect(close).toBeVisible();
  await close.click();
  await expect(dialog).toBeHidden();
});

test("el cuerpo del diálogo scrollea y la cabecera no se va con el scroll", async ({
  page,
}) => {
  await openProfileDialog(page);
  await page.setViewportSize({ width: 520, height: 300 });
  await page.waitForTimeout(150);

  const dialog = page.getByRole("dialog", { name: "Edit profile" });
  const close = page.getByRole("button", { name: "Close" });
  const headerBefore = await close.boundingBox();

  // Se desplaza el cuerpo hasta abajo: el scroll vive en el cuerpo, así que la
  // cabecera —y su asa— no debe moverse. Antes el scroll estaba en el diálogo
  // entero y al desplazar se iba también la cabecera.
  await dialog.locator(".dialog-body").evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  await page.waitForTimeout(100);

  const headerAfter = await close.boundingBox();
  expect(headerAfter!.y).toBeCloseTo(headerBefore!.y, 0);
});
