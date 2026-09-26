import { test, expect } from "@playwright/test";
import path from "node:path";
import { ensureProfile } from "./gateHelper";

/**
 * Vocabulary A1→C2 (V3.11): captura de revisión de la página única APRENDER →
 * Vocabulario con mock de red determinista.
 *
 * Misma arquitectura que Pronunciation/Conversation: el escenario de práctica
 * (un check MC del currículo con feedback inmediato y revelación de la respuesta
 * correcta) vive arriba y, bajo él, el mapa de rutas A1–C2 con anillos y el
 * panel del nivel (Repetir fallidas / Repasar aprendidas / Demostrar el nivel
 * con las evaluaciones formales del curso). Sin micrófono ni TTS: la evaluación
 * es determinista.
 *  - GET /api/vocabulary/routes/stats → ruta A1 en marcha (5/6 dominadas,
 *    1 fallada); A2–C2 sin empezar.
 *  - GET /api/vocabulary/routes/items → coherente con las stats.
 *  - GET /api/vocabulary/routes/question → un check MC de A1.
 *  - POST /api/vocabulary/routes/attempt → resultado determinista.
 *  - GET /api/vocabulary/lexicon → diccionario personal vacío.
 * Solo se ejecuta en desktop.
 */

const BANK: Record<string, number> = { A1: 6, A2: 5, B1: 5, B2: 4, C1: 4, C2: 4 };

