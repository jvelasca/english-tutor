import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { ensureProfile } from "./gateHelper";

/**
 * Speaking por micro-conversaciones A1→C2 (V3.8): captura de revisión de la
 * página única APRENDER → Speaking con mock de red determinista.
 *
 * La página deja de tener sesión a pantalla completa: el escenario de práctica
 * (tarjeta de micro-conversación guiada: situación + rol + línea del
 * interlocutor + grabación) vive arriba y, bajo él, el mapa de rutas A1–C2 con
 * anillos y el panel del nivel (Repetir fallidas / Repasar aprendidas /
 * Demostrar el nivel). Para revelar la respuesta modelo se simula el
 * micrófono y el MediaRecorder con init-scripts y se mockea el POST de
 * intento (pipeline de respuesta abierta).
 *  - GET /api/speaking/stats  → ruta A1 en marcha (5/6 dominadas, 1 fallada),
 *    puerta sin pasar por precisión; A2–C2 sin empezar.
 *  - GET /api/speaking/items  → coherente con las stats (5 mastered, 1 failed).
 *  - GET /api/speaking/question → una tarjeta de intercambio de A1 (sin la
 *    respuesta modelo: se revela tras responder).
 *  - POST /api/speaking/attempt → resultado determinista con criterios y
 *    respuesta modelo.
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
    base_total: total,
    base_mastered: 0,
    extras: 0,
    extras_mastered: 0,
  };
}

/** Tarjeta de micro-conversación de A1 servida por GET /question. */
const CARD_A1 = {
  id: "mc-a1-06",
  level: "A1",
  setup: "You are at a small cafe with a friend.",
  you: "Greet your friend and order something to drink.",
  app_line: "Hi! What would you like to drink?",
  topic: "food_and_drink",
  difficulty: 1,
  difficulty_vector: { lexical: 1, grammar: 1, length: 1, discourse: 1 },
  audio_ready: false,
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
    base_total: BANK.A1,
    base_mastered: 5,
    extras: 0,
    extras_mastered: 0,
  };
}

const LINES_A1 = [
  "Do you like living in this city?",
  "Where do you work?",
  "Could you pass me the salt, please?",
  "We went to the beach last summer.",
  "He doesn't like coffee at all.",
  "Hi! What would you like to drink?",
];

function itemsA1() {
  const base = (i: number, state: string) => ({
    phrase_id: `mc-a1-0${i + 1}`,
    level: "A1",
    app_line: LINES_A1[i],
    topic: "food_and_drink",
    difficulty: 1,
    attempts: state === "mastered" ? 2 : 1,
    state,
    source: "base",
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
  phrase_id: CARD_A1.id,
  level: "A1",
  app_line: CARD_A1.app_line,
  heard: "I would like a coffee please and maybe a cake with it",
  model_response: "Yes! I would love a coffee, please. Thank you.",
  overall: 0.87,
  passed: true,
  topic: "food_and_drink",
  difficulty: 1,
  criteria: {
    task_achievement: 0.9,
    grammatical_control: 1.0,
    lexical_resource: 0.8,
    fluency: 0.85,
    coherence: 0.9,
    interaction: 0.8,
  },
  observed: {
    task_achievement: true,
    grammatical_control: true,
    lexical_resource: true,
    fluency: true,
    coherence: true,
    interaction: true,
  },
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
  await page.route("**/api/speaking/stats*", (route) =>
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
  await page.route("**/api/speaking/items*", (route) =>
    route.fulfill({ json: itemsA1() }),
  );
  await page.route("**/api/speaking/question*", (route) =>
    route.fulfill({ json: CARD_A1 }),
  );
  // Intento de respuesta abierta (POST): resultado determinista.
  await page.route("**/api/speaking/attempt*", (route) => {
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

test("capturar Speaking por micro-conversaciones: página única + respuesta modelo (mock)", async ({
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
  await page.goto("/#/aprender/speaking");
  await expect(nav()).toBeVisible({ timeout: 15_000 });

  // Escenario superior (siempre visible, sin sesión): la tarjeta de
  // micro-conversación guiada está arriba y pide responder en voz alta.
  await expect(page.getByText(CARD_A1.app_line).first()).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText("Interlocutor").first()).toBeVisible();
  await expect(page.getByText(CARD_A1.setup, { exact: false }).first()).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Record your answer" }),
  ).toBeVisible();

  // Mapa honesto bajo el escenario: A1 desplegada por defecto con su anillo y
  // el panel de ruta (Repetir fallidas / Repasar aprendidas / Demostrar nivel).
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
  // La ruta no certifica: sin examen aún, la cabecera lo lee "no oral exam
  // taken yet" y ningún nivel muestra insignia de "demostrado".
  await expect(
    page.getByText("No oral exam taken yet", { exact: false }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Demonstrated/ }).first(),
  ).toHaveCount(0);

  await page.waitForTimeout(600);
  await page.screenshot({ path: shot("speaking-routes-map"), fullPage: true });

  // Lanzar "Repetir fallidas": la sesión vive en la MISMA página (sin pantalla
  // separada): el escenario sigue arriba con la tarjeta del drill y la barra
  // compacta de sesión; el mapa queda bajo ella, deshabilitado durante la sesión.
  await page.getByRole("button", { name: "Repeat failed (1)" }).click();
  await expect(page.getByText("Repeating failed cards")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(CARD_A1.app_line).first()).toBeVisible();
  await expect(page.getByText("Mastered 5 of 6").first()).toBeVisible();

  await page.waitForTimeout(500);
  await page.screenshot({ path: shot("speaking-route-practice"), fullPage: true });

  // Respuesta hablada → evaluación con el pipeline de respuesta abierta:
  // se revelan las barras por criterios y la respuesta modelo (con voz).
  await page.getByRole("button", { name: "Record your answer" }).click();
  await expect(page.getByRole("button", { name: "Stop" })).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("button", { name: "Stop" }).click();
  await expect(page.getByText("Model answer").first()).toBeVisible({
    timeout: 15_000,
  });
  await expect(
    page.getByText(ATTEMPT_OK.model_response, { exact: false }).first(),
  ).toBeVisible();
  await expect(page.getByText("Feedback by criteria", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue" })).toBeVisible();

  await page.waitForTimeout(500);
  await page.screenshot({ path: shot("speaking-model-answer"), fullPage: true });
});
