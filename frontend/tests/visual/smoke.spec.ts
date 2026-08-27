import { test, expect } from "@playwright/test";
import path from "node:path";

/**
 * Smoke visual: recorre las rutas principales y captura un screenshot por ruta.
 * Los screenshots se guardan en `tests/visual/screenshots/<proyecto>/<ruta>.png`
 * para su revisión manual (premisa 20: responsive 100% verificado + tests visuales).
 */

const ROUTES = [
  { id: "home", label: "Home" },
  { id: "course", label: "Course" },
  { id: "progress", label: "Progress" },
  { id: "chat", label: "Chat" },
  { id: "learn", label: "Learn" },
] as const;

test("capturar rutas principales", async ({ page }, testInfo) => {
  const project = testInfo.project.name;
  const shot = (name: string) =>
    path.join("tests", "visual", "screenshots", project, `${name}.png`);

  await page.goto("/");
  await expect(page.getByRole("navigation")).toBeVisible({ timeout: 15_000 });

  // Home es la ruta inicial.
  await page.waitForTimeout(600);
  await page.screenshot({ path: shot("home"), fullPage: true });

  for (const route of ROUTES) {
    if (route.id === "home") continue;
    const nav = page.getByRole("navigation");
    await nav.getByRole("button", { name: route.label, exact: true }).click();
    await page.waitForTimeout(600);
    await page.screenshot({ path: shot(route.id), fullPage: true });
  }

  // Chat con el panel ANALYSIS abierto (verifica el rediseño por pestañas).
  const nav = page.getByRole("navigation");
  await nav.getByRole("button", { name: "Chat", exact: true }).click();
  await page.waitForTimeout(400);
  const toggle = page.getByRole("button", { name: "Open analysis panel" });
  if (await toggle.isVisible()) {
    await toggle.click();
    await page.waitForTimeout(600);
  }
  await page.screenshot({ path: shot("chat-analysis"), fullPage: true });
});
