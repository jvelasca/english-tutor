import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import { ensureProfile } from "./gateHelper";

/**
 * «Repasar hoy» ACCIONABLE (V3.85.0) — red mockeada, 3 breakpoints.
 *
 * V3.85.0 retira la lista de 20 filas con un botón por ítem cuya etiqueta era una
 * **palabra de estado** («vencida») y la convierte en **resumen + una sola
 * acción** que **encadena** la cola del día. Esta spec fija ese contrato, que es
 * justo lo que la lista no tenía:
 *
 * 1. la entrada es UNA («Review now (N)»), no N botones;
 * 2. el resumen dice cuántas palabras tocan y la sesión abre en la primera;
 * 3. al superar el peldaño aparece «Next word» (y «Finish» en la última) y el
 *    drill **sigue montado** para poder leer el feedback: no auto-avanza;
 * 4. al terminar la cola se vuelve al resumen con el recuento refrescado.
 *
 * V3.85.1 (C1, P0 de la auditoría AY). El primer test sirve los ítems con
 * `activity: "write"` porque es el único peldaño que acredita producción **sin
 * micrófono** —y con eso se cubría solo el caso feliz—. Ese sesgo **tapaba** que
 * la sesión solo avanzaba con `onProduced`, que Recognition y Recall **nunca**
 * disparan: un ítem servido en uno de esos peldaños quedaba clavado. El segundo
 * test recorre **los cinco peldaños** (Recognition, Recall, Sentence, Write,
 * Transfer) y exige que la sesión avance en cada uno, con micrófono falso para
 * Sentence. Si el contrato vuelve a atarse a `onProduced`, este test se rompe.
 */

const USER = { id: "u1", name: "Test", created_at: "2026-01-01T00:00:00Z" };

const VOICES = {
  voices: [],
  downloadable: [],
  default: "en_GB-alan-medium",
  selected: "en_GB-alan-medium",
};

/** Peldaños de la escalera que la cola puede servir como actividad inicial. */
type Rung = "recognition" | "recall" | "sentence" | "write" | "transfer";

/** Ítem de la cola de repaso (misma forma que sirve `GET /api/learning/review`). */
function reviewItem(
  word: string,
  decisionId: string,
  activity: Rung = "write",
): Record<string, unknown> {
  return {
    word,
    lexical_unit: word,
    cefr: "A1",
    kind: "word",
    due_at: "",
    state: "review",
    stability: 1,
    retrievability: 0.4,
    elapsed_days: 9,
    activity,
    reason: "production_gap",
    recommended_cue: "translation",
    automatic: false,
    automatic_skills: [],
    priority: 0.5,
    expected_learning_value: 0.5,
    learning_value: null,
    signals: null,
    why: "",
    limiting_skill: "written_production",
    skill_priorities: { written_production: 0.5 },
    task: {
      skill: "written_production",
      activity,
      reason: "production_gap",
      support_level: "prompted",
    },
    decision: null,
    competence: null,
    evidence: null,
    task_key: `${word}|${activity}|prompted|lexical:3|${activity}`,
    task_instance_key: `${word}|${activity}|prompted|lexical:3|${activity}|`,
    served_load: { lexical: 3 },
    assessment_mode: "production",
    transfer_state: "none",
    decision_id: decisionId,
  };
}

/**
 * Micrófono falso + `MediaRecorder` determinista (mismo patrón que
 * `speakingRoutesReview.spec.ts`): el peldaño Sentence graba sin hardware.
 */
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

/**
 * Mockea TODO `/api/**` con la cola servida y devuelve el registro de llamadas
 * reales del navegador.
 *
 * OJO con el matcher: debe excluir `/src/api/*.ts` (los MÓDULOS de la app), que
 * un glob `**​/api/**` también captura y dejaría la app sin arrancar. Mismo
 * criterio que `drillProvenance.spec.ts`.
 */
