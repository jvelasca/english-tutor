import { test, expect, type Page } from "@playwright/test";
import { ensureProfile } from "./gateHelper";

/**
 * Sonda visual permanente del PUENTE Diccionario → Flashcards (V3.83.0, V3.84.0).
 *
 * La release promete, en pantalla, una equivalencia: «añadir desde el diccionario
 * deja la palabra en aprendizaje y en el proceso de estudio». Esa promesa no
 * añade endpoint, así que **la única forma de vigilarla** es fijar el contrato de
 * lo que el navegador envía y de lo que dice la UI:
 *
 * - EN→ES envía el término inglés y su traducción;
 * - ES→EN envía el EQUIVALENTE INGLÉS como palabra de práctica (nunca el español);
 * - una palabra ya rastreada NO se re-da de alta (no hay POST de alta);
 * - V3.84.0: el selector de **mazos** manuales es perezoso, no ofrece el mazo
 *   automático, y al elegir uno se crea además la tarjeta (`front`/`back`).
 *
 * Determinista: mockea el diccionario, el léxico, las colecciones y los mazos.
 * La identidad la resuelve `ensureProfile`.
 */

const LEXICON = {
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

const AUTO_DECK = {
  id: 0,
  slug: "auto",
  name: "auto",
  is_auto: true,
  new_per_day: 10,
  review_per_day: 50,
  card_count: 0,
  due_count: 0,
  new_count: 0,
  reviewed_today: 0,
};

/** Mazo manual: el único destino válido del alta. */
const MANUAL_DECK = {
  ...AUTO_DECK,
  id: 7,
  slug: "mi-mazo",
  name: "Mi mazo",
  is_auto: false,
};

const QUEUE = {
  deck: AUTO_DECK,
  items: [],
  due_count: 0,
  new_count: 0,
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

const VOICES = {
  voices: [],
  downloadable: [],
  default: "en_GB-alan-medium",
  selected: "en_GB-alan-medium",
};

const UNTRACKED_USAGE = { tracked: false, surface: null, unit: null };

function trackedUsage() {
  return {
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
  };
}

const EN_ENTRY = {
  word: "nebula",
  kind: "word",
  cefr: "B2",
  definition_source: "llm",
  pos: "noun",
  definition: "A cloud of gas and dust in space.",
  translation: "nebulosa",
  direction: "en-es",
  alternatives: [],
  example: null,
  usage: UNTRACKED_USAGE,
};

const ES_ENTRY = {
  word: "casa",
  kind: "word",
  cefr: "A1",
  definition_source: "llm",
  pos: "noun",
  definition: "A building where people live.",
  translation: "house",
  direction: "es-en",
  alternatives: ["home"],
  example: null,
  usage: UNTRACKED_USAGE,
};

const TRACKED_ENTRY = {
  word: "coffee",
  kind: "word",
  cefr: "A1",
  definition_source: "llm",
  pos: "noun",
  definition: "A hot drink made from roasted coffee beans.",
  translation: "café",
  direction: "en-es",
  alternatives: [],
  example: null,
  usage: trackedUsage(),
};

interface BridgeState {
  dictionaryHits: number;
  deckListCalls: number;
  itemPosts: Array<Record<string, unknown>>;
  cardPosts: Array<Record<string, unknown>>;
}

/**
 * Un único route, anclado al ORIGEN, para todo `/api/**` (V3.80.1). `/api/users`
 * y `/api/session` se dejan pasar a la cadena porque de ellos se encarga
 * `ensureProfile`, cuyas routes se registran después y por tanto ganan.
 */
async function installBridgeMocks(
  page: Page,
  entry: Record<string, unknown>,
): Promise<BridgeState> {
  const state: BridgeState = {
    dictionaryHits: 0,
    deckListCalls: 0,
    itemPosts: [],
    cardPosts: [],
  };

  await page.route(/^https?:\/\/[^/]+\/api\//, (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();

    if (pathname === "/api/users" || pathname === "/api/session") {
      return route.fallback();
    }
    if (pathname === "/api/vocabulary/dictionary") {
      state.dictionaryHits += 1;
      return route.fulfill({ json: entry });
    }
    if (pathname === "/api/vocabulary/items" && method === "POST") {
      const body = (request.postDataJSON() ?? {}) as Record<string, unknown>;
      state.itemPosts.push(body);
      return route.fulfill({
        json: {
          added: [String(body.word ?? "")],
          item: { word: String(body.word ?? ""), translation: "", definition: "" },
        },
      });
    }
    // La tarjeta del mazo manual (V3.84.0): anverso/reverso. Va ANTES que la
    // ruta de la lista de mazos, aunque son paths distintos (ambos anclados).
    if (
      /^\/api\/vocabulary\/decks\/[^/]+\/cards$/.test(pathname) &&
      method === "POST"
    ) {
      const body = (request.postDataJSON() ?? {}) as Record<string, unknown>;
      state.cardPosts.push(body);
      return route.fulfill({
        json: {
          id: 1,
          deck_id: 7,
          front: body.front ?? "",
          back: body.back ?? "",
          state: "new",
          reps: 0,
          due_at: "",
          created_at: "2026-09-25T10:00:00Z",
        },
      });
    }
    if (pathname === "/api/vocabulary/decks" && method === "GET") {
      state.deckListCalls += 1;
      return route.fulfill({
        json: {
          auto_deck_id: 0,
          decks: [AUTO_DECK, MANUAL_DECK],
          fsrs_version: "test",
        },
      });
    }
    if (/^\/api\/vocabulary\/decks\/[^/]+\/queue$/.test(pathname)) {
      return route.fulfill({ json: QUEUE });
    }
    if (pathname === "/api/vocabulary/collections") {
      return route.fulfill({ json: { collections: [] } });
    }
    if (pathname === "/api/vocabulary/lexicon") {
      return route.fulfill({ json: LEXICON });
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

  return state;
}

/** Abre el diccionario en modo Consultar y busca la palabra. */
async function lookup(page: Page, word: string) {
  await page.getByRole("tab", { name: "Look up", exact: true }).click();
  await page.getByLabel("Search the dictionary").fill(word);
  await page.getByRole("button", { name: "Look up" }).click();
  await expect(page.getByRole("heading", { name: word })).toBeVisible({
    timeout: 15_000,
  });
}

test("EN→ES: el alta lleva la traducción y guarda la tarjeta en el mazo elegido", async ({
  page,
}) => {
  await page.goto("/");
  const state = await installBridgeMocks(page, EN_ENTRY);
  await ensureProfile(page);
  await page.goto("/#/diccionario");

  await lookup(page, "nebula");

  // Perezoso: los mazos NO se piden al buscar; se piden al abrir el panel.
  expect(state.deckListCalls).toBe(0);

  await page.getByRole("button", { name: "Add to Flashcards" }).click();
  await expect(page.getByText(/The word always joins your study flow/)).toBeVisible({
    timeout: 15_000,
  });
  expect(state.deckListCalls).toBe(1);

  // El selector ofrece el mazo manual y NO el mazo automático.
  const select = page.getByRole("combobox");
  const options = await select.locator("option").allInnerTexts();
  expect(options).toContain("Mi mazo");
  expect(options).not.toContain("auto");

  await select.selectOption("7");
  await page.getByRole("button", { name: "Add and start learning" }).click();

  await expect(page.getByText("nebula is now learning.")).toBeVisible({
    timeout: 15_000,
  });
  // El alta de léxico es el MISMO endpoint de siempre y viaja con la traducción.
  expect(state.itemPosts).toHaveLength(1);
  expect(state.itemPosts[0]).toMatchObject({
    word: "nebula",
    translation: "nebulosa",
    collection_id: null,
  });
  // V3.84.0: además, la tarjeta del mazo manual con anverso y reverso.
  expect(state.cardPosts).toHaveLength(1);
  expect(state.cardPosts[0]).toMatchObject({ front: "nebula", back: "nebulosa" });
  await expect(page.getByText(/Saved as a card in/)).toBeVisible();

  // Salida natural: el modo Flashcards de la propia pantalla.
  await page.getByRole("button", { name: "Study in Flashcards" }).click();
  await expect(
    page.getByRole("tab", { name: "Flashcards", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
});

test("ES→EN: se añade el EQUIVALENTE INGLÉS, nunca el término español", async ({
  page,
}) => {
  await page.goto("/");
  const state = await installBridgeMocks(page, ES_ENTRY);
  await ensureProfile(page);
  await page.goto("/#/diccionario");

  await page.getByRole("tab", { name: "Look up", exact: true }).click();
  await page.getByRole("button", { name: "Spanish → English" }).click();
  await page.getByLabel("Search the dictionary").fill("casa");
  await page.getByRole("button", { name: "Look up" }).click();
  await expect(page.getByRole("heading", { name: "casa" })).toBeVisible({
    timeout: 15_000,
  });

  await page.getByRole("button", { name: "Add to Flashcards" }).click();
  await page.getByRole("button", { name: "Add and start learning" }).click();

  await expect(page.getByText("house is now learning.")).toBeVisible({
    timeout: 15_000,
  });
  // La tarjeta estudia el término inglés: `word` = house, `translation` = casa.
  expect(state.itemPosts).toHaveLength(1);
  expect(state.itemPosts[0]).toMatchObject({
    word: "house",
    translation: "casa",
    collection_id: null,
  });
  // Sin mazo elegido no se crea tarjeta manual.
  expect(state.cardPosts).toHaveLength(0);
});

test("una palabra ya rastreada no se re-da de alta: declara el vínculo y ofrece estudiar", async ({
  page,
}) => {
  await page.goto("/");
  const state = await installBridgeMocks(page, TRACKED_ENTRY);
  await ensureProfile(page);
  await page.goto("/#/diccionario");

  await lookup(page, "coffee");

  await expect(page.getByText(/Already in your dictionary/)).toBeVisible({
    timeout: 15_000,
  });
  // No se ofrece un alta que no cambiaría nada...
  await expect(
    page.getByRole("button", { name: "Add to Flashcards" }),
  ).toHaveCount(0);
  // ...y no se abre el panel, así que tampoco se piden mazos.
  expect(state.deckListCalls).toBe(0);

  // La salida sigue existiendo: estudiar.
  await page.getByRole("button", { name: "Study in Flashcards" }).click();
  await expect(
    page.getByRole("tab", { name: "Flashcards", exact: true }),
  ).toHaveAttribute("aria-selected", "true");

  // Y no ha habido ningún POST de alta.
  expect(state.itemPosts).toHaveLength(0);
});
