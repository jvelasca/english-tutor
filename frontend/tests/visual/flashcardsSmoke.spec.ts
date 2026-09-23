import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { ensureProfile } from "./gateHelper";

/**
 * Smoke visual permanente de FLASHCARDS (V3.80.1).
 *
 * Cubre la superficie que V3.80.0 dejó sin sonda permanente: las cuatro vistas
 * (Estudiar · Mazos · Tarjetas · Estadísticas), el arranque de una sesión, la
 * guía de mazo vacío y los mazos listos. Corre en los tres breakpoints (390 /
 * 768 / 1280) y captura una imagen por vista y proyecto, para que una regresión
 * de layout se vea sin depender de que alguien recuerde mirarla.
 *
 * Determinista: mockea mazos, cola, tarjetas, estadísticas y colecciones.
 */

const AUTO_DECK = {
  id: 0,
  slug: "auto",
  name: "auto",
  is_auto: true,
  new_per_day: 10,
  review_per_day: 50,
  card_count: 7,
  due_count: 2,
  new_count: 3,
  reviewed_today: 0,
};

const IDIOMS_DECK = {
  id: 5,
  slug: "",
  name: "Idioms",
  is_auto: false,
  new_per_day: 10,
  review_per_day: 50,
  card_count: 1,
  due_count: 1,
  new_count: 0,
  reviewed_today: 0,
};

const EMPTY_DECK = {
  ...IDIOMS_DECK,
  id: 6,
  name: "Phrasal verbs",
  card_count: 0,
  due_count: 0,
  new_count: 0,
};

const STUDY_ITEM = {
  card_type: "lexicon",
  card_id: "airport",
  front: "airport",
  back: "aeropuerto",
  definition: "",
  is_new: true,
  state: "new",
  due_at: "",
  reps: 0,
  retrievability: 1,
};

const QUEUE = {
  deck: AUTO_DECK,
  items: [STUDY_ITEM],
  due_count: 2,
  new_count: 3,
  reviewed_today: 0,
  new_today: 0,
  limits: {
    new_per_day: 10,
    review_per_day: 50,
    new_remaining: 7,
    review_remaining: 48,
  },
  fsrs_version: "test",
};

const CARDS = {
  deck_id: 5,
  cards: [
    {
      id: 11,
      deck_id: 5,
      front: "break a leg",
      back: "mucha suerte",
      state: "new",
      reps: 0,
      due_at: "",
      created_at: "2026-09-22T09:00:00Z",
    },
  ],
};

const STATS = {
  deck: AUTO_DECK,
  cards_total: 7,
  reviewed_today: 1,
  new_today: 1,
  reviews_30d: 4,
  new_cards_30d: 2,
  accuracy_30d: 75,
  by_day: [
    { day: "2026-09-21", total: 3, good: 2, count: 3 },
    { day: "2026-09-22", total: 1, good: 1, count: 1 },
  ],
  forecast: [
    { day: "2026-09-22", count: 2, total: 2, good: 0 },
    { day: "2026-09-23", count: 0, total: 0, good: 0 },
  ],
};