async function mockApi(page: Page, items: Record<string, unknown>[]): Promise<void> {
  await page.route(/^https?:\/\/[^/]+\/api\//, (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;

    if (pathname === "/api/users" || pathname === "/api/session") {
      return route.fallback();
    }
    if (pathname === "/api/learning/review") {
      return route.fulfill({
        json: { due_count: items.length, items, fsrs_version: "test", units: [] },
      });
    }
    // --- Peldaño Recognition (MCQ, sin micrófono) ---------------------------
    if (pathname === "/api/vocabulary/drill/recognition") {
      return route.fulfill({
        json: { word: "", available: true, question_id: "q1", options: ["río", "mar"] },
      });
    }
    if (pathname === "/api/vocabulary/drill/recognition-attempt") {
      return route.fulfill({
        json: { word: "", correct: true, correct_index: 0, selected_index: 0 },
      });
    }
    // --- Peldaño Recall (recuperación por texto) ----------------------------
    if (pathname === "/api/vocabulary/drill/recall") {
      return route.fulfill({
        json: { word: "", available: true, cue: "café", cue_kind: "translation" },
      });
    }
    if (pathname === "/api/vocabulary/drill/recall-attempt") {
      return route.fulfill({
        json: {
          word: "",
          correct: true,
          expected: "coffee",
          delayed: false,
          recall_days: 1,
          error_type: "correct",
        },
      });
    }
    // --- Peldaño Sentence (oral, con micrófono falso) -----------------------
    if (pathname === "/api/vocabulary/drill/sentence-context") {
      return route.fulfill({
        json: {
          word: "",
          phrase: "I cross the bridge every morning.",
          source: "template",
          level: "A1",
        },
      });
    }
    if (pathname === "/api/vocabulary/drill/sentence-attempt") {
      return route.fulfill({
        json: {
          word: "",
          phrase: "I cross the bridge every morning.",
          source: "template",
          produced: true,
          phrase_ok: true,
          passed: true,
          heard: "I cross the bridge every morning.",
          score: 90,
          level: "A1",
          asr_status: "ok",
        },
      });
    }
    // --- Peldaño Write (producción escrita) ---------------------------------
    if (pathname === "/api/vocabulary/drill/write-attempt") {
      return route.fulfill({
        json: { word: "", passed: true, used_word: true, word_count: 6, min_words: 4 },
      });
    }
    // --- Peldaño Transfer (contexto nuevo) ----------------------------------
    if (pathname === "/api/vocabulary/drill/transfer-context") {
      return route.fulfill({
        json: {
          word: "",
          context_id: "transfer:story",
          topic: "personal_experience",
          prompt: "Tell a short story about something that happened to you recently.",
          available: true,
          communicative_goal: "narrate",
          discourse_type: "narrative",
        },
      });
    }
    if (pathname === "/api/vocabulary/drill/transfer-attempt") {
      return route.fulfill({
        json: {
          word: "",
          text: "",
          context_id: "transfer:story",
          used_word: true,
          word_count: 8,
          passed: true,
          error_type: "correct",
          lexical_transfer: true,
          semantic_fit: true,
          adequacy: "fit",
        },
      });
    }
    if (pathname === "/api/vocabulary/drill/decision-lifecycle") {
      return route.fulfill({ json: { applied: true } });
    }
    if (pathname === "/api/vocabulary/decks") {
      return route.fulfill({
        json: {
          decks: [
            {
              id: 0,
              name: "",
              is_auto: true,
              card_count: 0,
              due_count: 0,
              new_count: 0,
              new_per_day: 20,
              review_per_day: 200,
            },
          ],
          auto_deck_id: 0,
          fsrs_version: "test",
        },
      });
    }
    if (pathname.startsWith("/api/vocabulary/decks/")) {
      // Cola de tarjetas vacía: la otra acción del bloque no ofrece sesión, que
      // es lo que se quiere para aislar la del repaso.
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
    }
    if (pathname === "/api/vocabulary/lexicon") {
      return route.fulfill({
        json: {
          summary: {
            total: 0,
            known: 0,
            learning: 0,
            weak: 0,
            mastered: 0,
            by_cefr: [],
          },
          items: [],
        },
      });
    }
    if (pathname === "/api/vocabulary/collections") {
      return route.fulfill({ json: { collections: [] } });
    }
    if (pathname === "/api/vocabulary/drill/candidates") {
      return route.fulfill({ json: { words: [] } });
    }
    if (pathname === "/api/settings") {
      return route.fulfill({ json: { settings: {} } });
    }
    if (pathname.startsWith("/api/voices")) {
      return route.fulfill({ json: VOICES });
    }
    // El resto: forma vacía y válida.
    return route.fulfill({ json: request.method() === "GET" ? {} : { ok: true } });
  });
}

