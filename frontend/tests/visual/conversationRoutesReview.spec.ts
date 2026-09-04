import { test, expect } from "@playwright/test";
import path from "node:path";
import { ensureProfile } from "./gateHelper";

/**
 * Conversation guiada A1→C2 (V3.10): captura de revisión de la página única
 * APRENDER → Conversation con mock de red determinista.
 *
 * Misma arquitectura que Speaking/Pronunciation: el escenario de práctica (el
 * mini-diálogo guiado multi-turno con el tutor) vive arriba y, bajo él, el mapa
 * de rutas A1–C2 con anillos y el panel del nivel (Repetir fallidos / Repasar
 * aprendidos / Demostrar el nivel). La conversación usa el chat del tutor vía
 * SSE: se mockea el stream para no depender del LLM local.
 *  - GET /api/conversation/routes/stats → ruta A1 en marcha (5/11 dominados,
 *    1 fallado); A2–C2 sin empezar.
 *  - GET /api/conversation/routes/items → coherente con las stats.
 *  - GET /api/conversation/routes/question → diálogo guiado de A1.
 *  - POST /api/conversations + PUT /api/conversations/{id} → conversación real.
 *  - POST /api/chat/stream → respuestas del tutor (SSE determinista).
 *  - POST /api/conversation/routes/attempt → resultado por criterios.
 *  - GET /api/academy/speaking/level → sin examen: "no oral exam taken yet".
 * Solo se ejecuta en desktop.
 */

const BANK: Record<string, number> = {
  A1: 11,
  A2: 11,
  B1: 11,
  B2: 11,
  C1: 11,
  C2: 11,
};

function gateFor(level: string, mastered: number, coveragePct: number) {
  return {
    passed: mastered >= BANK[level],
    total: BANK[level],
    mastered,
    coverage_pct: coveragePct,
    coverage_required_pct: 80,
    accuracy: mastered > 0 ? 65 : null,
    accuracy_required: 70,
    topics: mastered > 0 ? 4 : 0,
    topics_required: 3,
    checkpoint: 1,
    checkpoint_required: 2,
    blockers:
      mastered >= BANK[level]
        ? ["accuracy"]
        : mastered > 0
          ? ["coverage"]
          : ["coverage"],
  };
}

function emptyLevel(level: string) {
  const total = BANK[level];
  return {
    level,
    total,
    mastered: 0,
    completed: false,
    coverage_pct: 0,
    accuracy: null,
    gate: gateFor(level, 0, 0),
    state: "not_started",
  };
}

/** Diálogo guiado de A1 servido por GET /question. */
const DIALOGUE_A1 = {
  id: "cv-A1-0005",
  level: "A1",
  topic: "Introductions",
  context:
    "You arrive at your first English lesson and sit next to a student you do not know.",
  student_role: "A new student in an English class.",
  tutor_role: "A friendly classmate sitting next to you.",
  opening_line: "Hi! I am Tom. What is your name?",
  communicative_goals: [
    "Say hello and give your name",
    "Say where you are from",
    "Ask his name again politely if you do not hear it",
  ],
};

function masteredA1() {
  return {
    level: "A1",
    total: BANK.A1,
    mastered: 5,
    completed: false,
    coverage_pct: 45,
    accuracy: 65,
    gate: gateFor("A1", 5, 45),
    state: "developing",
  };
}

function itemsA1() {
  const base = (i: number, state: string) => ({
    dialogue_id: `cv-A1-000${i + 1}`,
    level: "A1",
    opening_line: `Opening line ${i + 1}.`,
    topic: "Introductions",
    attempts: state === "mastered" ? 2 : 1,
    state,
  });
  const states = ["failed", "mastered", "mastered", "mastered", "mastered", "mastered"];
  const items = states.map((s, i) => base(i, s));
  for (let i = 6; i < BANK.A1; i++) items.push(base(i, "unseen"));
  return {
    level: "A1",
    total: BANK.A1,
    mastered: 5,
    failed: 1,
    unseen: 5,
    completed: false,
    gate: gateFor("A1", 5, 45),
    items,
  };
}

function emptySpeakingLevel() {
  return {
    level: null,
    numeric: null,
    score: null,
    confidence: 0,
    attempts: 0,
  };
}

const ATTEMPT_OK = {
  dialogue_id: DIALOGUE_A1.id,
  level: "A1",
  opening_line: DIALOGUE_A1.opening_line,
  heard: "Hello Tom, I am Alex. I am from Madrid. Nice to meet you!",
  overall: 0.85,
  passed: true,
  criteria: {
    content: 0.9,
    vocabulary: 0.8,
    grammar: 0.75,
    fluency: 0.85,
    pronunciation: 0.8,
    interaction: 0.9,
  },
  observed: {
    content: true,
    vocabulary: true,
    grammar: true,
    fluency: true,
    pronunciation: true,
    interaction: true,
  },
  topic: DIALOGUE_A1.topic,
  communicative_goals: DIALOGUE_A1.communicative_goals,
};

/** Respuesta determinista del tutor (chat por SSE). */
const SSE_REPLY =
  "data: {\"content\": \"Nice to meet you, Alex!\"}\n\n" +
  "data: {\"content\": \" Where are you from?\"}\n\n" +
  'data: {"done": true}\n\n';

