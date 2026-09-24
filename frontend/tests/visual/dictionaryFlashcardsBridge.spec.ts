import { test, expect, type Page } from "@playwright/test";
import { ensureProfile } from "./gateHelper";

/**
 * Sonda visual permanente del PUENTE Diccionario → Flashcards (V3.83.0).
 *
 * La release se declara «SOLO FRONTEND» y promete, en pantalla, una equivalencia:
 * «añadir desde el diccionario deja la palabra en aprendizaje y en el proceso de
 * estudio». Esa promesa no añade endpoint, así que **la única forma de vigilarla**
 * es fijar el contrato de lo que el navegador envía y de lo que dice la UI:
 *
 * - EN→ES envía el término inglés y su traducción;
 * - ES→EN envía el EQUIVALENTE INGLÉS como palabra de práctica (nunca el español);
 * - una palabra ya rastreada NO se re-da de alta (no hay POST de alta);
 * - el selector de listas es perezoso y solo ofrece listas propias (`user_list`),
 *   y archiva con `collection_id` numérico.
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

/** Lista propia (destino de archivo válido) + pack curado (NO es destino). */
const USER_LIST = {
  id: 7,
  kind: "user_list",
  slug: "mi-lista",
  title: "Mi lista",
  title_es: "Mi lista",
  cefr_hint: "",
  item_count: 0,
  enrolled: true,
  is_global: false,
};

const THEME_PACK = {
  id: 3,
  kind: "theme_pack",
  slug: "travel",
  title: "Travel Pack",
  title_es: "Pack Viajes",
  cefr_hint: "A2",
  item_count: 12,
  enrolled: false,
  is_global: true,
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
  collectionCalls: number;
  itemPosts: Array<Record<string, unknown>>;
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
    collectionCalls: 0,
    itemPosts: [],
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
    if (pathname === "/api/vocabulary/collections") {
      state.collectionCalls += 1;
      return route.fulfill({ json: { collections: [THEME_PACK, USER_LIST] } });
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
    if (pathname === "/api/vocabulary/lexicon") {
      return route.fulfill({ json: LEXICON });
    }
    if (pathname === "/api/vocabulary/retention/due") {
      return route.fulfill({
        json: { due_count: 0, limit: 0, items: [], fsrs_version: "test" },
      });
    }
    if (pathname === "/api/vocabulary/decks") {
      return route.fulfill({
        json: { auto_deck_id: 0, decks: [AUTO_DECK], fsrs_version: "test" },
      });
    }
    if (/^\/api\/vocabulary\/decks\/[^/]+\/queue$/.test(pathname)) {
      return route.fulfill({ json: QUEUE });
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

test("EN→ES: el alta lleva la traducción, la lista es perezosa y solo ofrece listas propias", async ({
  page,
}) => {
  await page.goto("/");
  const state = await installBridgeMocks(page, EN_ENTRY);
  await ensureProfile(page);
  await page.goto("/#/diccionario");

  await lookup(page, "nebula");

  // Perezoso: las colecciones NO se piden al buscar; se piden al abrir el panel.
  expect(state.collectionCalls).toBe(0);

  await page.getByRole("button", { name: "Add to Flashcards" }).click();
  await expect(page.getByText(/The word joins your study flow/)).toBeVisible({
    timeout: 15_000,
  });
  expect(state.collectionCalls).toBe(1);

  // El selector ofrece la lista propia y NO el pack curado.
  const select = page.getByRole("combobox");
  const options = await select.locator("option").allInnerTexts();
  expect(options).toContain("Mi lista");
  expect(options).not.toContain("Travel Pack");

  await select.selectOption("7");
  await page.getByRole("button", { name: "Add and start learning" }).click();

  await expect(page.getByText("nebula is now learning.")).toBeVisible({
    timeout: 15_000,
  });
  // El alta es el MISMO endpoint de siempre y viaja con traducción y lista.
  expect(state.itemPosts).toHaveLength(1);
  expect(state.itemPosts[0]).toMatchObject({
    word: "nebula",
    translation: "nebulosa",
    collection_id: 7,
  });

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
  // ...y no se abre el panel, así que tampoco se piden listas.
  expect(state.collectionCalls).toBe(0);

  // La salida sigue existiendo: estudiar.
  await page.getByRole("button", { name: "Study in Flashcards" }).click();
  await expect(
    page.getByRole("tab", { name: "Flashcards", exact: true }),
  ).toHaveAttribute("aria-selected", "true");

  // Y no ha habido ningún POST de alta.
  expect(state.itemPosts).toHaveLength(0);
});
