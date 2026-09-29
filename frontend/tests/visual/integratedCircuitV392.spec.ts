import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

import { ensureProfile, mockIdentitySession } from "./gateHelper";

/**
 * Cobertura visual del CIRCUITO INTEGRADO de V3.92, en los 3 breakpoints.
 *
 * Qué se comprueba, y por qué importa:
 *
 * 1. **El fallo de Listening declara la evidencia de dificultad.** Si la frase
 *    fallada contenía palabras que el alumno YA tiene, el backend sube su
 *    dificultad de FSRS y lo devuelve en `difficulty_evidence`. La UI lo dice:
 *    es evidencia, no un repaso, y **nada se bloquea**.
 * 2. **El plan diario publica la métrica unificada del día** (`words_flagged` /
 *    `difficulty_evidence`) como línea propia, sin inflar el progreso ni los
 *    repasos pendientes. La evidencia no es trabajo hecho; decir lo contrario
 *    sería mentir con el objetivo del día.
 *
 * El mock sirve la forma EXACTA del backend: `transcript_policy`,
 * `sentence_timings` y `word_timings` en snake_case (contrato de Pydantic). Usar
 * camelCase en el mock escondería justo el fallo que se quiere vigilar: durante
 * V3.27–V3.91 esas tres claves llegaban con el nombre equivocado, así que la
 * tarjeta de fallo de V3.89 (las tres acciones) nunca se pintaba. Aquí se fija
 * contra el payload real, no contra un mock complaciente.
 */

/** Ítem receptivo con micro-flujo, tal como lo sirve `/api/listening/question`. */
const QUESTION = {
  id: "c071",
  level: "B1",
  skill: "numbers",
  difficulty: 3,
  difficulty_vector: { speed: 3 },
  script: "I'll pick you up at a quarter past eight.",
  question: "Which time did you hear?",
  options: ["8:45", "7:45", "9:15", "8:15"],
  audio_id: "",
  duration: 5,
  speaker_id: "speaker_001",
  accent: "British RP",
  speech_rate: 143,
  transcript: "I'll pick you up at a quarter past eight.",
  clean_transcript: "I'll pick you up at a quarter past eight.",
  noise_level: 0,
  repetition_policy: "twice",
  topic: "daily_routine",
  context: "message",
  // Sin audio pre-renderizado: la ruta degrada a TTS en vivo y el PLAY sigue
  // declarando «he escuchado» (es la señal, no el sonido).
  audio_ready: false,
  audio_type: "tts",
  realized_difficulty: 3,
  realization: {},
  variants: [],
  default_variant: "normal",
  // --- Contrato REAL del backend en snake_case --------------------------------
  flow: [
    {
      stage: "while1",
      task: "listen_global",
      transcript_state_inicial: "hidden",
      allow_skip: true,
      requires_audio: true,
    },
    {
      stage: "while2",
      task: "native_question",
      transcript_state_inicial: "hidden",
      allow_skip: false,
      requires_audio: true,
    },
  ],
  transcript_policy: {
    revelation: "on_first_fail",
    max_attempts_per_stage: 2,
    allow_manual_reveal: true,
    shadowing_optional: true,
  },
  sentence_timings: [
    {
      index: 0,
      start: 0,
      end: 5,
      text: "I'll pick you up at a quarter past eight.",
      sync: "coarse_heuristic",
    },
  ],
  word_timings: [],
};

/** Fallo con evidencia: la frase contenía dos palabras que el alumno ya tenía. */
const FAILURE = {
  question_id: "c071",
  correct: false,
  correct_index: 3,
  level: "B1",
  skill: "numbers",
  difficulty: 3,
  realized_difficulty: 3,
  outcome: "wrong",
  queued_for_review: true,
  immediate_retry_available: true,
  difficulty_evidence: { words: ["quarter", "eight"], count: 2 },
};

