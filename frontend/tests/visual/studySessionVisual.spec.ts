import { test, expect, type Page } from "@playwright/test";
import { ensureProfile } from "./gateHelper";

/**
 * Sonda visual permanente de la SESIÓN DE ESTUDIO: anuncio del progreso, texto
 * largo y `prefers-reduced-motion` (V3.83.0).
 *
 * Tres promesas de la release que solo se pueden comprobar pintando:
 * 1. la barra de progreso no solo se ve: **se anuncia** (`aria-valuenow`);
 * 2. el volteo 3D **no rompe el layout** con un reverso largo en pantalla pequeña;
 * 3. con «reducir movimiento» el volteo se apaga pero **la información no cambia**.
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

const LONG_BACK =
  "billete de ida y vuelta con derecho a equipaje facturado, selección de asiento y cambio de fecha sin coste adicional";
const LONG_DEFINITION =
  "A document issued by a carrier that entitles the holder to travel between two points, including any baggage allowance, seat reservation or change conditions agreed at the time of purchase.";

const LONG_CARD = {
  ...CARD_ONE,
  card_id: "round-trip",
  front: "round-trip ticket",
  back: LONG_BACK,
  definition: LONG_DEFINITION,
};

const VOICES = {
  voices: [],
  downloadable: [],
  default: "en_GB-alan-medium",
  selected: "en_GB-alan-medium",
};

function queueWith(items: unknown[]) {
  return {
    deck: AUTO_DECK,
    items,
    due_count: items.length,
    new_count: items.length,
    reviewed_today: 0,
    new_today: 0,
    limits: {
      new_per_day: 10,
      review_per_day: 50,
      new_remaining: 10,
      review_remaining: 50,
    },
    fsrs_version: "test",
  };
}

async function installStudyMocks(page: Page, items: unknown[]) {
  const queue = queueWith(items);
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
      return route.fulfill({ json: queue });
    }
    if (/^\/api\/vocabulary\/decks\/[^/]+\/review$/.test(pathname)) {
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

async function startSession(page: Page, items: unknown[]) {
  await page.goto("/");
  await installStudyMocks(page, items);
  await ensureProfile(page);
  await page.goto("/#/diccionario");
  await page.getByRole("tab", { name: "Flashcards", exact: true }).click();
  await expect(page.getByText(`${items.length} cards due`)).toBeVisible({
    timeout: 15_000,
  });
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

test.describe("barra de progreso anunciada", () => {
  test("el progreso se anuncia con aria-valuenow y no solo se pinta", async ({
    page,
  }) => {
    await startSession(page, [CARD_ONE, CARD_TWO]);

    const bar = page.getByRole("progressbar");
    await expect(bar).toBeVisible();
    // Primera de dos tarjetas: 50 %. El `value` llega a la raíz de Radix.
    await expect(bar).toHaveAttribute("aria-valuenow", "50");
    await expect(bar).toHaveAttribute("aria-label", "Card 1 of 2");

    await page.getByRole("button", { name: "Flip card" }).click();
    await page.getByText("Good").click();

    // Última tarjeta: 100 % (extremo superior alcanzable).
    await expect(page.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "100",
    );
  });
});

test("un reverso largo no desborda el layout tras el volteo", async ({ page }) => {
  await startSession(page, [LONG_CARD]);

  await page.getByRole("button", { name: "Flip card" }).click();
  await expect(page.getByText(LONG_BACK)).toBeVisible();
  await expect(page.getByText(LONG_DEFINITION)).toBeVisible();
  await page.waitForTimeout(500);

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  // 1px de tolerancia por redondeo subpíxel.
  expect(overflow).toBeLessThanOrEqual(1);
});

test.describe("prefers-reduced-motion", () => {
  // OJO: `test.use({ reducedMotion })` NO es una opción válida de `test.use` en
  // Playwright 1.62 (no existe como propiedad de `TestOptions`), así que se
  // ignora en silencio y `matchMedia('(prefers-reduced-motion: reduce)')` queda
  // en `false`. La vía que sí emula es `page.emulateMedia`. Este spec se
  // protege con una guarda explícita: si la emulación no está activa, falla en
  // vez de pasar por vacío.

  test("sin volteo 3D, la información de las dos caras sigue disponible", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await startSession(page, [CARD_ONE]);

    // Guarda de mordida: sin esto el test sería vacuo (el fallo que tuvo GUI-05).
    const mediaReduce = await page.evaluate(
      () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    );
    expect(mediaReduce).toBe(true);

    await page.getByRole("button", { name: "Flip card" }).click();

    // El reverso se ve igualmente (la información no depende del movimiento).
    await expect(page.getByText("aeropuerto")).toBeVisible();
    await expect(page.getByRole("button", { name: "Good" })).toBeVisible();

    // Y no queda ninguna rotación 3D en línea: el volteo se ha apagado.
    await page.waitForTimeout(700);
    const rotateInline = await page.evaluate(() =>
      Array.from(document.querySelectorAll("[style]"))
        .map((el) => el.getAttribute("style") ?? "")
        .filter((style) => style.includes("rotateY")),
    );
    expect(rotateInline).toHaveLength(0);
  });
});