/** Abre el diccionario en la sub-pestaña Estudiar de Flashcards. */
async function openStudyTab(page: Page) {
  await page.goto("/#/diccionario");
  await page
    .getByRole("tab", { name: "Flashcards", exact: true })
    .first()
    .click();
  await page.getByRole("tab", { name: "Study", exact: true }).click();
}

/** Supera el peldaño Write con una frase propia y espera al veredicto. */
async function passWriteStep(page: Page, sentence: string) {
  const answer = page.getByLabel("Your sentence");
  await expect(answer).toBeVisible({ timeout: 15_000 });
  await answer.fill(sentence);
  await page.getByRole("button", { name: "Check sentence" }).click();
  await expect(page.getByText(/You produced the word in writing/)).toBeVisible({
    timeout: 15_000,
  });
}

/** Supera Recognition eligiendo la opción correcta (sin micrófono). */
async function passRecognitionStep(page: Page) {
  const option = page.getByRole("button", { name: "río", exact: true });
  await expect(option).toBeVisible({ timeout: 15_000 });
  await option.click();
  await page.getByRole("button", { name: "Check answer" }).click();
}

/** Supera Recall tecleando la palabra a partir del cue. */
async function passRecallStep(page: Page) {
  const input = page.getByLabel("Type the word");
  await expect(input).toBeVisible({ timeout: 15_000 });
  await input.fill("coffee");
  await page.getByRole("button", { name: "Check", exact: true }).click();
}

/** Supera Sentence grabando con el micrófono falso. */
async function passSentenceStep(page: Page) {
  const record = page.getByRole("button", { name: "Record", exact: true });
  await expect(record).toBeEnabled({ timeout: 15_000 });
  await record.click();
  const stop = page.getByRole("button", { name: "Stop", exact: true });
  await expect(stop).toBeVisible({ timeout: 15_000 });
  await stop.click();
  await expect(
    page.getByText(/You said the word inside the sentence/),
  ).toBeVisible({ timeout: 15_000 });
}

/** Supera Transfer usando la palabra en un contexto nuevo. */
async function passTransferStep(page: Page) {
  const answer = page.getByLabel("Your answer");
  await expect(answer).toBeVisible({ timeout: 15_000 });
  await answer.fill("Yesterday I opened the window and felt the cold air.");
  await page.getByRole("button", { name: "Check answer" }).click();
}

/** Pulsa el CTA de avance (sea «Next word» o «Finish»). */
async function advance(page: Page) {
  await page.getByRole("button", { name: /Next word|Finish/ }).click();
}

test("la sesión de repaso encadena la cola y vuelve al resumen (3 breakpoints)", async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name;
  const shot = (name: string) =>
    path.join("tests", "visual", "screenshots", project, `${name}.png`);

  const items = [
    reviewItem("river", "d-river"),
    reviewItem("coffee", "d-coffee"),
  ];

  await page.goto("/");
  // Los mocks se registran ANTES de `ensureProfile`: su `page.reload()` es la
  // carga con la que arranca la app bajo el contrato determinista.
  await mockApi(page, items);
  await ensureProfile(page);
  await openStudyTab(page);

  // --- El resumen: UNA acción con el recuento -----------------------------
  await expect(page.getByText("Today's review")).toBeVisible({ timeout: 15_000 });
  await expect(
    page.getByText("2 words are due. One session, one step each."),
  ).toBeVisible();
  const start = page.getByRole("button", { name: "Review now (2)" });
  await expect(start).toBeVisible();
  await page.waitForTimeout(400);
  await page.screenshot({ path: shot("review-today-summary"), fullPage: true });

  // --- Sesión encadenada: primera palabra ---------------------------------
  await start.click();
  await expect(page.getByText("1 of 2")).toBeVisible({ timeout: 15_000 });
  // No auto-avanza: antes de superar el peldaño no hay «Next word».
  await expect(page.getByRole("button", { name: "Next word" })).toHaveCount(0);
  await passWriteStep(page, "I swim in the river every summer morning.");
  // El drill SIGUE montado (el feedback se lee) y ahora sí se ofrece avanzar.
  await expect(page.getByLabel("Your sentence")).toBeVisible();
  const next = page.getByRole("button", { name: "Next word" });
  await expect(next).toBeVisible();
  await page.waitForTimeout(400);
  await page.screenshot({ path: shot("review-session-first"), fullPage: true });

  // --- Segunda palabra: el contador avanza y el CTA pasa a «Finish» -------
  await next.click();
  await expect(page.getByText("2 of 2")).toBeVisible({ timeout: 15_000 });
  // Cada palabra arranca limpia: el intento de la anterior no se hereda.
  await expect(page.getByLabel("Your sentence")).toHaveValue("");
  await expect(page.getByRole("button", { name: "Next word" })).toHaveCount(0);
  await passWriteStep(page, "I drink coffee with my family every Sunday.");
  const finish = page.getByRole("button", { name: "Finish" });
  await expect(finish).toBeVisible();

  // --- Terminar: se vuelve al resumen con el recuento refrescado ----------
  await finish.click();
  await expect(page.getByRole("button", { name: "Review now (2)" })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText("2 words are due. One session, one step each.")).toBeVisible();
});

