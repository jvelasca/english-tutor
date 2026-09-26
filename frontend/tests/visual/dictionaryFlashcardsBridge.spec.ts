import { test, expect, type Page } from "@playwright/test";
import { ensureProfile } from "./gateHelper";

/**
 * Sonda visual permanente del PUENTE Diccionario → Flashcards (V3.83.0, V3.84.0,
 * V3.84.1).
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
 * - V3.84.1: si esa SEGUNDA escritura falla, el alta NO se declara en error: el
 *   aprendizaje ya está hecho y la UI lo declara como PARCIAL, ofreciendo
 *   reintentar SOLO la tarjeta (sin repetir el alta del léxico).
 *
 * Determinista: mockea el diccionario, el léxico, las colecciones y los mazos, y
 * **construye la cola de cada mazo con lo que de verdad entró** (el léxico para
 * el mazo automático, las tarjetas creadas para los manuales). Así «la tarjeta
 * aparece en el mazo» es consecuencia del alta, no un fixture paralelo.
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
  /** Tarjetas que ENTRARON en un mazo manual (los intentos fallidos no cuentan). */
  cardPosts: Array<Record<string, unknown>>;
  deckPosts: Array<Record<string, unknown>>;
  /** Tarjetas vivas por mazo manual: lo que la cola de ese mazo sirve. */
  cardsByDeck: Record<number, Array<{ id: number; front: string; back: string }>>;
  /** Palabras que entraron en el léxico: lo que sirve el mazo automático. */
  lexiconWords: string[];
  /** Intentos de crear tarjeta, incluidos los que fallan (estado parcial). */
  cardAttempts: number;
  /** Mazos manuales vivos: el inicial + los creados desde el panel. */
  manualDecks: Array<Record<string, unknown>>;
}

interface BridgeOptions {
  /** V3.84.1: falla las primeras N creaciones de tarjeta. Sirve para provocar el
   *  estado PARCIAL —el alta del léxico entra y la tarjeta no— y su reintento. */
  failCardTimes?: number;
}

/**
 * Un único route, anclado al ORIGEN, para todo `/api/**` (V3.80.1). `/api/users`
 * y `/api/session` se dejan pasar a la cadena porque de ellos se encarga
 * `ensureProfile`, cuyas routes se registran después y por tanto ganan.
 */
