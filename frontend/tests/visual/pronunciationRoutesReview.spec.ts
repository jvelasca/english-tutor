import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { ensureProfile } from "./gateHelper";

/**
 * Pronunciation read-aloud A1→C2 (V3.9): captura de revisión de la página
 * única APRENDER → Pronunciation con mock de red determinista.
 *
 * Misma arquitectura que Speaking: el escenario de práctica (frase modelo a
 * leer en voz alta + grabación) vive arriba y, bajo él, el mapa de rutas A1–C2
 * con anillos y el panel del nivel (Repetir fallidas / Repasar aprendidas /
 * Demostrar el nivel). La evaluación es determinista: se mockea el micrófono y
 * el MediaRecorder y el POST de intento devuelve un score fonético fijo.
 *  - GET /api/pronunciation/routes/stats → ruta A1 en marcha (5/6 dominadas,
 *    1 fallada); A2–C2 sin empezar.
 *  - GET /api/pronunciation/routes/items → coherente con las stats.
 *  - GET /api/pronunciation/routes/question → frase modelo de A1.
 *  - POST /api/pronunciation/routes/attempt → resultado determinista.
 *  - GET /api/academy/speaking/level → sin examen: "no oral exam taken yet".
 * Solo se ejecuta en desktop.
 */

const BANK: Record<string, number> = { A1: 6, A2: 6, B1: 5, B2: 4, C1: 3, C2: 3 };

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
    checkpoint_required: 1,
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

/** Frase modelo de A1 servida por GET /question. */
const PHRASE_A1 = {
  id: "pr-A1-0005",
  level: "A1",
  script: "I would like a cup of coffee, please.",
  topic: "Food",
  difficulty: 1,
  difficulty_vector: { lexical: 1, grammar: 1, length: 1, prosody: 1 },
};

function masteredA1() {
  return {
    level: "A1",
    total: BANK.A1,
    mastered: 5,
    completed: false,
    coverage_pct: 83,
    accuracy: 65,
    gate: gateFor("A1", 5, 83),
    state: "developing",
  };
}

const SCRIPTS_A1 = [
  "Hello, nice to meet you.",
  "My name is Lisa and I am a student.",
  "I get up at seven o'clock every day.",
  "This is my new phone.",
  "I live in a small flat in the city.",
  "I would like a cup of coffee, please.",
];