test("la sesión es navegable por teclado y anuncia el progreso (V3.85.1, a11y)", async ({
  page,
}) => {
  const items = [
    reviewItem("river", "d-river"),
    reviewItem("coffee", "d-coffee"),
  ];

  await page.goto("/");
  await mockApi(page, items);
  await ensureProfile(page);
  await openStudyTab(page);

  await expect(page.getByText("Today's review")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: "Review now (2)" }).click();

  // El contador es región VIVA: el progreso se anuncia, no solo se ve.
  const progress = page.getByRole("status").filter({ hasText: "1 of 2" });
  await expect(progress).toBeVisible({ timeout: 15_000 });
  await expect(progress).toHaveAttribute("aria-live", "polite");
  await expect(progress).toHaveAttribute("aria-atomic", "true");

  await passWriteStep(page, "I swim in the river every summer morning.");

  // El foco viaja al CTA al aparecer: no hay que tabular por todo el drill.
  const next = page.getByRole("button", { name: "Next word" });
  await expect(next).toBeFocused();
  // Enter avanza sin tocar el ratón.
  await page.keyboard.press("Enter");
  await expect(page.getByText("2 of 2")).toBeVisible({ timeout: 15_000 });
});

test("la sesión avanza en los cinco peldaños (V3.85.1, C1)", async ({ page }) => {
  const items = [
    reviewItem("river", "d-recognition", "recognition"),
    reviewItem("coffee", "d-recall", "recall"),
    reviewItem("bridge", "d-sentence", "sentence"),
    reviewItem("forest", "d-write", "write"),
    reviewItem("window", "d-transfer", "transfer"),
  ];

  await installFakeMedia(page);
  await page.goto("/");
  await mockApi(page, items);
  await ensureProfile(page);
  await openStudyTab(page);

  await expect(page.getByText("Today's review")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: "Review now (5)" }).click();

  // 1/5 Recognition: su acierto es señal, no producción — y aun así avanza.
  await expect(page.getByText("1 of 5")).toBeVisible({ timeout: 15_000 });
  await passRecognitionStep(page);
  await expect(page.getByRole("button", { name: "Next word" })).toBeVisible({
    timeout: 15_000,
  });
  await advance(page);

  // 2/5 Recall: recuperación por texto; tampoco dispara `onProduced`.
  await expect(page.getByText("2 of 5")).toBeVisible({ timeout: 15_000 });
  await passRecallStep(page);
  await expect(page.getByRole("button", { name: "Next word" })).toBeVisible({
    timeout: 15_000,
  });
  await advance(page);

  // 3/5 Sentence: peldaño oral con micrófono falso.
  await expect(page.getByText("3 of 5")).toBeVisible({ timeout: 15_000 });
  await passSentenceStep(page);
  await expect(page.getByRole("button", { name: "Next word" })).toBeVisible({
    timeout: 15_000,
  });
  await advance(page);

  // 4/5 Write: producción escrita.
  await expect(page.getByText("4 of 5")).toBeVisible({ timeout: 15_000 });
  await passWriteStep(page, "The forest was quiet after the rain.");
  await expect(page.getByRole("button", { name: "Next word" })).toBeVisible({
    timeout: 15_000,
  });
  await advance(page);

  // 5/5 Transfer: contexto nuevo; es la última, así que el CTA es «Finish».
  await expect(page.getByText("5 of 5")).toBeVisible({ timeout: 15_000 });
  await passTransferStep(page);
  const finish = page.getByRole("button", { name: "Finish" });
  await expect(finish).toBeVisible({ timeout: 15_000 });
  await finish.click();

  // Se vuelve al resumen: la cola quedó recorrida entera.
  await expect(page.getByText("Today's review")).toBeVisible({ timeout: 15_000 });
});