async function installMocks(page: import("@playwright/test").Page) {
  await page.route("**/api/conversation/routes/stats*", (route) =>
    route.fulfill({
      json: {
        attempts: 6,
        passed: 5,
        accuracy: 83,
        level: "A1",
        completed: false,
        levels: [
          masteredA1(),
          emptyLevel("A2"),
          emptyLevel("B1"),
          emptyLevel("B2"),
          emptyLevel("C1"),
          emptyLevel("C2"),
        ],
      },
    }),
  );
  await page.route("**/api/academy/speaking/level*", (route) =>
    route.fulfill({ json: emptySpeakingLevel() }),
  );
  await page.route("**/api/conversation/routes/items*", (route) =>
    route.fulfill({ json: itemsA1() }),
  );
  await page.route("**/api/conversation/routes/question*", (route) =>
    route.fulfill({ json: DIALOGUE_A1 }),
  );
  // Conversación real: crear y guardar (id estable para el intento).
  await page.route("**/api/conversations*", (route) => {
    if (route.request().method() === "POST") {
      route.fulfill({
        json: {
          id: "conv-guiada-1",
          title: "Guided A1",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          user_id: "test-user",
        },
      });
    } else if (route.request().method() === "PUT") {
      route.fulfill({
        json: {
          id: "conv-guiada-1",
          title: "Guided A1",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          user_id: "test-user",
        },
      });
    } else {
      route.fulfill({ json: [] });
    }
  });
  // Respuestas del tutor en el mini-diálogo (SSE determinista).
  await page.route("**/api/chat/stream*", (route) => {
    if (route.request().method() === "POST") {
      route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: SSE_REPLY,
      });
    } else {
      route.continue();
    }
  });
  // Intento de conversación (POST): resultado por criterios.
  await page.route("**/api/conversation/routes/attempt*", (route) => {
    if (route.request().method() === "POST") {
      route.fulfill({ json: ATTEMPT_OK });
    } else {
      route.continue();
    }
  });
  await page.route("**/api/voices*", (route) =>
    route.fulfill({
      json: {
        voices: [],
        downloadable: [],
        default: "en_GB-alan-medium",
        selected: "en_GB-alan-medium",
      },
    }),
  );
}

test("capturar Conversation guiada: página única + conversación puntuada (mock)", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Solo desktop");

  const project = testInfo.project.name;
  const shot = (name: string) =>
    path.join("tests", "visual", "screenshots", project, `${name}.png`);
  const nav = () => page.getByRole("navigation", { name: "Main navigation" });

  await page.goto("/");
  await ensureProfile(page);
  await expect(nav()).toBeVisible({ timeout: 15_000 });

  await installMocks(page);
  await page.goto("/#/aprender/conversar");
  await expect(nav()).toBeVisible({ timeout: 15_000 });

  // Escenario superior: el diálogo guiado muestra la situación, los roles y la
  // línea de apertura del tutor; el mapa honesto queda bajo él.
  await expect(
    page.getByText(DIALOGUE_A1.opening_line, { exact: false }).first(),
  ).toBeVisible({ timeout: 15_000 });
  await expect(
    page.getByText(DIALOGUE_A1.context, { exact: false }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Finish and score" }),
  ).toBeVisible();

  // Mapa de rutas: A1 desplegada por defecto con el panel y "no oral exam yet".
  await expect(page.getByText("Mastered 5 of 11").first()).toBeVisible({
    timeout: 15_000,
  });
  await expect(
    page.getByRole("button", { name: "Repeat failed (1)" }),
  ).toBeVisible({ timeout: 15_000 });
  await expect(
    page.getByRole("button", { name: "Review learned (5)" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Take the Speaking Assessment" }),
  ).toBeVisible();
  await expect(
    page.getByText("No oral exam taken yet", { exact: false }).first(),
  ).toBeVisible();
  // El chat libre queda accesible desde la propia página.
  await expect(
    page.getByRole("button", { name: "Open free chat" }),
  ).toBeVisible();

  await page.waitForTimeout(600);
  await page.screenshot({ path: shot("conversation-routes-map"), fullPage: true });

  // Conversa el mini-diálogo con el tutor (3 turnos del alumno): cada envío
  // dispara una respuesta SSE determinista del tutor en personaje.
  const input = page.getByPlaceholder("Write your answer…");
  for (const line of [
    "Hello Tom! My name is Alex.",
    "I am from Madrid, in Spain.",
    "Nice to meet you! Sorry, what was your name again?",
  ]) {
    await input.fill(line);
    await input.press("Enter");
    await expect(page.getByText("Nice to meet you, Alex!").first()).toBeVisible({
      timeout: 15_000,
    });
  }
  await expect(page.getByRole("button", { name: "Finish and score" })).toBeEnabled({
    timeout: 15_000,
  });

  await page.waitForTimeout(400);
  await page.screenshot({ path: shot("conversation-guided-chat"), fullPage: true });

  // Terminar la conversación → se evalúa el transcripto (LLM+interacción) y se
  // muestra el resultado por criterios con la nota honesta.
  await page.getByRole("button", { name: "Finish and score" }).click();
  await expect(page.getByText(/Conversation scored/).first()).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("Goals reached").first()).toBeVisible();
  await expect(page.getByText("content", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Interaction", { exact: true }).first()).toBeVisible();
  await expect(
    page.getByText(ATTEMPT_OK.heard, { exact: false }).first(),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue" })).toBeVisible();

  await page.waitForTimeout(500);
  await page.screenshot({ path: shot("conversation-score"), fullPage: true });
});
