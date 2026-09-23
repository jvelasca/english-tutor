import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { ensureProfile } from "./gateHelper";

/**
 * Smoke visual permanente del DICCIONARIO (V3.80.1).
 *
 * No sustituye al barrido de capturas de `smoke.spec.ts` (que recorre las rutas
 * raíz): fija el **contrato de UI** de la pantalla que más superficie acumula
 * —tres modos, buscador, resultado y borrado— y lo deja **capturado en los tres
 * breakpoints** (390 / 768 / 1280), sin `skip` por proyecto. Era el hueco que
 * declaró V3.80.0: la autoridad visual estaba solo en CI y no había una sonda
 * permanente que mordiera si el diccionario se rompía al pintar (el fallo de
 * V3.77.0/V3.77.1, que tumbó la pantalla entera).
 *
 * Determinista: mockea el diccionario, el léxico, las colecciones, los ajustes y
 * el catálogo de voces. La identidad la resuelve `ensureProfile`.
 */

const COFFEE_ENTRY = {
  word: "coffee",
  kind: "word",
  cefr: "A1",
  definition_source: "llm",
  pos: "noun",
  definition: "A hot drink made from roasted coffee beans.",
  translation: "café",
  direction: "en-es",
  alternatives: ["java"],
  example: {
    phrase: "I drink coffee every morning.",
    source: "pronunciation_corpus",
    level: "A1",
  },
  usage: {
    tracked: true,
    surface: {
      status: "known",
      mastery: 0.6,
      recall: 0.8,
      next_review_days: 3,
      production_count: 1,
      exposure_count: 4,
      production_channels: ["chat"],
      competence: {
        recognition: true,
        production: true,
        transfer: false,
        retention: false,
      },
      last_activity_at: "2026-09-20T10:00:00Z",
    },
    unit: null,
  },
};

const LEXICON = {
  summary: {
    total: 1,
    known: 0,
    learning: 1,
    weak: 0,
    mastered: 0,
    by_cefr: [{ cefr: "A1", count: 1 }],
  },
  items: [
    {
      word: "coffee",
      lemma: "coffee",
      cefr: "A1",
      kind: "word",
      source: "chat",
      status: "learning",
      recall: 0.8,
      next_review_days: 3,
      production_count: 1,
      exposure_count: 4,
    },
  ],
};

const VOICES = {
  voices: [],
  downloadable: [],
  default: "en_GB-alan-medium",
  selected: "en_GB-alan-medium",
};

/**
 * Un único route, anclado al ORIGEN, para todo `/api/**` (V3.80.1).
 *
 * OJO con los globs: un `**​/api/settings*` casa también con el módulo de la app
 * `/src/api/settings.ts`, y servirle JSON **deja la app sin arrancar** (el
 * navegador rechaza el módulo por MIME). Es la misma trampa que ya documenta
 * `drillProvenance.spec.ts`. Anclar el patrón a `https://<host>/api/` deja fuera
 * `/src/api/**` y no hay colisiones posibles.
 *
 * `/api/users` y `/api/session` se dejan pasar a la cadena (`fallback`) porque de
 * ellos se encarga `ensureProfile`, que registra sus routes **después**: en
 * Playwright gana la última registrada, así que la identidad sigue siendo suya.
 */
async function installDictionaryMocks(page: Page) {
  await page.route(/^https?:\/\/[^/]+\/api\//, (route) => {
    const url = new URL(route.request().url());
    const { pathname } = url;
    const method = route.request().method();

    if (pathname === "/api/users" || pathname === "/api/session") {
      return route.fallback();
    }
    if (pathname === "/api/vocabulary/dictionary") {
      return route.fulfill({ json: COFFEE_ENTRY });
    }
    if (pathname === "/api/vocabulary/lexicon") {
      return route.fulfill({ json: LEXICON });
    }
    if (pathname === "/api/vocabulary/collections") {
      return route.fulfill({ json: { collections: [] } });
    }
    if (pathname === "/api/vocabulary/retention/due") {
      return route.fulfill({
        json: { due_count: 0, limit: 0, items: [], fsrs_version: "test" },
      });
    }
    if (pathname === "/api/settings") {
      return route.fulfill({ json: { settings: {} } });
    }
    if (pathname.startsWith("/api/voices")) {
      return route.fulfill({ json: VOICES });
    }
    // El resto (salud, modelos, rutas de aprendizaje…): forma vacía y válida.
    return route.fulfill({ json: method === "GET" ? {} : { ok: true } });
  });
}

test("smoke del diccionario: tres modos, buscador y borrado (3 breakpoints)", async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name;
  const shot = (name: string) =>
    path.join("tests", "visual", "screenshots", project, `${name}.png`);

  await page.goto("/");
  // Los mocks se registran ANTES de `ensureProfile`: su `page.reload()` es la
  // carga con la que arranca la app bajo el contrato determinista.
  await installDictionaryMocks(page);
  await ensureProfile(page);
  await page.goto("/#/diccionario");

  // --- Modo Consultar (el defecto) ---------------------------------------
  const lookupTab = page.getByRole("tab", { name: "Look up", exact: true });
  await expect(lookupTab).toBeVisible({ timeout: 15_000 });
  await expect(lookupTab).toHaveAttribute("aria-selected", "true");
  // El panel está asociado a su pestaña (semántica ARIA real, V3.80.1).
  await expect(page.getByRole("tabpanel", { name: "Look up", exact: true })).toHaveAttribute(
    "aria-labelledby",
    "dictionary-tab-lookup",
  );

  await page.getByLabel("Search the dictionary").fill("coffee");
  await page.getByRole("button", { name: "Look up" }).click();
  await expect(page.getByRole("heading", { name: "coffee" })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(COFFEE_ENTRY.definition)).toBeVisible();
  await page.waitForTimeout(400);
  await page.screenshot({ path: shot("dictionary-lookup"), fullPage: true });

  // La X limpia búsqueda Y resultado, y devuelve el estado de «nueva consulta».
  await page.getByRole("button", { name: "Clear the search" }).click();
  await expect(page.getByRole("heading", { name: "coffee" })).toHaveCount(0);
  await expect(page.getByText("Try an example")).toBeVisible();

  // --- Modo Personal ------------------------------------------------------
  await page.getByRole("tab", { name: "Personal", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Personal", exact: true })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByRole("tabpanel", { name: "Personal", exact: true })).toHaveAttribute(
    "aria-labelledby",
    "dictionary-tab-personal",
  );
  await page.waitForTimeout(400);
  await page.screenshot({ path: shot("dictionary-personal"), fullPage: true });

  // --- Modo Flashcards (el detalle vive en flashcardsSmoke) ---------------
  await page.getByRole("tab", { name: "Flashcards", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Flashcards", exact: true })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  // El panel de la pantalla envuelve al de Flashcards: dos niveles de tabpanel.
  await expect(page.getByRole("tabpanel", { name: "Flashcards", exact: true })).toHaveAttribute(
    "aria-labelledby",
    "dictionary-tab-flashcards",
  );
  await expect(page.getByRole("tabpanel", { name: "Study", exact: true })).toHaveAttribute(
    "aria-labelledby",
    "flashcards-tab-study",
  );
  await page.waitForTimeout(400);
  await page.screenshot({ path: shot("dictionary-flashcards"), fullPage: true });
});