function gateFor(level: string, mastered: number, coveragePct: number) {
  const total = BANK[level];
  return {
    passed: mastered >= total,
    total,
    mastered,
    coverage_pct: coveragePct,
    coverage_required_pct: 80,
    accuracy: mastered > 0 ? 65 : null,
    accuracy_required: 70,
    topics: mastered > 0 ? 3 : 0,
    topics_required: 3,
    checkpoint: 1,
    checkpoint_required: 1,
    short_bank: total < 12,
    blockers: mastered >= total ? ["accuracy"] : mastered > 0 ? ["coverage"] : ["coverage"],
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

/** Check MC de A1 servido por GET /question (sin la respuesta: se oculta). */
const QUESTION_A1 = {
  check_id: "a1-m01-u01-l01-o01-c05",
  level: "A1",
  topic: "Everyday Life",
  prompt: "Which word means 'casa'?",
  options: ["house", "car", "phone", "town"],
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

const PROMPTS_A1 = [
  "Which word means 'país'?",
  "Which word means 'ciudad'?",
  "Which word means 'trabajo'?",
  "Which word means 'edad'?",
  "Which word means 'familia'?",
  "Which word means 'casa'?",
];

function itemsA1() {
  const base = (i: number, state: string) => ({
    check_id: `a1-m01-u01-l01-o01-c0${i + 1}`,
    level: "A1",
    topic: "Everyday Life",
    prompt: PROMPTS_A1[i],
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
      base(4, "failed"),
      base(0, "mastered"),
      base(1, "mastered"),
      base(2, "mastered"),
      base(3, "mastered"),
      base(5, "mastered"),
    ],
  };
}

/** Resultado determinista del POST: el alumno elige "house" (índice 0). */
function attemptOk(selectedIndex: number) {
  return {
    check_id: QUESTION_A1.check_id,
    level: "A1",
    topic: QUESTION_A1.topic,
    prompt: QUESTION_A1.prompt,
    options: QUESTION_A1.options,
    correct_index: 0,
    selected_index: selectedIndex,
    passed: selectedIndex === 0,
    score: selectedIndex === 0 ? 100 : 0,
  };
}

const LEXICON_EMPTY = {
  summary: {
    total: 0,
    known: 0,
    learning: 0,
    weak: 0,
    mastered: 0,
    by_cefr: [],
  },
  items: [],
};

/**
 * V3.86.0: palabra YA rastreada. Es la que se quedaba SIN NINGUNA SALIDA en el
 * diccionario incrustado de APRENDER → Vocabulario: como el panel no hospeda la
 * sesión de estudio, «Estudiar en Flashcards» no existía y la única acción
 * ofrecida (el alta) perdía sentido.
 */
const TRACKED_LOOKUP = {
  word: "coffee",
  kind: "word",
  cefr: "A1",
  definition_source: "llm",
  pos: "noun",
  definition: "A hot drink made from roasted coffee beans.",
  translation: "café",
  direction: "en-es",
  alternatives: [],
  meanings: [],
  example: null,
  usage: {
    tracked: true,
    surface: {
      status: "learning",
      mastery: 0.4,
      recall: 0.6,
      next_review_days: 2,
      production_count: 1,
      exposure_count: 3,
      production_channels: ["chat"],
      competence: {
        recognition: true,
        production: false,
        transfer: false,
        retention: false,
      },
      last_activity_at: "2026-09-20T10:00:00Z",
    },
    unit: null,
  },
};

async function installMocks(page: import("@playwright/test").Page) {
  await page.route("**/api/vocabulary/routes/stats*", (route) =>
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
  await page.route("**/api/vocabulary/routes/items*", (route) =>
    route.fulfill({ json: itemsA1() }),
  );
  await page.route("**/api/vocabulary/routes/question*", (route) =>
    route.fulfill({ json: QUESTION_A1 }),
  );
  // Intento MC (POST): resultado determinista según la opción elegida.
  await page.route("**/api/vocabulary/routes/attempt*", (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as {
        check_id: string;
        selected_index: number;
      };
      route.fulfill({ json: attemptOk(body.selected_index) });
    } else {
      route.continue();
    }
  });
  await page.route("**/api/vocabulary/lexicon*", (route) =>
    route.fulfill({ json: LEXICON_EMPTY }),
  );
  // V3.86.0: la consulta del diccionario incrustado (misma respuesta que la
  // pantalla dedicada) más los ajustes, de donde sale la dirección.
  await page.route("**/api/vocabulary/dictionary*", (route) =>
    route.fulfill({ json: TRACKED_LOOKUP }),
  );
  await page.route("**/api/settings*", (route) =>
    route.fulfill({ json: { settings: {} } }),
  );
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
  // V3.85.1 (D4): destino del CTA «Repasar hoy» del panel incrustado — la
  // superficie central (Flashcards → Estudiar) necesita su cola y sus mazos.
  await page.route("**/api/learning/review*", (route) =>
    route.fulfill({
      json: { due_count: 0, items: [], fsrs_version: "test", units: [] },
    }),
  );
  await page.route(/\/api\/vocabulary\/decks(\/.*)?$/, (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/api/vocabulary/decks") {
      return route.fulfill({
        json: { auto_deck_id: 0, decks: [], fsrs_version: "test" },
      });
    }
    return route.fulfill({
      json: {
        deck: { id: 0, name: "", is_auto: true },
        items: [],
        due_count: 0,
        new_count: 0,
        reviewed_today: 0,
        new_today: 0,
        limits: { new_remaining: 0, review_remaining: 0 },
        fsrs_version: "test",
      },
    });
  });
}

test("capturar Vocabulary: página única MC + feedback + diccionario (mock)", async ({
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
  await page.goto("/#/aprender/vocabulario");
  await expect(nav()).toBeVisible({ timeout: 15_000 });

  // Escenario superior (siempre visible, sin sesión): pregunta MC y el mapa
  // honesto queda bajo ella.
  await expect(page.getByText(QUESTION_A1.prompt, { exact: true }).first()).toBeVisible(
    { timeout: 15_000 },
  );
  await expect(page.getByText("Choose the word that fits.").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "house" })).toBeVisible();

  // Mapa de rutas: A1 desplegada por defecto con el panel (Repetir fallidas /
  // Repasar aprendidas / Demostrar nivel con las evaluaciones del curso).
  await expect(page.getByText("5 of 6").first()).toBeVisible({
    timeout: 15_000,
  });
  await expect(
    page.getByRole("button", { name: "Repeat missed (1)" }),
  ).toBeVisible({ timeout: 15_000 });
  await expect(
    page.getByRole("button", { name: "Review learned (5)" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Open formal assessments" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "My dictionary" }),
  ).toBeVisible();

  await page.waitForTimeout(600);
  await page.screenshot({ path: shot("vocabulary-routes-map"), fullPage: true });

  // Responder en práctica libre: feedback determinista con la correcta revelada.
  await page.getByRole("button", { name: "house" }).click();
  await expect(page.getByText("Correct", { exact: true }).first()).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(/Score: 100\/100/).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue" })).toBeVisible();

  await page.waitForTimeout(500);
  await page.screenshot({ path: shot("vocabulary-score"), fullPage: true });

  // Continuar (vuelve a práctica libre) y lanzar "Repetir fallidas": la sesión
  // vive en la MISMA página y se cierra al dominar el único check fallado.
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText(QUESTION_A1.prompt, { exact: true }).first()).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("button", { name: "Repeat missed (1)" }).click();
  await expect(page.getByText("Repeating missed checks")).toBeVisible({
    timeout: 15_000,
  });

  await page.getByRole("button", { name: "house" }).click();
  await expect(page.getByText("Correct", { exact: true }).first()).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("Session finished").first()).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByRole("button", { name: "Back to routes" }).first()).toBeVisible();

  await page.waitForTimeout(500);
  await page.screenshot({ path: shot("vocabulary-session-done"), fullPage: true });

  // El diccionario personal sigue accesible desde la propia página.
  await page.getByRole("button", { name: "Back to routes" }).first().click();
  await expect(page.getByText(QUESTION_A1.prompt, { exact: true }).first()).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("button", { name: "My dictionary" }).click();
  await expect(page.getByText("Personal dictionary").first()).toBeVisible({
    timeout: 15_000,
  });

  await page.waitForTimeout(600);
  await page.screenshot({ path: shot("vocabulary-dictionary"), fullPage: true });
});

