import { test, expect } from "@playwright/test";

/**
 * Speaking 2.0 en MI PROGRESO (V3.1): el contenido que vivía en la pestaña
 * "Speaking" del antiguo panel Analysis ahora se muestra en `#/progreso` →
 * pestaña "Tracks" (Recorridos) → sub-pestaña "Speaking". Verifica que el
 * diagnóstico renderiza la insignia "proxy" de pronunciación, el desglose de
 * Interaction Quality y los hitos de Conversation Endurance. Se mockea la API
 * con `page.route` para obtener datos deterministas sin depender de evidencia
 * real en la BD (el resto de llamadas degradan sin romper la pantalla).
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
  // Un único usuario para que la app lo auto-seleccione y el shell de pestañas
  // de MI PROGRESO se renderice aunque el resto de llamadas falle.
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

/** Abre MI PROGRESO → pestaña "Tracks" → sub-pestaña "Speaking". */
async function openSpeakingTrack(
  page: import("@playwright/test").Page,
): Promise<import("@playwright/test").Locator> {
  await page.goto("/#/progreso");

  // Pestaña de progreso "Tracks" (progress.tracksTab = en "Tracks").
  const progressTabs = page.getByRole("tablist", {
    name: "Progress sections",
  });
  await expect(progressTabs).toBeVisible({ timeout: 15_000 });
  await progressTabs
    .getByRole("tab", { name: "Tracks", exact: true })
    .click();

  // Sub-pestañas de Recorridos: "Speaking" (skill.speaking = en "Speaking").
  const tracks = page.getByRole("tablist", { name: "Tracks" });
  await expect(tracks).toBeVisible({ timeout: 15_000 });
  await tracks.getByRole("tab", { name: "Speaking", exact: true }).click();

  // Sección que agrupa SpeakingDiagnostic + SpeakingPanel (panels.speaking).
  const section = page.getByRole("region", { name: "Speaking", exact: true });
  await expect(section).toBeVisible({ timeout: 15_000 });
  return section;
}

test("desktop: Speaking 2.0 muestra proxy, Interaction Quality y Endurance", async ({
  page,
}) => {
  test.skip(page.viewportSize()!.width < 1024, "Solo desktop");

  await mockApi(page);
  const section = await openSpeakingTrack(page);

  // Insignia "proxy" en el criterio de pronunciación (diag.proxy).
  await expect(section.getByText("proxy", { exact: true })).toBeVisible({
    timeout: 15_000,
  });

  // Desglose de Interaction Quality (título + sub-dimensiones).
  await expect(section.getByText("Interaction quality")).toBeVisible();
  await expect(section.getByText("Initiation")).toBeVisible();
  await expect(section.getByText("Follow-up")).toBeVisible();
  await expect(section.getByText("Turn-taking")).toBeVisible();

  // Conversation Endurance (título + turnos + hitos).
  await expect(section.getByText("Conversation endurance")).toBeVisible();
  await expect(section.getByText(/spoken turns/)).toBeVisible();
  await expect(section.getByText("30s", { exact: true })).toBeVisible();
  await expect(section.getByText("3m 0s", { exact: true })).toBeVisible();
});