function lv(level: string, mastered: number, total: number) {
  return {
    level,
    mastered,
    total,
    base_total: total,
    extras: 0,
    completed: mastered >= total,
    state: "functional",
    retention: null,
    gate: null,
  };
}

async function mockListening(page: Page) {
  await page.route("**/api/listening/stats*", (route) =>
    route.fulfill({
      json: {
        attempts: 210,
        correct: 155,
        accuracy: 74,
        level: "B1",
        completed: false,
        levels: [
          lv("A1", 200, 200),
          lv("A2", 200, 200),
          lv("B1", 3, 25),
          lv("B2", 0, 25),
          lv("C1", 0, 20),
          lv("C2", 0, 20),
        ],
      },
    }),
  );
  await page.route("**/api/listening/items*", (route) =>
    route.fulfill({ json: { level: "B1", items: [] } }),
  );
  await page.route("**/api/listening/question*", (route) =>
    route.fulfill({ json: QUESTION }),
  );
  await page.route("**/api/listening/answer*", (route) =>
    route.fulfill({ json: FAILURE }),
  );
  // La cola de repaso de frases (V3.89) se refresca tras el fallo.
  await page.route("**/api/listening/review-queue*", (route) =>
    route.fulfill({
      json: { pending: 1, due: 1, total: 1, entries: [] },
    }),
  );
  await page.route("**/api/listening/diagnostic*", (route) =>
    route.fulfill({
      json: {
        subskills: [],
        weak: [],
        recommendation: "",
        first_pass_accuracy: null,
        automaticity: null,
        by_difficulty: [],
        by_topic: [],
        trend: {
          recent_accuracy: null,
          prior_accuracy: null,
          delta: null,
          direction: "n/a",
        },
        recurrence: {
          questions_seen: 0,
          retried: 0,
          recovered: 0,
          retry_rate: null,
          recovery_rate: null,
        },
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
      },
    }),
  );
  await page.route("**/api/voices*", (route) =>
    route.fulfill({
      json: {
        voices: [{ id: "en_US-lessac-medium", name: "American English · Lessac" }],
        downloadable: [],
        default: "en_US-lessac-medium",
        selected: "en_US-lessac-medium",
        defaults: { en: "en_US-lessac-medium" },
      },
    }),
  );
  await page.route("**/api/settings*", (route) =>
    route.fulfill({ json: { settings: {} } }),
  );
  // El TTS en vivo se deja PENDIENTE a propósito: nunca responde, así el estado
  // «sonando» es determinista y la prueba no depende del sintetizador.
  await page.route("**/api/tts", () => new Promise(() => {}));
}

const VISUAL_TESTER = { id: "u-visual-circuit", name: "Visual Tester" };

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

/** Día a medias que YA arrastra la evidencia: 2 palabras señaladas, 3 fallos. */
const DAILY_PLAN = {
  goal: GOAL,
  plan_mode: "mixed",
  minutes_target: 30,
  units_target: 4,
  units_remaining: 2,
  minutes_remaining: 14,
  include_listening: true,
  include_speaking: true,
  pending: { fsrs: 3, listening: 1, total: 4 },
  progress: {
    units_done: 2,
    units_target: 4,
    minutes_done: 16,
    minutes_target: 30,
    units_ratio: 0.5,
    minutes_ratio: 0.53,
    percent: 0.52,
    done: false,
  },
  metrics: {
    day: "2026-09-29",
    units: 2,
    unknown_units: 0,
    minutes: 16,
    reviews: 1,
    new: 1,
    listening: 1,
    practice: 2,
    speaking: 0,
    listening_attempts: 4,
    listening_accuracy: 0.5,
    accuracy: 0.6,
    difficulty_evidence: 3,
    words_flagged: 2,
    by_kind: { review: 1, new: 1 },
    by_skill: { vocabulary: 1, listening: 1 },
  },
  session: { total_minutes: 16, review_count: 1, practice_count: 2, items: [] },
};

