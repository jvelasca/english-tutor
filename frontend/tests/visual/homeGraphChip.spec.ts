import { test, expect, type Page } from "@playwright/test";
import path from "node:path";

/**
 * Cobertura visual de la región del grafo tocada en V3.17/V3.18 (D7.3):
 *
 * - H5: el chip del factor limitante de un paso con `limiting_factor.id =
 *   "transfer"` muestra la etiqueta humana ("Transfer") en la fila del plan de
 *   Today, nunca el id en crudo.
 *
 * El mock de red es determinista (mismo contrato que TodayPlan.test.tsx): se
 * interceptan `student-model`, `session`, `goal` y `next-best`; el backend no
 * interviene. El perfil se auto-selecciona mockeando `/api/users` con un único
 * usuario (patrón de `gateHelper.ts`).
 */
const VISUAL_TESTER = { id: "u-visual-graph", name: "Visual Tester" };

const GOAL = {
  goal_type: "general",
  minutes_per_day: 30,
  days_per_week: 5,
  target_level: "B1",
};

const MODEL = {
  level_id: "a1",
  current_level: "A1",
  estimated_level: "A1",
  estimated_numeric: 1,
  confidence: 0.5,
  target_level: "B1",
  skills: [],
  critical_skills: [],
  readiness: {
    target_level: "B1",
    skills: [],
    overall: 55,
    blocking_skills: [],
    ready: false,
    band: "emerging",
  },
  reassessment: null,
  mastery: [],
};

/** Sesión con un paso `new` cuyo nodo declara `transfer` como limiting factor. */
const SESSION = {
  total_minutes: 30,
  review_count: 0,
  practice_count: 1,
  items: [
    {
      kind: "new",
      step_key: "new-a1-m01-u01-l01-o01",
      skill: "vocabulary",
      subskill: null,
      objective_id: "a1-m01-u01-l01-o01",
      level_id: "a1",
      skills: ["vocabulary"],
      title: "Greetings",
      reason: "next in path",
      minutes: 30,
      can_do: "I can greet people politely.",
      limiting_factor: { id: "transfer", score: 0.3, missing: false },
      graph_mastery: 0.3,
      because: ["Transfer is the limiting factor of this can-do."],
    },
  ],
};

async function mockGraphHome(page: Page) {
  // Perfil único → la app lo auto-selecciona y la ProfileGate no aparece.
  await page.route("**/api/users", (route) => {
    if (route.request().method() === "GET") {
      void route.fulfill({ json: [VISUAL_TESTER] });
    } else {
      void route.continue();
    }
  });
  const get = (url: string, data: unknown) =>
    page.route(`**${url}`, (route) => {
      if (route.request().method() === "GET") {
        void route.fulfill({ json: data });
      } else {
        void route.continue();
      }
    });
  await get("/api/academy/student-model*", MODEL);
  await get("/api/academy/session*", SESSION);
  await get("/api/academy/goal*", GOAL);
  // Sin siguiente mejor actividad: evita el bloque de `NextBestCard`.
  await get("/api/academy/next-best*", null);
}

test("H5: el chip del factor limitante muestra la etiqueta humana de la dimensión", async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name;
  const shot = (name: string) =>
    path.join("tests", "visual", "screenshots", project, `${name}.png`);

  await mockGraphHome(page);
  await page.goto("/");

  await expect(
    page.getByRole("navigation", { name: "Main navigation" }),
  ).toBeVisible({ timeout: 15_000 });

  // El can-do del nodo y el chip con la etiqueta de la dimensión no-skill.
  await expect(
    page.getByText("I can greet people politely."),
  ).toBeVisible({ timeout: 15_000 });
  const chip = page.locator('span[role="note"]');
  await expect(chip).toContainText("Transfer");
  await expect(chip).not.toContainText(": transfer ·");
  await expect(chip).toContainText("30%");

  await page.screenshot({ path: shot("home-graph-chip"), fullPage: true });
});