function itemsA1() {
  const base = (i: number, state: string) => ({
    phrase_id: `pr-A1-000${i + 1}`,
    level: "A1",
    script: SCRIPTS_A1[i],
    topic: "Food",
    difficulty: 1,
    attempts: state === "mastered" ? 2 : 1,
    state,
  });
  return {
    level: "A1",
    total: BANK.A1,
    mastered: 5,
    failed: 1,
    unseen: 0,
    completed: false,
    gate: gateFor("A1", 5, 83),
    items: [
      base(5, "failed"),
      base(0, "mastered"),
      base(1, "mastered"),
      base(2, "mastered"),
      base(3, "mastered"),
      base(4, "mastered"),
    ],
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
  phrase_id: PHRASE_A1.id,
  level: "A1",
  script: PHRASE_A1.script,
  heard: "I would like a cup of coffee please",
  score: 92,
  grade: "good",
  passed: true,
  word_accuracy: 100,
  phonetic_score: 95,
  phoneme_accuracy_proxy: 90,
  prosody_proxy: 85,
  pronunciation_source: "transcript",
  breakdown: {
    correct: ["I", "would", "like", "a", "cup", "of", "coffee"],
    missing: [],
    extra: [],
    substituted: [],
    total: 7,
  },
  phoneme_breakdown: {
    correct: [],
    missing: [],
    extra: [],
    substituted: [],
    total: 0,
  },
  fluency: { word_count: 8, duration_seconds: 3, wpm: 160, level: "good" },
  topic: "Food",
  difficulty: 1,
};

/** Micrófono falso + MediaRecorder determinista para poder grabar sin hardware. */
async function installFakeMedia(page: Page) {
  await page.addInitScript(() => {
    Object.defineProperty(window.navigator, "mediaDevices", {
      configurable: true,
      value: {
        ...window.navigator.mediaDevices,
        getUserMedia: async () => new MediaStream(),
      },
    });
    const FakeRecorder = class {
      static isTypeSupported(_type?: string) {
        return true;
      }
      mimeType = "audio/webm";
      state: "inactive" | "recording" | "paused" = "inactive";
      ondataavailable: ((e: BlobEvent) => void) | null = null;
      onstop: (() => void) | null = null;
      constructor(_stream: MediaStream, options?: MediaRecorderOptions) {
        if (options?.mimeType) this.mimeType = options.mimeType;
      }
      start() {
        this.state = "recording";
        window.setTimeout(() => {
          this.ondataavailable?.({
            data: new Blob(["fake-audio"], { type: this.mimeType }),
          } as BlobEvent);
        }, 20);
      }
      stop() {
        this.state = "inactive";
        window.setTimeout(() => this.onstop?.(), 40);
      }
      pause() {
        this.state = "paused";
      }
      resume() {
        this.state = "recording";
      }
      requestData() {
        /* no-op */
      }
    };
    Object.defineProperty(window, "MediaRecorder", {
      configurable: true,
      writable: true,
      value: FakeRecorder,
    });
  });
}

async function installMocks(page: Page) {
  await page.route("**/api/pronunciation/routes/stats*", (route) =>
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
  await page.route("**/api/pronunciation/routes/items*", (route) =>
    route.fulfill({ json: itemsA1() }),
  );
  await page.route("**/api/pronunciation/routes/question*", (route) =>
    route.fulfill({ json: PHRASE_A1 }),
  );
  // Intento read-aloud (POST): resultado determinista.
  await page.route("**/api/pronunciation/routes/attempt*", (route) => {
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

test("capturar Pronunciation read-aloud: página única + score fonético (mock)", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Solo desktop");

  const project = testInfo.project.name;
  const shot = (name: string) =>
    path.join("tests", "visual", "screenshots", project, `${name}.png`);
  const nav = () => page.getByRole("navigation", { name: "Main navigation" });

  await installFakeMedia(page);
  await page.goto("/");
  await ensureProfile(page);
  await expect(nav()).toBeVisible({ timeout: 15_000 });

  await installMocks(page);
  await page.goto("/#/aprender/pronunciacion");
  await expect(nav()).toBeVisible({ timeout: 15_000 });

  // Escenario superior (siempre visible, sin sesión): la frase modelo pide
  // leerla en voz alta y el mapa honesto queda bajo ella.
  await expect(page.getByText(PHRASE_A1.script, { exact: false }).first()).toBeVisible(
    { timeout: 15_000 },
  );
  await expect(page.getByText("Read this phrase aloud").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Record" })).toBeVisible();

  // Mapa de rutas: A1 desplegada por defecto con el panel (Repetir fallidas /
  // Repasar aprendidas / Demostrar nivel) y "no oral exam taken yet".
  await expect(page.getByText("Mastered 5 of 6").first()).toBeVisible({
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

  await page.waitForTimeout(600);
  await page.screenshot({ path: shot("pronunciation-routes-map"), fullPage: true });

  // Lanzar "Repetir fallidas": la sesión vive en la MISMA página.
  await page.getByRole("button", { name: "Repeat failed (1)" }).click();
  await expect(page.getByText("Repeating failed phrases")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(PHRASE_A1.script, { exact: false }).first()).toBeVisible();

  await page.waitForTimeout(500);
  await page.screenshot({ path: shot("pronunciation-route-practice"), fullPage: true });

  // Lectura hablada → score fonético determinista con desglose de métricas.
  await page.getByRole("button", { name: "Record" }).click();
  await expect(page.getByRole("button", { name: "Stop" })).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("button", { name: "Stop" }).click();
  await expect(page.getByText(/92\/100/).first()).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText("Word accuracy").first()).toBeVisible();
  await expect(
    page.getByText(ATTEMPT_OK.heard, { exact: false }).first(),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue" })).toBeVisible();

  await page.waitForTimeout(500);
  await page.screenshot({ path: shot("pronunciation-score"), fullPage: true });
});
