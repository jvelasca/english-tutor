import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { ensureProfile } from "./gateHelper";

/**
 * Captura de revisión del panel de ruta dominada con práctica extra (V3.6).
 *
 * Usa un mock de red determinista (no depende del estado real del perfil):
 *  - GET /api/listening/stats  → ruta A1 con su banco oficial (205) dominado y
 *    25 ítems extra activados ("Dominadas 207 de 230", desglose "205 oficiales
 *    · +25 extra"); el resto de rutas sin progreso.
 *  - GET /api/listening/items  → A1 coherente con las stats (205 base dominadas
 *    + 2 generadas dominadas + 23 generadas sin ver), puerta sin pasar.
 *  - question / diagnostic / voices → objetos vacíos válidos para que la
 *    pantalla se monte sin errores.
 *
 * Objetivo: revisar visualmente que el anillo crece con las extras, que la
 * puerta/certificación no se altera (aviso honesto) y que el panel ofrece
 * "Review learned" y "Add more practice". Solo se ejecuta en desktop.
 */

const BANK: Record<string, number> = {
  A1: 205,
  A2: 206,
  B1: 33,
  B2: 29,
  C1: 20,
  C2: 20,
};

function gateFor(level: string, mastered: number, coveragePct: number) {
  return {
    passed: false,
    total: BANK[level],
    mastered,
    coverage_pct: coveragePct,
    coverage_required_pct: 100,
    accuracy: mastered > 0 ? 72 : null,
    accuracy_required: 70,
    topics: mastered > 0 ? 12 : 0,
    topics_required: 10,
    subskills: mastered > 0 ? 8 : 0,
    subskills_required: 6,
    checkpoint: 0,
    checkpoint_required: 3,
    blockers: mastered > 0 ? ["checkpoint", "accuracy"] : ["coverage"],
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
    retention: null,
    base_total: total,
    base_mastered: 0,
    extras: 0,
    extras_mastered: 0,
  };
}

function masteredA1() {
  const total = BANK.A1;
  const extras = 25;
  const extrasMastered = 2;
  return {
    level: "A1",
    total: total + extras, // 230: el denominador del anillo crece con las extras
    mastered: total + extrasMastered, // 207: base dominada + 2 generadas
    completed: false,
    coverage_pct: ((total + extrasMastered) / (total + extras)) * 100,
    accuracy: 72,
    gate: gateFor("A1", total, 100), // la puerta se ancla al banco oficial (205)
    state: "functional",
    retention: {
      retention_rate: 0.42,
      stable: false,
      long_delayed_exposures: 1,
    },
    base_total: total,
    base_mastered: total,
    extras,
    extras_mastered: extrasMastered,
  };
}

const QUIET = {
  attempts: 0,
  correct: 0,
  accuracy: null,
};

function itemsA1() {
  // 2 generadas dominadas (al principio del grupo "Mastered" para ver la
  // etiqueta "generated practice" sin hacer scroll), 205 base dominadas y 23
  // generadas sin ver. `total`/`mastered`/`unseen` coherentes con las stats.
  const baseMastered = Array.from({ length: BANK.A1 }, (_, i) => ({
    question_id: `l-a1-${String(i + 1).padStart(4, "0")}`,
    level: "A1",
    script: `Official phrase number ${i + 1}.`,
    topic: "daily_routine",
    skill: "gist",
    difficulty: 1,
    attempts: 3,
    state: "mastered",
    source: "base",
  }));
  const genMastered = Array.from({ length: 2 }, (_, i) => ({
    question_id: `g-a1-${i + 1}`,
    level: "A1",
    script: `Extra generated phrase about weekend plans, number ${i + 1}.`,
    topic: "free_time",
    skill: "detail",
    difficulty: 1,
    attempts: 2,
    state: "mastered",
    source: "generated",
  }));
  const genUnseen = Array.from({ length: 23 }, (_, i) => ({
    question_id: `g-a1-u${i + 1}`,
    level: "A1",
    script: `Extra generated unseen phrase ${i + 1} for extra listening practice.`,
    topic: "free_time",
    skill: "gist",
    difficulty: 1,
    attempts: 0,
    state: "unseen",
    source: "generated",
  }));
  return {
    level: "A1",
    total: 230,
    mastered: 207,
    failed: 0,
    unseen: 23,
    completed: false,
    gate: gateFor("A1", BANK.A1, 100),
    items: [...genMastered, ...baseMastered, ...genUnseen],
  };
}