async function mockDailyPlanHome(page: Page) {
  await page.route("**/api/users", (route) => {
    if (route.request().method() === "GET") {
      void route.fulfill({ json: [VISUAL_TESTER] });
    } else {
      void route.continue();
    }
  });
  // La identidad la firma el servidor (cookie HttpOnly), así que el arnés visual
  // —que corre sin backend por diseño— la resuelve en el navegador. Sin esto la
  // puerta de entrada tapa la app y Home nunca pinta el plan.
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

test("V3.92: el fallo de Listening declara la evidencia de dificultad y deja continuar", async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name;

  await page.goto("/");
  await ensureProfile(page);
  await mockListening(page);
  await page.goto("/#/aprender/listening");

  await expect(page.getByText("Mastered 3 of 25").first()).toBeVisible({
    timeout: 15_000,
  });

  // Arrancar la ruta B1: sirve el ítem con micro-flujo (mismo payload del backend).
  await page.getByRole("button", { name: "Level B1 history" }).last().click();

  // while1: aún no se ve la pregunta; el PLAY es la señal de «he escuchado».
  const play = page.getByRole("button", { name: "Listen to audio" }).first();
  await expect(play).toBeVisible({ timeout: 15_000 });
  await play.click();

  // while2: la pregunta con sus opciones.
  const wrongOption = page.getByRole("button", { name: /8:45/ }).first();
  await expect(wrongOption).toBeVisible({ timeout: 15_000 });
  await wrongOption.click();

  // La tarjeta de fallo de V3.89 existe (sin la política del backend no se
  // pintaba) y EXPLICA la evidencia: 2 palabras que el alumno ya tenía.
  await expect(
    page.getByText("Not quite — you can keep going"),
  ).toBeVisible({ timeout: 15_000 });
  const evidence = page.getByTestId("listening-difficulty-evidence");
  await expect(evidence).toBeVisible();
  await expect(evidence).toContainText(
    "2 word(s) you already had are now marked as harder",
  );
  await expect(evidence).toContainText("evidence, not a review");
  await expect(evidence).toContainText("Nothing is blocked");

  // El fallo no bloquea: las tres acciones siguen ahí.
  await expect(page.getByRole("button", { name: "Review now" }).first()).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Continue", exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Review later" }).first(),
  ).toBeVisible();

  await page.screenshot({
    path: path.join(
      "tests",
      "visual",
      "screenshots",
      project,
      "listening-difficulty-evidence.png",
    ),
    fullPage: true,
  });
});

test("V3.92: el plan diario publica la evidencia unificada sin inflar el objetivo", async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name;

  await mockDailyPlanHome(page);
  await page.goto("/");

  await expect(
    page.getByRole("navigation", { name: "Main navigation" }),
  ).toBeVisible({ timeout: 15_000 });

  // La evidencia del día se declara como lo que es: palabras complicadas por
  // fallos de escucha, y se aclara que NO es un repaso pendiente.
  const evidence = page.getByTestId("goal-difficulty-evidence");
  await expect(evidence).toBeVisible();
  await expect(evidence).toContainText("Words that got harder: 2");
  await expect(evidence).toContainText("3 listening misses; it's evidence, not a review");

  // El progreso no se toca por la evidencia: manda el plan, no los fallos.
  await expect(page.getByTestId("goal-progress-pct")).toHaveText("52%");
  await expect(
    page.getByRole("progressbar", { name: "Today's goal" }),
  ).toHaveAttribute("aria-valuenow", "52");

  // Y la cola de repaso sigue contando solo lo que es repaso (3 FSRS + 1 frase).
  await expect(page.getByText("Pending reviews: 4")).toBeVisible();
  await expect(page.getByText("(3 FSRS, 1 Listening)")).toBeVisible();

  await page.screenshot({
    path: path.join(
      "tests",
      "visual",
      "screenshots",
      project,
      "home-difficulty-evidence.png",
    ),
    fullPage: true,
  });
});