test("V3.85.1: el panel APRENDER → Vocabulario recupera el acceso al repaso (D4)", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Solo desktop");

  await page.goto("/");
  await ensureProfile(page);
  await installMocks(page);
  await page.goto("/#/aprender/vocabulario");
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible({
    timeout: 15_000,
  });

  await page.getByRole("button", { name: "My dictionary" }).click();
  await expect(page.getByText("Personal dictionary").first()).toBeVisible({
    timeout: 15_000,
  });

  // V3.85.0 retiró el drill de repaso del panel: este CTA lo devuelve SIN
  // duplicar la sesión — transporta a la superficie central del diccionario.
  const cta = page.getByRole("button", { name: "Review today" });
  await expect(cta).toBeVisible();
  await cta.click();

  await expect(page).toHaveURL(/#\/diccionario/);
  await expect(
    page.getByRole("tab", { name: "Flashcards", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  // El destino es la sub-pestaña de estudio, donde vive «Repasar hoy».
  await expect(
    page.getByRole("tab", { name: "Study", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
});

test("V3.86.0: el diccionario incrustado da salida a una palabra ya rastreada", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Solo desktop");

  await page.goto("/");
  await ensureProfile(page);
  await installMocks(page);
  await page.goto("/#/aprender/vocabulario");
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible({
    timeout: 15_000,
  });

  // El panel solo ofrecía inventario y consulta. La consulta de una palabra ya
  // rastreada se quedaba sin NINGUNA acción: el alta no cambiaría nada y la
  // sesión de estudio no cabe en el panel. Ahora tiene salida.
  await page.getByRole("button", { name: "Consult" }).click();
  await page.getByLabel("Search the dictionary").fill("coffee");
  await page.getByRole("button", { name: "Look up" }).click();
  await expect(page.getByText(/Already in your dictionary/)).toBeVisible({
    timeout: 15_000,
  });

  // La salida cruza de pantalla (el panel no hospeda el estudio): persiste la
  // vista y navega a la superficie central, en Flashcards → Estudiar.
  await page.getByRole("button", { name: "Study in Flashcards" }).click();
  await expect(page).toHaveURL(/#\/diccionario/);
  await expect(
    page.getByRole("tab", { name: "Flashcards", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByRole("tab", { name: "Study", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
});