async function installBridgeMocks(
  page: Page,
  entry: Record<string, unknown>,
  options: BridgeOptions = {},
): Promise<BridgeState> {
  const failCardTimes = options.failCardTimes ?? 0;
  const state: BridgeState = {
    dictionaryHits: 0,
    deckListCalls: 0,
    itemPosts: [],
    cardPosts: [],
    deckPosts: [],
    cardsByDeck: {},
    lexiconWords: [],
    cardAttempts: 0,
    manualDecks: [{ ...MANUAL_DECK }],
  };
  let nextDeckId = 8;
  let nextCardId = 1;

  /** Cola de un mazo derivada de lo que entró de verdad, no de un fixture. */
  function queueFor(deckId: number): Record<string, unknown> {
    const deck =
      deckId === AUTO_DECK.id
        ? AUTO_DECK
        : state.manualDecks.find((d) => d.id === deckId) ?? AUTO_DECK;
    const items =
      deckId === AUTO_DECK.id
        ? state.lexiconWords.map((word) => ({
            card_type: "lexicon",
            card_id: word,
            front: word,
            back: "",
            definition: "",
            is_new: true,
            state: "new",
            due_at: "",
            reps: 0,
            retrievability: 0,
          }))
        : (state.cardsByDeck[deckId] ?? []).map((card) => ({
            card_type: "flashcard",
            card_id: String(card.id),
            front: card.front,
            back: card.back,
            definition: "",
            is_new: true,
            state: "new",
            due_at: "",
            reps: 0,
            retrievability: 0,
          }));
    return {
      deck: { ...deck, card_count: items.length },
      items,
      due_count: 0,
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
    // El alta del léxico (léxico + carta FSRS). Es la PRIMERA escritura.
    if (pathname === "/api/vocabulary/items" && method === "POST") {
      const body = (request.postDataJSON() ?? {}) as Record<string, unknown>;
      state.itemPosts.push(body);
      const word = String(body.word ?? "");
      if (word) state.lexiconWords.push(word);
      return route.fulfill({
        json: {
          added: [word],
          item: { word, translation: "", definition: "" },
        },
      });
    }
    // La tarjeta del mazo manual (V3.84.0): anverso/reverso. Es la SEGUNDA
    // escritura; `failCardTimes` permite que falle para probar el reintento.
    const cardMatch = pathname.match(
      /^\/api\/vocabulary\/decks\/([^/]+)\/cards$/,
    );
    if (cardMatch && method === "POST") {
      state.cardAttempts += 1;
      if (state.cardAttempts <= failCardTimes) {
        return route.fulfill({ status: 500, json: { detail: "boom" } });
      }
      const body = (request.postDataJSON() ?? {}) as Record<string, unknown>;
      state.cardPosts.push(body);
      const deckId = Number(cardMatch[1]);
      const card = {
        id: nextCardId,
        front: String(body.front ?? ""),
        back: String(body.back ?? ""),
      };
      nextCardId += 1;
      (state.cardsByDeck[deckId] ??= []).push(card);
      return route.fulfill({
        json: {
          id: card.id,
          deck_id: deckId,
          front: card.front,
          back: card.back,
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
          auto_deck_id: AUTO_DECK.id,
          decks: [AUTO_DECK, ...state.manualDecks],
          fsrs_version: "test",
        },
      });
    }
    // Crear un mazo desde el propio panel (V3.84.0): el mazo pasa a existir de
    // verdad y su cola queda disponible para el salto a Flashcards.
    if (pathname === "/api/vocabulary/decks" && method === "POST") {
      const body = (request.postDataJSON() ?? {}) as Record<string, unknown>;
      state.deckPosts.push(body);
      const deck = {
        ...MANUAL_DECK,
        id: nextDeckId,
        name: String(body.name ?? ""),
        slug: "",
      };
      nextDeckId += 1;
      state.manualDecks.push(deck);
      return route.fulfill({ json: deck });
    }
    const queueMatch = pathname.match(
      /^\/api\/vocabulary\/decks\/([^/]+)\/queue$/,
    );
    if (queueMatch) {
      return route.fulfill({ json: queueFor(Number(queueMatch[1])) });
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

test("EN→ES: el alta lleva la traducción y la tarjeta aparece en el mazo elegido", async ({
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
  const select = page.getByLabel("Also save it as a card in a deck (optional)");
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

  // Salida natural: el modo Flashcards de la propia pantalla, con ESE mazo.
  await page.getByRole("button", { name: "Study in Flashcards" }).click();
  await expect(
    page.getByRole("tab", { name: "Flashcards", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  // El salto abre la sesión del mazo elegido (no la del automático) y su cola
  // sirve la tarjeta que acaba de entrar. El nombre que declara la sesión es lo
  // que demuestra QUE mazo se abrió: si se abriera el automático diría
  // «My dictionary».
  await expect(
    page.getByRole("heading", { name: "Mi mazo", level: 2 }),
  ).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("nebula", { exact: true })).toBeVisible();
});

test("ES→EN: se añade el EQUIVALENTE INGLÉS, nunca el término español, y queda en el mazo automático", async ({
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
  // Sin mazo elegido: SOLO aprendizaje (léxico + carta FSRS).
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
  // Sin mazo elegido NO se crea tarjeta manual: es una sola escritura.
  expect(state.cardPosts).toHaveLength(0);

  // Y el aprendizaje es real: el mazo automático («Mi diccionario») sirve la
  // palabra, porque el alta del léxico es lo que deriva su carta FSRS.
  await page.getByRole("button", { name: "Study in Flashcards" }).click();
  await expect(
    page.getByRole("tab", { name: "Flashcards", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByRole("heading", { name: "My dictionary", level: 2 }),
  ).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("house", { exact: true })).toBeVisible();
});

test("V3.84.1: crear el mazo en el panel, añadir y estudiar ese mazo muestra la tarjeta", async ({
  page,
}) => {
  await page.goto("/");
  const state = await installBridgeMocks(page, EN_ENTRY);
  await ensureProfile(page);
  await page.goto("/#/diccionario");

  await lookup(page, "nebula");
  await page.getByRole("button", { name: "Add to Flashcards" }).click();

  const select = page.getByLabel("Also save it as a card in a deck (optional)");
  await select.selectOption("__new__");
  await page.getByLabel("New deck name").fill("Verbos");
  await page.getByRole("button", { name: "Create deck" }).click();

  // El mazo se crea sin salir del panel y queda seleccionado.
  await expect(select).toHaveValue("8");
  expect(state.deckPosts).toHaveLength(1);
  expect(state.deckPosts[0]).toMatchObject({ name: "Verbos" });

  await page.getByRole("button", { name: "Add and start learning" }).click();
  await expect(page.getByText("nebula is now learning.")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText("Saved as a card in “Verbos”.")).toBeVisible();

  // «Estudiar en Flashcards» abre el mazo RECIÉN creado y su tarjeta está ahí.
  await page.getByRole("button", { name: "Study in Flashcards" }).click();
  await expect(
    page.getByRole("heading", { name: "Verbos", level: 2 }),
  ).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("nebula", { exact: true })).toBeVisible();
});

test("V3.84.1: si falla la tarjeta, declara el estado PARCIAL y el reintento no repite el alta", async ({
  page,
}) => {
  await page.goto("/");
  const state = await installBridgeMocks(page, EN_ENTRY, { failCardTimes: 1 });
  await ensureProfile(page);
  await page.goto("/#/diccionario");

  await lookup(page, "nebula");
  await page.getByRole("button", { name: "Add to Flashcards" }).click();
  const select = page.getByLabel("Also save it as a card in a deck (optional)");
  await select.selectOption("7");
  await page.getByRole("button", { name: "Add and start learning" }).click();

  // Estado PARCIAL: ni «ok» (mentiría) ni un «error» genérico. La primera
  // escritura (léxico) entró; la segunda (tarjeta) falló una vez.
  await expect(
    page.getByText(/is now learning, but it could not be saved in/),
  ).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Mi mazo")).toBeVisible();
  expect(state.itemPosts).toHaveLength(1);
  expect(state.cardAttempts).toBe(1);
  expect(state.cardPosts).toHaveLength(0);
  // El aprendizaje ya está hecho: estudiar sigue disponible.
  await expect(
    page.getByRole("button", { name: "Study in Flashcards" }),
  ).toBeVisible();

  // Reintento explícito: SOLO la tarjeta, y cierra en el éxito completo.
  await page.getByRole("button", { name: "Retry saving to the deck" }).click();
  await expect(page.getByText(/Saved as a card in “Mi mazo”/)).toBeVisible({
    timeout: 15_000,
  });
  expect(state.cardAttempts).toBe(2);
  expect(state.cardPosts).toHaveLength(1);
  // El reintento NO repite el alta del léxico: sigue habiendo UNA sola.
  expect(state.itemPosts).toHaveLength(1);
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
