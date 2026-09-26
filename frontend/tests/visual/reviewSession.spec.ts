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
 * Los ítems se sirven con `activity: "write"` porque es el único peldaño que
 * acredita producción **sin micrófono** (Recognition y Recall no disparan
 * `onProduced`: su acierto es señal, no producción). La suite corre sin backend,
 * así que el micrófono no está disponible y un peldaño oral dejaría la sesión sin
 * forma de avanzar —que es precisamente lo que esta prueba mide.
 */

const USER = { id: "u1", name: "Test", created_at: "2026-01-01T00:00:00Z" };

const VOICES = {
  voices: [],
  downloadable: [],
  default: "en_GB-alan-medium",
  selected: "en_GB-alan-medium",
};

/** Ítem de la cola de repaso (misma forma que sirve `GET /api/learning/review`). */
function reviewItem(word: string, decisionId: string): Record<string, unknown> {
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
    activity: "write",
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
      activity: "write",
      reason: "production_gap",
      support_level: "prompted",
    },
    decision: null,
    competence: null,
    evidence: null,
    task_key: `${word}|write|prompted|lexical:3|write`,
    task_instance_key: `${word}|write|prompted|lexical:3|write|`,
    served_load: { lexical: 3 },
    assessment_mode: "production",
    transfer_state: "none",
    decision_id: decisionId,
  };
}

/**
 * Mockea TODO `/api/**` con una cola de DOS palabras y devuelve el registro de
 * llamadas reales del navegador.
 *
 * OJO con el matcher: debe excluir `/src/api/*.ts` (los MÓDULOS de la app), que
 * un glob `**​/api/**` también captura y dejaría la app sin arrancar. Mismo
 * criterio que `drillProvenance.spec.ts`.
 */
async function mockApi(page: Page): Promise<void> {
  await page.route(/^https?:\/\/[^/]+\/api\//, (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;

    if (pathname === "/api/users" || pathname === "/api/session") {
      return route.fallback();
    }
    if (pathname === "/api/learning/review") {
      return route.fulfill({
        json: {
          due_count: 2,
          items: [
            reviewItem("river", "d-river"),
            reviewItem("coffee", "d-coffee"),
          ],
          fsrs_version: "test",
          units: [],
        },
      });
    }
    // El peldaño Write no pide consigna al servidor: se puntúa el intento.
    if (pathname === "/api/vocabulary/drill/write-attempt") {
      return route.fulfill({
        json: {
          word: "",
          passed: true,
          used_word: true,
          word_count: 6,
          min_words: 4,
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

test("la sesión de repaso encadena la cola y vuelve al resumen (3 breakpoints)", async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name;
  const shot = (name: string) =>
    path.join("tests", "visual", "screenshots", project, `${name}.png`);

  await page.goto("/");
  // Los mocks se registran ANTES de `ensureProfile`: su `page.reload()` es la
  // carga con la que arranca la app bajo el contrato determinista.
  await mockApi(page);
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
