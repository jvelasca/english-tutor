import { test, expect } from "@playwright/test";
import path from "node:path";

/**
 * MI PROGRESO (V3.1): pantalla consolidada de 5 pestañas accesibles en
 * `#/progreso` (Overview / Course / Skills / Journey / Tracks). Sustituye al
 * antiguo test del panel Analysis con 7 pestañas, que ya no existe en V3.1
 * (el panel Analysis del workspace es ahora ligero: calidad del tutor + botón
 * "See my progress").
 *
 * Se mockea `/api/users` para que el shell de pestañas se renderice aunque el
 * resto de APIs fallen: la app debe degradar con estados vacíos sin romperse.
 */

const USER = { id: "u1", name: "Test", created_at: "2026-01-01T00:00:00Z" };

// progress.overviewTab / courseTab / skillsTab / journeyTab / tracksTab (en).
const PROGRESS_TAB_LABELS = [
  "Overview",
  "Course",
  "Skills",
  "Journey",
  "Tracks",
];

async function mockUsers(page: import("@playwright/test").Page) {
  await page.route("**/api/users", (route) =>
    route.fulfill({ json: [USER] }),
  );
}

async function gotoProgress(
  page: import("@playwright/test").Page,
): Promise<import("@playwright/test").Locator> {
  await page.goto("/#/progreso");

  await expect(
    page.getByRole("heading", { name: "My progress", exact: true }),
  ).toBeVisible({ timeout: 15_000 });

  const tablist = page.getByRole("tablist", { name: "Progress sections" });
  await expect(tablist).toBeVisible({ timeout: 15_000 });
  return tablist;
}

test("desktop: MI PROGRESO muestra las 5 pestañas", async ({ page }, testInfo) => {
  test.skip(page.viewportSize()!.width < 1024, "Solo desktop");

  await mockUsers(page);
  const tablist = await gotoProgress(page);

  const tabs = tablist.getByRole("tab");
  await expect(tabs).toHaveCount(5);
  for (const label of PROGRESS_TAB_LABELS) {
    await expect(
      tablist.getByRole("tab", { name: label, exact: true }),
    ).toBeVisible();
  }

  const project = testInfo.project.name;
  await page.screenshot({
    path: path.join(
      "tests",
      "visual",
      "screenshots",
      project,
      "progress-tabs.png",
    ),
    fullPage: true,
  });
});

test("móvil: MI PROGRESO muestra el tablist y la pestaña activa seleccionada", async ({
  page,
}) => {
  test.skip(page.viewportSize()!.width >= 1024, "Solo móvil/tablet");

  await mockUsers(page);
  const tablist = await gotoProgress(page);

  // En móvil el tablist es desplazable en horizontal (overflow-x-auto): se
  // valida que existan al menos 3 pestañas y que la activa (la primera,
  // Overview) esté marcada con aria-selected.
  const tabs = tablist.getByRole("tab");
  expect(await tabs.count()).toBeGreaterThanOrEqual(3);

  await expect(
    tablist.getByRole("tab", { name: "Overview", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
});
