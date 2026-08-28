import { test, expect } from "@playwright/test";

/**
 * Speaking 2.0 (V1.34): verifica que el diagnóstico de speaking renderiza la
 * insignia "proxy" de pronunciación, el desglose de Interaction Quality y los
 * hitos de Conversation Endurance. Se mockea la API con `page.route` para
 * obtener datos deterministas sin depender de evidencia real en la BD.
 */

const DIAGNOSTIC = {
  criteria: [
    {
      criterion: "pronunciation",
      attempts: 5,
      mean: 0.72,
      min: 0.5,
      max: 0.9,
      review_due: true,
      proxy: true,
    },
    {
      criterion: "fluency",
      attempts: 5,
      mean: 0.8,
      min: 0.7,
      max: 0.9,
      review_due: false,
      proxy: false,
    },
  ],
  weak: ["pronunciation"],
  recommendation: "Keep practicing connected speech.",
  attempts: 5,
  overall_mean: 0.76,
  overall_recent: 0.78,
  trend: { recent_mean: 0.78, prior_mean: 0.74, delta: 0.04, direction: "up" },
  rubric_version: "2.0",
  interaction_quality: [
    { dimension: "initiation", attempts: 4, mean: 0.7, recent_score: 0.75 },
    { dimension: "response", attempts: 4, mean: 0.8, recent_score: 0.85 },
    { dimension: "follow_up", attempts: 3, mean: 0.6, recent_score: 0.65 },
    { dimension: "repair", attempts: 3, mean: 0.55, recent_score: 0.6 },
    { dimension: "turn_taking", attempts: 4, mean: 0.75, recent_score: 0.8 },
  ],
};

const ENDURANCE = {
  milestones: [
    { seconds: 30, achieved: true },
    { seconds: 60, achieved: true },
    { seconds: 90, achieved: false },
    { seconds: 120, achieved: false },
    { seconds: 180, achieved: false },
  ],
  longest_session_seconds: 75,
  longest_turn_seconds: 20,
  total_speaking_seconds: 140,
  turns: 12,
  current_goal_seconds: 90,
};

async function mockApi(page: import("@playwright/test").Page) {
  // Un único usuario para que la app lo auto-seleccione y el diagnóstico
  // (dependiente de `user_id`) se dispare.
  await page.route("**/api/users", (route) =>
    route.fulfill({
      json: [{ id: "u1", name: "Test", created_at: "2026-01-01T00:00:00Z" }],
    }),
  );
  await page.route("**/api/academy/speaking/diagnostic*", (route) =>
    route.fulfill({ json: DIAGNOSTIC }),
  );
  await page.route("**/api/academy/speaking/endurance*", (route) =>
    route.fulfill({ json: ENDURANCE }),
  );
}

async function openSpeakingTab(page: import("@playwright/test").Page) {
  await page.goto("/");
  await expect(page.getByRole("navigation")).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(800);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Learn", exact: true })
    .click();

  const tablist = page.getByRole("tablist", { name: "Analysis" });
  await expect(tablist).toBeVisible({ timeout: 15_000 });
  await tablist
    .getByRole("tab", { name: "Speaking", exact: true })
    .click();
}

test("desktop: Speaking 2.0 muestra proxy, Interaction Quality y Endurance", async ({
  page,
}) => {
  test.skip(page.viewportSize()!.width < 1024, "Solo desktop");

  await mockApi(page);
  await openSpeakingTab(page);

  // Insignia "proxy" en el criterio de pronunciación.
  await expect(page.getByText("proxy", { exact: true })).toBeVisible({
    timeout: 15_000,
  });

  // Desglose de Interaction Quality (título + sub-dimensiones).
  await expect(page.getByText("Interaction quality")).toBeVisible();
  await expect(page.getByText("Initiation")).toBeVisible();
  await expect(page.getByText("Follow-up")).toBeVisible();
  await expect(page.getByText("Turn-taking")).toBeVisible();

  // Conversation Endurance (título + turnos + hitos).
  await expect(page.getByText("Conversation endurance")).toBeVisible();
  await expect(page.getByText(/spoken turns/)).toBeVisible();
  await expect(page.getByText("30s", { exact: true })).toBeVisible();
  await expect(page.getByText("3m 0s", { exact: true })).toBeVisible();
});