function emptyDiagnostic() {
  return {
    subskills: [],
    weak: [],
    recommendation: "",
    first_pass_accuracy: null,
    automaticity: null,
    by_difficulty: [],
    by_topic: [],
    trend: { recent_accuracy: null, prior_accuracy: null, delta: null, direction: "n/a" },
    recurrence: { questions_seen: 0, retried: 0, recovered: 0, retry_rate: null, recovery_rate: null },
    retention: {
      total_questions: 0,
      immediate_accuracy: null,
      delayed_accuracy: null,
      retention_rate: null,
      by_bucket: [],
    },
    bank_version: "7.0.0",
    realization: { attempts: 0, verified: 0, gap: 0 },
    resilience: { dimensions: [], main_weakness: null, recommendation: "" },
  };
}

function emptyQuestion() {
  return {
    id: "l-a1-0001",
    level: "A1",
    skill: "gist",
    difficulty: 1,
    difficulty_vector: { clear_speech: 1 },
    script: "Where do you usually have breakfast?",
    question: "Where do you usually have breakfast?",
    options: [
      "At home with my family.",
      "At work before starting.",
      "At school with friends.",
      "I usually skip breakfast.",
    ],
    audio_id: "",
    duration: 3,
    speaker_id: "p1",
    accent: "american",
    speech_rate: 1.0,
    transcript: "Where do you usually have breakfast?",
    clean_transcript: "Where do you usually have breakfast?",
    noise_level: 0,
    repetition_policy: "no-repeat",
    topic: "daily_routine",
    context: "",
    audio_ready: false,
    audio_type: "tts",
    realized_difficulty: 1,
    realization: {},
    variants: [
      { variant: "slow", speech_rate: 0.8, label: "Slow" },
      { variant: "normal", speech_rate: 1.0, label: "Normal" },
      { variant: "fast", speech_rate: 1.15, label: "Fast" },
    ],
    default_variant: "normal",
  };
}

async function installMocks(page: Page) {
  await page.route("**/api/listening/stats*", (route) =>
    route.fulfill({
      json: {
        attempts: 210,
        correct: 155,
        accuracy: 74,
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
  await page.route("**/api/listening/items*", (route) =>
    route.fulfill({ json: itemsA1() }),
  );
  await page.route("**/api/listening/question*", (route) =>
    route.fulfill({ json: emptyQuestion() }),
  );
  await page.route("**/api/listening/diagnostic*", (route) =>
    route.fulfill({ json: emptyDiagnostic() }),
  );
  await page.route("**/api/voices*", (route) =>
    route.fulfill({
      json: { voices: [], downloadable: [], default: "es_ES-sharvard-medium", selected: "es_ES-sharvard-medium" },
    }),
  );
}

test("capturar ruta A1 dominada con práctica extra (mock)", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Solo desktop");

  const project = testInfo.project.name;
  const shot = (name: string) =>
    path.join("tests", "visual", "screenshots", project, `${name}.png`);
  const nav = () => page.getByRole("navigation", { name: "Main navigation" });

  await page.goto("/");
  await ensureProfile(page);
  await expect(nav()).toBeVisible({ timeout: 15_000 });

  await installMocks(page);
  await page.goto("/#/aprender/listening");
  await expect(nav()).toBeVisible({ timeout: 15_000 });

  // El anillo de A1 ya refleja el banco oficial dominado + extras activados.
  await expect(
    page.getByText("Mastered 207 of 230").first(),
  ).toBeVisible({ timeout: 15_000 });

  // Anillo pequeño de la ruta A1 (la lista de rutas bajo el donut "Current level").
  const ringA1 = page.getByRole("button", { name: "Level A1 history" }).nth(1);
  await ringA1.scrollIntoViewIfNeeded();
  await page.waitForTimeout(400);
  await page.screenshot({ path: shot("listening-rings-mastered") });

  // Despliega el historial de A1: panel con "Add more practice" y "Review learned".
  await ringA1.click();
  await expect(
    page.getByRole("button", { name: "Review learned (207)" }),
  ).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Add more practice to A1").first()).toBeVisible();

  // Abre el grupo "Mastered" para que se vean las filas con etiqueta generada.
  await page
    .getByRole("button", { name: "Mastered (207)" })
    .click()
    .catch(() => {
      /* el grupo ya estaba abierto */
    });
  await expect(page.getByText("generated practice").first()).toBeVisible();

  await page.waitForTimeout(600);
  await page.screenshot({ path: shot("listening-route-mastered"), fullPage: true });

  // Captura enfocada del bloque "Añadir más práctica" (desglose + aviso honesto).
  await page.getByText("Add more practice to A1").first().scrollIntoViewIfNeeded();
  await page.waitForTimeout(400);
  await page.screenshot({ path: shot("listening-add-practice") });
});