const COLLECTIONS = {
  collections: [
    {
      id: 3,
      kind: "theme_pack",
      slug: "travel",
      title: "Travel",
      title_es: "Viajes",
      cefr_hint: "A2",
      item_count: 12,
      enrolled: false,
      is_global: true,
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
 * OJO con los globs: un `**​/api/voices*` casa también con el módulo de la app
 * `/src/api/voices.ts`, y servirle JSON **deja la app sin arrancar** (el navegador
 * rechaza el módulo por MIME). Es la misma trampa que ya documenta
 * `drillProvenance.spec.ts`. Anclar el patrón a `https://<host>/api/` deja fuera
 * `/src/api/**` y no hay colisiones posibles.
 *
 * `/api/users` y `/api/session` se dejan pasar a la cadena (`fallback`) porque de
 * ellos se encarga `ensureProfile`, que registra sus routes **después**: en
 * Playwright gana la última registrada, así que la identidad sigue siendo suya.
 */
async function installFlashcardMocks(page: Page) {
  await page.route(/^https?:\/\/[^/]+\/api\//, (route) => {
    const { pathname } = new URL(route.request().url());
    const method = route.request().method();

    if (pathname === "/api/users" || pathname === "/api/session") {
      return route.fallback();
    }
    if (pathname === "/api/vocabulary/decks") {
      return route.fulfill({
        json: {
          auto_deck_id: 0,
          decks: [AUTO_DECK, IDIOMS_DECK, EMPTY_DECK],
          fsrs_version: "test",
        },
      });
    }
    if (/^\/api\/vocabulary\/decks\/[^/]+\/queue$/.test(pathname)) {
      return route.fulfill({ json: QUEUE });
    }
    if (/^\/api\/vocabulary\/decks\/[^/]+\/cards$/.test(pathname)) {
      return route.fulfill({ json: CARDS });
    }
    if (/^\/api\/vocabulary\/decks\/[^/]+\/stats$/.test(pathname)) {
      return route.fulfill({ json: STATS });
    }
    if (pathname === "/api/vocabulary/collections") {
      return route.fulfill({ json: COLLECTIONS });
    }
    if (pathname === "/api/vocabulary/lexicon") {
      return route.fulfill({
        json: {
          summary: {
            total: 1,
            known: 0,
            learning: 1,
            weak: 0,
            mastered: 0,
            by_cefr: [],
          },
          items: [],
        },
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

test("smoke de Flashcards: cuatro vistas y una sesión (3 breakpoints)", async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name;
  const shot = (name: string) =>
    path.join("tests", "visual", "screenshots", project, `${name}.png`);

  await page.goto("/");
  // Los mocks se registran ANTES de `ensureProfile`: su `page.reload()` es la
  // carga con la que arranca la app bajo el contrato determinista.
  await installFlashcardMocks(page);
  await ensureProfile(page);
  await page.goto("/#/diccionario");

  const flashcardsTab = page.getByRole("tab", { name: "Flashcards", exact: true });
  await expect(flashcardsTab).toBeVisible({ timeout: 15_000 });
  await flashcardsTab.click();
  await expect(flashcardsTab).toHaveAttribute("aria-selected", "true");

  // --- Estudiar -----------------------------------------------------------
  const studyTab = page.getByRole("tab", { name: "Study", exact: true });
  await expect(studyTab).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel", { name: "Study", exact: true })).toHaveAttribute(
    "aria-labelledby",
    "flashcards-tab-study",
  );
  await expect(page.getByText("1 cards due")).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(400);
  await page.screenshot({ path: shot("flashcards-study"), fullPage: true });

  // La sesión: anverso, volteo (con el reverso que ya sirvió el backend).
  await page.getByRole("button", { name: /Start session/ }).click();
  await expect(page.getByText("airport")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: "Flip card" }).click();
  await expect(page.getByText("aeropuerto")).toBeVisible();
  await page.waitForTimeout(400);
  await page.screenshot({ path: shot("flashcards-session"), fullPage: true });
  await page.getByRole("button", { name: "End session" }).click();

  // --- Mazos --------------------------------------------------------------
  await page.getByRole("tab", { name: "Decks", exact: true }).click();
  await expect(page.getByRole("tabpanel", { name: "Decks", exact: true })).toHaveAttribute(
    "aria-labelledby",
    "flashcards-tab-decks",
  );
  await expect(page.getByText("My decks")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Idioms")).toBeVisible();
  await expect(page.getByText("Ready-made decks")).toBeVisible();
  await page.waitForTimeout(400);
  await page.screenshot({ path: shot("flashcards-decks"), fullPage: true });

  // --- Tarjetas -----------------------------------------------------------
  await page.getByRole("tab", { name: "Cards", exact: true }).click();
  await expect(page.getByRole("tabpanel", { name: "Cards", exact: true })).toHaveAttribute(
    "aria-labelledby",
    "flashcards-tab-cards",
  );
  await expect(page.getByText("break a leg")).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(400);
  await page.screenshot({ path: shot("flashcards-cards"), fullPage: true });

  // --- Estadísticas -------------------------------------------------------
  await page.getByRole("tab", { name: "Stats", exact: true }).click();
  await expect(page.getByRole("tabpanel", { name: "Stats", exact: true })).toHaveAttribute(
    "aria-labelledby",
    "flashcards-tab-stats",
  );
  await expect(page.getByText("Accuracy")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("75%")).toBeVisible();
  await page.waitForTimeout(400);
  await page.screenshot({ path: shot("flashcards-stats"), fullPage: true });
});
