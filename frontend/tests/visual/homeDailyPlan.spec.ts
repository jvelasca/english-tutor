import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { mockIdentitySession } from "./gateHelper";

/**
 * Cobertura visual de V3.90 (plan diario) en INICIO, en los 3 breakpoints.
 *
 * Qué se comprueba, y por qué así:
 * - la barra «Today's goal» publica el porcentaje del plan y su `aria-valuenow`
 *   coincide con el número pintado (una sola fuente: el `/daily-plan` que lee
 *   Home y reparte a la barra del encabezado y a la lista de pasos);
 * - los minutos del plan se declaran **estimación del motor** y nunca como
 *   cronómetro (honestidad de la métrica);
 * - los repasos pendientes se desglosan por origen (FSRS / cola de Listening):
 *   sumar a ciegas es lo que este desglose evita;
 * - con un acierto del 75% y 3 unidades hechas, el día se declara cumplido y no
 *   se lista trabajo nuevo.
 *
 * El backend no interviene: el mock sirve el MISMO contrato que
 * `TodayPlan.test.tsx` y que `GET /api/academy/daily-plan`.
 */
const VISUAL_TESTER = { id: "u-visual-plan", name: "Visual Tester" };

const GOAL = {
  goal_type: "general",
  minutes_per_day: 30,
  days_per_week: 5,
  target_level: "B1",
  plan_mode: "mixed",
  target_units: 4,
  max_new: 1,
  include_listening: true,
  include_speaking: true,
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

const PROFILE = {
  user_id: VISUAL_TESTER.id,
  current_level: "A1",
  estimated_level: "A1",
  target_level: "B1",
  skills: [],
};

const SESSION = {
  total_minutes: 0,
  review_count: 0,
  practice_count: 0,
  items: [],
};

/** Día cumplido: 3/3 unidades, 30/30 min, 5 repasos pendientes de dos orígenes. */
const DAILY_PLAN = {
  goal: GOAL,
  plan_mode: "mixed",
  minutes_target: 30,
  units_target: 3,
  units_remaining: 0,
  minutes_remaining: 0,
  include_listening: true,
  include_speaking: true,
  pending: { fsrs: 3, listening: 2, total: 5 },
  progress: {
    units_done: 3,
    units_target: 3,
    minutes_done: 30,
    minutes_target: 30,
    units_ratio: 1,
    minutes_ratio: 1,
    percent: 1,
    done: true,
  },
  metrics: {
    day: "2026-09-29",
    units: 3,
    unknown_units: 0,
    minutes: 30,
    reviews: 2,
    new: 1,
    listening: 1,
    practice: 3,
    speaking: 0,
    listening_attempts: 4,
    listening_accuracy: 0.5,
    accuracy: 0.75,
    by_kind: { review: 2, new: 1 },
    by_skill: { vocabulary: 2, listening: 1 },
  },
  session: SESSION,
};

async function mockDailyPlanHome(page: Page) {
  await page.route("**/api/users", (route) => {
    if (route.request().method() === "GET") {
      void route.fulfill({ json: [VISUAL_TESTER] });
    } else {
      void route.continue();
    }
  });
  await mockIdentitySession(page, VISUAL_TESTER);
  const get = (url: string, data: unknown) =>
    page.route(`**${url}`, (route) => {
      if (route.request().method() === "GET") {
        void route.fulfill({ json: data });
      } else {
        void route.continue();
      }
    });
  await get("/api/academy/student-model*", MODEL);
  await get("/api/academy/daily-plan*", DAILY_PLAN);
  await get("/api/profile", PROFILE);
  await get("/api/academy/next-best*", null);
}

test("V3.90: la barra del objetivo del día publica progreso, repasos por origen y estimación", async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name;
  const shot = (name: string) =>
    path.join("tests", "visual", "screenshots", project, `${name}.png`);

  await mockDailyPlanHome(page);
  await page.goto("/");

  await expect(
    page.getByRole("navigation", { name: "Main navigation" }),
  ).toBeVisible({ timeout: 15_000 });

  // La barra del plan y su número son el mismo dato.
  const planBar = page.getByRole("progressbar", { name: "Today's goal" });
  await expect(planBar).toBeVisible({ timeout: 15_000 });
  await expect(planBar).toHaveAttribute("aria-valuenow", "100");
  await expect(page.getByTestId("goal-progress-pct")).toHaveText("100%");

  // El encabezado de Home repite el porcentaje del MISMO plan (no una segunda lectura).
  await expect(page.getByTestId("home-goal-progress")).toContainText("100%");

  // Repasos pendientes con origen: 5 en total, 3 de FSRS y 2 de la cola de Listening.
  await expect(page.getByText("Pending reviews: 5")).toBeVisible();
  await expect(page.getByText("(3 FSRS, 2 Listening)")).toBeVisible();

  // Los minutos se presentan como estimación del motor, no como cronómetro.
  await expect(page.getByText("engine estimate")).toBeVisible();
  await expect(page.getByText("Today's accuracy: 75%")).toBeVisible();

  // Objetivo cumplido: no se lista trabajo nuevo.
  await expect(page.getByText("Today's goal is met")).toBeVisible();

  await page.screenshot({ path: shot("home-daily-plan"), fullPage: true });
});
