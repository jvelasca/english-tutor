import { test, expect, type Page } from "@playwright/test";
import { ensureProfile } from "./gateHelper";

/**
 * Sonda visual permanente de la SESIÓN DE ESTUDIO por teclado (V3.83.0).
 *
 * La release convierte calificar en un gesto de juego con los atajos 1–4. Ese
 * contrato tiene dos mitades que se pueden romper sin que falle ningún test
 * unitario: (a) el atajo califica y avanza; y (b) el atajo **no** se dispara
 * mientras se escribe el reverso propio (el campo captura el número). Esta sonda
 * fija las dos en los tres breakpoints.
 *
 * Determinista: mockea mazos, cola y la respuesta de calificación.
 */

const AUTO_DECK = {
  id: 0,
  slug: "auto",
  name: "auto",
  is_auto: true,
  new_per_day: 10,
  review_per_day: 50,
  card_count: 2,
  due_count: 2,
  new_count: 2,
  reviewed_today: 0,
};

const CARD_ONE = {
  card_type: "lexicon",
  card_id: "airport",
  front: "airport",
  back: "aeropuerto",
  definition: "A place where aircraft take off and land.",
  is_new: true,
  state: "new",
  due_at: "",
  reps: 0,
  retrievability: 1,
};

const CARD_TWO = {
  ...CARD_ONE,
  card_id: "ticket",
  front: "ticket",
  back: "billete",
  definition: "A piece of paper that shows you have paid.",
};

const QUEUE = {
  deck: AUTO_DECK,
  items: [CARD_ONE, CARD_TWO],
  due_count: 2,
  new_count: 2,
  reviewed_today: 0,
  new_today: 0,
  limits: {
    new_per_day: 10,
    review_per_day: 50,
    new_remaining: 8,
    review_remaining: 50,
  },
  fsrs_version: "test",
};

const VOICES = {
  voices: [],
  downloadable: [],
  default: "en_GB-alan-medium",
  selected: "en_GB-alan-medium",
};

const REVIEWS: Array<Record<string, unknown>> = [];

async function installStudyMocks(page: Page) {
  REVIEWS.length = 0;
  await page.route(/^https?:\/\/[^/]+\/api\//, (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();

    if (pathname === "/api/users" || pathname === "/api/session") {
      return route.fallback();
    }
    if (pathname === "/api/vocabulary/decks") {
      return route.fulfill({
        json: { auto_deck_id: 0, decks: [AUTO_DECK], fsrs_version: "test" },
      });
    }
    if (/^\/api\/vocabulary\/decks\/[^/]+\/queue$/.test(pathname)) {
      return route.fulfill({ json: QUEUE });
    }
    if (/^\/api\/vocabulary\/decks\/[^/]+\/review$/.test(pathname)) {
      REVIEWS.push((request.postDataJSON() ?? {}) as Record<string, unknown>);
      return route.fulfill({
        json: { card: {}, grade: 3, due_at: "", next_in_days: 1 },
      });
    }
    if (pathname === "/api/vocabulary/lexicon") {
      return route.fulfill({
        json: {
          summary: { total: 0, known: 0, learning: 0, weak: 0, mastered: 0, by_cefr: [] },
          items: [],
        },
      });
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
    return route.fulfill({ json: method === "GET" ? {} : { ok: true } });
  });
}

async function startSession(page: Page) {
  await page.goto("/");
  await installStudyMocks(page);
  await ensureProfile(page);
  await page.goto("/#/diccionario");
  await page.getByRole("tab", { name: "Flashcards", exact: true }).click();
  await expect(page.getByText("2 cards due")).toBeVisible({ timeout: 15_000 });
  // V3.85.0: el botón pasó a llamarse «Study cards (N)» porque el bloque de
  // estudio ahora ofrece DOS acciones y esta es la de la cola FSRS (la otra,
  // «Review now (N)», es el drill de competencia).
  await page
    .getByRole("button", { name: /Study cards|Estudiar tarjetas/ })
    .click();
  await expect(page.getByRole("button", { name: "Flip card" })).toBeVisible({
    timeout: 15_000,
  });
}

test("los atajos 1–4 califican y avanzan hasta el resumen", async ({ page }) => {
  await startSession(page);

  // Primera tarjeta: voltear y calificar con «3» (Good).
  await page.getByRole("button", { name: "Flip card" }).click();
  await expect(page.getByText("aeropuerto")).toBeVisible();
  await page.keyboard.press("3");
  await expect(page.getByText("2 / 2")).toBeVisible({ timeout: 15_000 });

  // Segunda tarjeta: voltear y calificar con «4» (Easy).
  await page.getByRole("button", { name: "Flip card" }).click();
  await expect(page.getByText("billete")).toBeVisible();
  await page.keyboard.press("4");

  // Dos tarjetas, dos grados >= 3: acierto de la sesión = 100 %.
  await expect(
    page.getByText("Session done — 2 cards reviewed."),
  ).toBeVisible({ timeout: 15_000 });
  await expect(
    page.getByText("100% of this session rated Good or Easy."),
  ).toBeVisible();

  // Un grado por tarjeta, sin dobles registros por los atajos.
  expect(REVIEWS).toHaveLength(2);
  expect(REVIEWS[0]).toMatchObject({ card_id: "airport", grade: 3 });
  expect(REVIEWS[1]).toMatchObject({ card_id: "ticket", grade: 4 });
});

test("el atajo no se dispara mientras se escribe el reverso propio", async ({
  page,
}) => {
  await startSession(page);

  await page.getByRole("button", { name: "Flip card" }).click();
  await page.getByRole("button", { name: "Correct the reverse" }).click();

  const editor = page.getByLabel("Reverse side (Spanish)");
  await expect(editor).toBeVisible();
  await editor.click();
  // Escribir un número en el campo NO puede calificar la tarjeta.
  await page.keyboard.press("3");
  await page.keyboard.press("4");
  await expect(editor).toHaveValue(/3/);
  // La sesión sigue en la primera tarjeta: sin avance por el atajo.
  await expect(page.getByText("1 / 2")).toBeVisible();
  expect(REVIEWS).toHaveLength(0);

  // Al cerrar la edición, el atajo vuelve a funcionar.
  await page.keyboard.press("Escape");
  await page.keyboard.press("3");
  await expect(page.getByText("2 / 2")).toBeVisible({ timeout: 15_000 });
  expect(REVIEWS).toHaveLength(1);
});
