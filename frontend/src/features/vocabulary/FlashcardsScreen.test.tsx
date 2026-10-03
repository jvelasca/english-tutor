// @vitest-environment jsdom
/**
 * Vitest de `FlashcardsScreen` (V3.78.0): la ÚNICA superficie de estudio.
 *
 * Se mockea la frontera de API entera (los clientes ya normalizan, y ese
 * contrato tiene sus propias pruebas). Lo que se fija aquí es el
 * comportamiento de la pantalla:
 *
 * 1. Las cinco subpestañas existen (V3.85.0 añade «Mi léxico») y Estudiar es la
 *    de entrada.
 * 2. Estudiar muestra los contadores del ámbito y un solo inicio. La lección
 *    cierra la palabra con `complete` (léxico + nota), y el resumen final sigue
 *    siendo alcanzable.
 * 3. El mazo automático no se puede borrar ni editar (no es una fila).
 * 4. El navegador filtra por texto y estado, y el CRUD llama a lo que dice.
 * 5. El salto desde «Mis listas»/packs abre Estudiar con la lista filtrada y
 *    arranca la sesión.
 * 6. «Mi léxico» monta el inventario (buscador, filtros, añadir) sin estudio.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within, act } from "@testing-library/react";
import { I18nProvider } from "../../hooks/useI18n";
import type { FlashcardDeck, StudyQueue } from "../../types/api";
import { FlashcardsScreen } from "./FlashcardsScreen";

vi.mock("../../api/vocabulary", () => ({
  listFlashcardDecks: vi.fn(),
  createFlashcardDeck: vi.fn(),
  updateFlashcardDeck: vi.fn(),
  deleteFlashcardDeck: vi.fn(),
  getStudyQueue: vi.fn(),
  completeStudyLesson: vi.fn(),
  lookupDictionaryWord: vi.fn(),
  requestStudyExample: vi.fn(),
  // V3.86.0: la pestaña Fichas es ficha-primero (una ficha vive en N mazos).
  listVocabularyCards: vi.fn(),
  createVocabularyCard: vi.fn(),
  updateVocabularyCard: vi.fn(),
  deleteVocabularyCard: vi.fn(),
  addFlashcardsBulk: vi.fn(),
  getFlashcardStats: vi.fn(),
  listVocabCollections: vi.fn(),
  enrollVocabCollection: vi.fn(),
  // V3.85.0: la sub-pestaña «Mi léxico» monta el inventario, que lee el léxico,
  // las candidatas del drill oral y el alta de palabras/listas.
  getLexicon: vi.fn(),
  getDrillCandidates: vi.fn(),
  addVocabularyItem: vi.fn(),
  addVocabularyBulk: vi.fn(),
}));

vi.mock("../../components/ItemReplayButton", () => ({
  ItemReplayButton: () => <button type="button">audio</button>,
}));

vi.mock("../../api/study", () => ({
  getStudyConfig: vi.fn(),
  saveStudyConfig: vi.fn(),
}));

import {
  createFlashcardDeck,
  addFlashcardsBulk,
  createVocabularyCard,
  deleteFlashcardDeck,
  deleteVocabularyCard,
  enrollVocabCollection,
  getDrillCandidates,
  completeStudyLesson,
  getFlashcardStats,
  getLexicon,
  getStudyQueue,
  listFlashcardDecks,
  listVocabCollections,
  listVocabularyCards,
  lookupDictionaryWord,
  updateVocabularyCard,
} from "../../api/vocabulary";
import { getStudyConfig, saveStudyConfig } from "../../api/study";
import type { StudyConfig } from "../../types/api";

/** Configuración de estudio por defecto de las pruebas (V3.87.0). */
const DEFAULT_STUDY_CONFIG: StudyConfig = {
  direction: "en-es",
  mode: "recognition",
  hints: "off",
  difficulty: "auto",
  words_per_day: 20,
  required_facets: [],
  configured: false,
};

const AUTO: FlashcardDeck = {
  id: 0,
  slug: "auto",
  name: "auto",
  is_auto: true,
  new_per_day: 10,
  review_per_day: 50,
  card_count: 7,
  shared_count: 0,
  due_count: 2,
  new_count: 3,
  reviewed_today: 0,
};

const MANUAL: FlashcardDeck = {
  id: 5,
  slug: "",
  name: "Idioms",
  is_auto: false,
  new_per_day: 10,
  review_per_day: 50,
  card_count: 1,
  shared_count: 0,
  due_count: 1,
  new_count: 0,
  reviewed_today: 0,
};

function studyQueue(overrides: Partial<StudyQueue> = {}): StudyQueue {
  return {
    scope: "all",
    level: "",
    deck_id: 0,
    collection_id: null,
    items: [
      {
        item_id: "item-airport",
        word: "airport",
        cefr: "A1",
        card_type: "lexicon",
        card_id: "airport",
        deck_id: 0,
        is_new: true,
        translation: "aeropuerto",
        definition: "",
        mnemonic: "",
        facets: {},
        state: "new",
      },
    ],
    total: 12,
    studied: 1,
    learned: 0,
    due: 2,
    times_studied: 4,
    queued: 1,
    mode: "pending",
    study_config: DEFAULT_STUDY_CONFIG,
    ...overrides,
  };
}

function renderScreen(
  props: Partial<Parameters<typeof FlashcardsScreen>[0]> = {},
) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <FlashcardsScreen userId="u1" {...props} />
    </I18nProvider>,
  );
}

describe("FlashcardsScreen", () => {
  beforeEach(() => {
    vi.mocked(listFlashcardDecks).mockResolvedValue({
      auto_deck_id: 0,
      decks: [AUTO, MANUAL],
      fsrs_version: "test",
    });
    vi.mocked(getStudyQueue).mockImplementation(async (_userId, options) =>
      studyQueue({
        scope: options.scope,
        mode: options.mode ?? "pending",
        level: options.level ?? "",
        deck_id: options.deckId ?? 0,
        collection_id: options.collectionId ?? null,
      }),
    );
    vi.mocked(lookupDictionaryWord).mockResolvedValue({
      word: "airport",
      translation: "aeropuerto",
      meanings: [{ term: "aeropuerto", pos: "noun", gloss: "", domain: "", proper_noun: false }],
      senses: [],
      example: null,
    } as never);
    vi.mocked(completeStudyLesson).mockResolvedValue({
      word: "airport",
      learned: false,
      facets: { meaning: "done" },
    });
    vi.mocked(getStudyConfig).mockResolvedValue(DEFAULT_STUDY_CONFIG);
    vi.mocked(saveStudyConfig).mockResolvedValue({
      ...DEFAULT_STUDY_CONFIG,
      configured: true,
    });
    vi.mocked(listVocabularyCards).mockResolvedValue({
      cards: [
        {
          id: 11,
          deck_id: 5,
          deck_ids: [5],
          front: "break a leg",
          back: "mucha suerte",
          mnemonic: "",
          state: "new",
          reps: 0,
          due_at: "",
          created_at: "",
        },
      ],
    } as never);
    vi.mocked(getFlashcardStats).mockResolvedValue({
      deck: AUTO,
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
    });
    // V3.80.0: por defecto no hay packs en el catálogo, así que el bloque «Mazos
    // listos» no se pinta (no se promete lo que no existe). Los tests que lo
    // ejercitan ponen su propio catálogo.
    vi.mocked(listVocabCollections).mockResolvedValue({ collections: [] });
    // «Mi léxico» no se abre salvo que la prueba lo pida; se deja un vacío honesto.
    vi.mocked(getLexicon).mockResolvedValue({
      summary: {
        total: 0,
        known: 0,
        learning: 0,
        weak: 0,
        mastered: 0,
        by_cefr: [],
        recognized: 0,
        produced: 0,
        transfer: 0,
        retention: 0,
        spaced_exposure: 0,
        production_gap: 0,
        transfer_gap: 0,
      },
      items: [],
      coverage: null,
    } as never);
    vi.mocked(getDrillCandidates).mockResolvedValue({ words: [] } as never);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("ofrece las cinco subpestañas y entra por Estudiar", async () => {
    renderScreen();

    expect(await screen.findByRole("tab", { name: "Study" })).toBeTruthy();
    for (const name of ["Study", "My lexicon", "Decks", "Cards", "Stats"]) {
      expect(screen.getByRole("tab", { name })).toBeTruthy();
    }
    expect(
      screen.getByRole("tab", { name: "Study" }).getAttribute("aria-selected"),
    ).toBe("true");
    // La cola del banco (ámbito «Todas») es la de entrada.
    await waitFor(() =>
      expect(getStudyQueue).toHaveBeenCalledWith("u1", {
        scope: "all",
        mode: "pending",
        level: null,
        deckId: 0,
        collectionId: null,
      }),
    );
  });

  it("las vistas son pestañas ARIA y las flechas cambian de vista (V3.80.1)", async () => {
    renderScreen();
    const tablist = await screen.findByRole("tablist", {
      name: "Flashcard views",
    });
    const tabs = within(tablist).getAllByRole("tab");
    expect(tabs).toHaveLength(5);

    const study = screen.getByRole("tab", { name: "Study" });
    study.focus();
    // V3.85.0: «Mi léxico» entra entre Estudiar y Mazos.
    fireEvent.keyDown(study, { key: "ArrowRight" });

    expect(await screen.findByText("Add vocabulary")).toBeTruthy();
    const lexicon = screen.getByRole("tab", { name: "My lexicon" });
    expect(lexicon.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(lexicon);

    fireEvent.keyDown(lexicon, { key: "ArrowRight" });
    expect(await screen.findByPlaceholderText("Deck name")).toBeTruthy();
    const decks = screen.getByRole("tab", { name: "Decks" });
    expect(decks.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(decks);
  });

  it("«Mi léxico» monta el inventario, sin estudio ni repaso (V3.85.0)", async () => {
    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "My lexicon" }));

    // El inventario pide el léxico y las candidatas del drill oral, no la cola
    // de tarjetas ni la de repaso.
    await waitFor(() => expect(getLexicon).toHaveBeenCalledWith("u1"));
    expect(getDrillCandidates).toHaveBeenCalledWith("u1");
    expect(screen.getByText("Add vocabulary")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Study \(/ })).toBeNull();
  });

  it("Estudiar muestra los contadores del banco y un solo inicio", async () => {
    renderScreen();

    expect(await screen.findByText("Total")).toBeTruthy();
    expect(screen.getByText("Studied")).toBeTruthy();
    expect(screen.getByText("Learned")).toBeTruthy();
    expect(screen.getByText("To review")).toBeTruthy();
    expect(screen.getByText("Times studied")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Study (1)" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "All" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
    expect(screen.getByRole("button", { name: "Due" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
    expect(screen.getByRole("button", { name: "Missed" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Whole set" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "My lexicon" })).toBeTruthy();
  });

  it("declara la espera de la cola en vez de decir que el banco está vacío", async () => {
    let resolveQueue: (value: StudyQueue) => void = () => {};
    vi.mocked(getStudyQueue).mockReturnValue(
      new Promise((resolve) => {
        resolveQueue = resolve;
      }) as never,
    );

    renderScreen();

    const statuses = await screen.findAllByRole("status");
    expect(
      statuses.some(
        (el) =>
          el.getAttribute("aria-busy") === "true" &&
          /Loading/.test(el.textContent ?? ""),
      ),
    ).toBe(true);
    expect(
      screen.queryByText(
        "This view of the bank is empty.",
      ),
    ).toBeNull();

    await act(async () => {
      resolveQueue(studyQueue({ items: [], total: 0, queued: 0 }));
    });

    expect(
      await screen.findByText(
        "This view of the bank is empty.",
      ),
    ).toBeTruthy();
  });

  it("estudiar cierra la palabra y el resumen es alcanzable", async () => {
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Study (1)" }));

    expect(screen.getByText("airport")).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Show the meaning" }));
    await waitFor(() => {
      const good = screen.getByRole("button", { name: "Good" }) as HTMLButtonElement;
      expect(good.disabled).toBe(false);
    });
    fireEvent.click(screen.getByRole("button", { name: "Good" }));

    await waitFor(() =>
      expect(completeStudyLesson).toHaveBeenCalledWith(
        "u1",
        expect.objectContaining({
          item_id: "item-airport",
          grade: 3,
        }),
      ),
    );
    expect(await screen.findByText("Session done — 1 cards reviewed.")).toBeTruthy();
  });

  it("el mazo automático se ofrece pero no se puede borrar", async () => {
    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Decks" }));

    expect(await screen.findByText("My dictionary")).toBeTruthy();
    expect(
      screen.getByText("The auto deck cannot be renamed or deleted."),
    ).toBeTruthy();

    // Solo el mazo manual tiene acciones de borrado.
    const deletes = screen.getAllByRole("button", { name: "Delete" });
    expect(deletes).toHaveLength(1);

    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    fireEvent.click(deletes[0]);
    await waitFor(() =>
      expect(deleteFlashcardDeck).toHaveBeenCalledWith("u1", 5),
    );
    confirmSpy.mockRestore();
  });

  it("crear un mazo manda el nombre y recarga la lista", async () => {
    vi.mocked(createFlashcardDeck).mockResolvedValue(MANUAL);
    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Decks" }));

    fireEvent.change(await screen.findByPlaceholderText("Deck name"), {
      target: { value: "Phrasal verbs" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(createFlashcardDeck).toHaveBeenCalledWith("u1", {
        name: "Phrasal verbs",
      }),
    );
  });

  it("el navegador de tarjetas filtra por texto y borra la tarjeta elegida", async () => {
    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Cards" }));

    expect(await screen.findByText("break a leg")).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText("Search front or back…"), {
      target: { value: "zzz" },
    });
    expect(screen.queryByText("break a leg")).toBeNull();
    expect(screen.getByText("No cards match the filter.")).toBeTruthy();

    fireEvent.change(screen.getByPlaceholderText("Search front or back…"), {
      target: { value: "break" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() =>
      expect(deleteVocabularyCard).toHaveBeenCalledWith("u1", 11),
    );
  });

  it("añadir una tarjeta exige anverso y lo envía con el dorso y el mazo", async () => {
    vi.mocked(createVocabularyCard).mockResolvedValue({} as never);
    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Cards" }));
    await screen.findByText("break a leg");

    fireEvent.change(screen.getByPlaceholderText("What you see first…"), {
      target: { value: "on the fly" },
    });
    fireEvent.change(screen.getByPlaceholderText("What you must recall…"), {
      target: { value: "sobre la marcha" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(createVocabularyCard).toHaveBeenCalledWith("u1", {
        front: "on the fly",
        back: "sobre la marcha",
        mnemonic: "",
        deckIds: [5],
      }),
    );
  });

  // --- V3.86.0: una ficha, varios mazos y un recordatorio -------------------

  it("la ficha muestra sus mazos y guarda el recordatorio con casillas (V3.86.0)", async () => {
    const SECOND: FlashcardDeck = {
      ...MANUAL,
      id: 6,
      name: "Travel",
      card_count: 0,
    };
    vi.mocked(listFlashcardDecks).mockResolvedValue({
      auto_deck_id: 0,
      decks: [AUTO, MANUAL, SECOND],
      fsrs_version: "test",
    });
    vi.mocked(listVocabularyCards).mockResolvedValue({
      cards: [
        {
          id: 11,
          deck_id: 5,
          deck_ids: [5],
          front: "break a leg",
          back: "mucha suerte",
          mnemonic: "",
          state: "new",
          reps: 0,
          due_at: "",
          created_at: "",
        },
      ],
    } as never);
    vi.mocked(updateVocabularyCard).mockResolvedValue({} as never);

    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Cards" }));
    await screen.findByText("break a leg");
    // Los mazos de la ficha se ven como etiquetas (el navegador ya no la
    // encasilla en uno solo).
    expect(screen.getAllByText("Idioms").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    const editor = screen.getByLabelText("Reminder").closest("form") as HTMLElement;
    fireEvent.change(within(editor).getByLabelText("Reminder"), {
      target: { value: "leg = pierna" },
    });
    // Se marca un SEGUNDO mazo: la ficha pasa a vivir en los dos.
    fireEvent.click(within(editor).getByLabelText("Travel"));
    fireEvent.click(within(editor).getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(updateVocabularyCard).toHaveBeenCalledWith("u1", 11, {
        front: "break a leg",
        back: "mucha suerte",
        mnemonic: "leg = pierna",
        deckIds: [5, 6],
      }),
    );
  });

  it("el borrado de un mazo avisa de las fichas compartidas (V3.86.0)", async () => {
    const SHARED: FlashcardDeck = {
      ...MANUAL,
      card_count: 4,
      shared_count: 3,
    };
    vi.mocked(listFlashcardDecks).mockResolvedValue({
      auto_deck_id: 0,
      decks: [AUTO, SHARED],
      fsrs_version: "test",
    });
    vi.mocked(deleteFlashcardDeck).mockResolvedValue({
      deleted_count: 1,
      shared_count: 3,
    });

    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Decks" }));
    expect(await screen.findByText("3 also in other decks")).toBeTruthy();

    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    // El aviso dice cuántas se borran y cuántas se conservan.
    expect(confirmSpy).toHaveBeenCalledWith(
      expect.stringContaining("3 will be kept"),
    );
    confirmSpy.mockRestore();
  });

  it("las estadísticas muestran repasos, acierto y previsión", async () => {
    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Stats" }));

    expect(await screen.findByText("Accuracy")).toBeTruthy();
    expect(screen.getByText("75%")).toBeTruthy();
    expect(screen.getByText("Reviewed today")).toBeTruthy();
    expect(screen.getByText("Last 14 days")).toBeTruthy();
    expect(screen.getByText("Next 7 days")).toBeTruthy();
  });

  it("el salto desde «Mis listas» abre Estudiar con la lista filtrada y arranca", async () => {
    // Lo que llega de PERSONAL: un encargo de un solo salto (collectionId +
    // nonce), no una preferencia.
    renderScreen({ focusCollectionId: 42, focusCollectionLabel: "Travel", focusNonce: 1 });

    await waitFor(() =>
      expect(getStudyQueue).toHaveBeenCalledWith("u1", {
        scope: "all",
        mode: "pending",
        level: null,
        deckId: 0,
        collectionId: 42,
      }),
    );
    // Arranca sola: el alumno ya pidió estudiar al pulsar «Estudiar».
    expect(await screen.findByText("airport")).toBeTruthy();
    expect(
      screen.getByRole("tab", { name: "Study" }).getAttribute("aria-selected"),
    ).toBe("true");
  });

  it("el salto con un mazo del diccionario abre ESE mazo (V3.84.0)", async () => {
    // El alta del diccionario puede guardar la palabra en un mazo manual: al
    // pulsar «Estudiar en Flashcards» se abre ese mazo, no el automático.
    // V3.86.0: la cola que se sirve es LA DEL MAZO (así arranca su sesión).
    renderScreen({ focusDeckId: 5, focusNonce: 1 });

    await waitFor(() =>
      expect(getStudyQueue).toHaveBeenCalledWith("u1", {
        scope: "deck",
        mode: "pending",
        level: null,
        deckId: 5,
        collectionId: null,
      }),
    );
    expect(await screen.findByText("airport")).toBeTruthy();
  });

  it("una cola del mazo anterior que llega tarde no se come el arranque del mazo pedido (V3.86.0)", async () => {
    // El foco pide el mazo 5, pero la carga del mazo automático (que aún estaba
    // seleccionado) seguía en vuelo. Cuando esa cola vieja resuelve, NO debe
    // gastar el encargo: el alumno terminaría en el panel aunque su mazo tenga
    // tarjetas, que es justo el fallo que destapó «una palabra ya rastreada».
    vi.mocked(getStudyQueue).mockImplementation(async (_userId, options) =>
      studyQueue({
        scope: options.scope,
        mode: options.mode ?? "pending",
        level: options.level ?? "",
        deck_id: options.deckId ?? 0,
        collection_id: options.collectionId ?? null,
      }),
    );
    renderScreen({ focusDeckId: 5, focusNonce: 1 });

    // La sesión arranca con la cola del mazo PEDIDO (y la nombra).
    expect(await screen.findByText("airport")).toBeTruthy();
    expect(screen.getAllByText("Idioms").length).toBeGreaterThan(0);
  });

  it("«Por nivel» pide la cola de ese nivel", async () => {
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "By level" }));

    await waitFor(() =>
      expect(getStudyQueue).toHaveBeenCalledWith("u1", {
        scope: "level",
        mode: "pending",
        level: "A1",
        deckId: 0,
        collectionId: null,
      }),
    );
  });

  it("sin perfil no pide nada y lo dice", async () => {
    renderScreen({ userId: null });

    expect(
      await screen.findByText(
        "Select a learning profile to see your personal dictionary.",
      ),
    ).toBeTruthy();
    expect(listFlashcardDecks).not.toHaveBeenCalled();
  });

  // --- V3.80.0: el mazo es UNA selección y crear uno lleva a escribir --------

  it("crear un mazo lo selecciona y abre Tarjetas con el anverso enfocado", async () => {
    // La queja literal era «creo uno nuevo pero luego no sé cómo añadir
    // palabras». El arreglo no es un texto de ayuda: es que el mazo creado sea
    // el seleccionado y que el cursor esté donde hay que escribir.
    const created: FlashcardDeck = {
      ...MANUAL,
      id: 9,
      name: "Phrasal verbs",
      card_count: 0,
    };
    vi.mocked(createFlashcardDeck).mockResolvedValue(created);
    vi.mocked(listFlashcardDecks).mockResolvedValue({
      auto_deck_id: 0,
      decks: [AUTO, MANUAL, created],
      fsrs_version: "test",
    });
    vi.mocked(listVocabularyCards).mockResolvedValue({ cards: [] } as never);

    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Decks" }));
    fireEvent.change(await screen.findByPlaceholderText("Deck name"), {
      target: { value: "Phrasal verbs" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(
      await screen.findByText(
        "Deck selected. Write the front and the back below; the card will be ready to study immediately.",
      ),
    ).toBeTruthy();
    await waitFor(() =>
      expect(listVocabularyCards).toHaveBeenCalledWith("u1", { deckId: 9 }),
    );
    expect(document.activeElement).toBe(
      screen.getByPlaceholderText("What you see first…"),
    );
  });

  it("«Añadir tarjetas» en la fila del mazo abre Tarjetas en ese mazo", async () => {
    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Decks" }));
    // El mazo automático no lo ofrece: sus tarjetas son el léxico.
    expect(screen.getAllByRole("button", { name: "Add cards" })).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Add cards" }));

    await waitFor(() =>
      expect(listVocabularyCards).toHaveBeenCalledWith("u1", { deckId: 5 }),
    );
    expect(
      screen.getByRole("tab", { name: "Cards" }).getAttribute("aria-selected"),
    ).toBe("true");
  });

  it("estudiar un mazo vacío no abre una sesión de 0: ofrece añadir tarjetas", async () => {
    vi.mocked(getStudyQueue).mockImplementation(async (_userId, options) =>
      studyQueue({
        scope: options.scope,
        deck_id: options.deckId ?? 0,
        collection_id: options.collectionId ?? null,
        items: options.scope === "deck" ? [] : studyQueue().items,
        total: options.scope === "deck" ? 0 : 12,
        queued: 0,
      }),
    );

    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Decks" }));
    const row = (await screen.findByText("Idioms")).closest("li")!;
    fireEvent.click(within(row).getByRole("button", { name: "Study" }));

    expect(
      await screen.findByText(
        "This deck has no cards yet. Add the first one and it can be studied right away.",
      ),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Study \(/ })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Add cards" }));
    await waitFor(() =>
      expect(listVocabularyCards).toHaveBeenCalledWith("u1", { deckId: 5 }),
    );
  });

  it("el mazo automático vacío manda al diccionario en vez de ofrecer botones inertes", async () => {
    vi.mocked(getStudyQueue).mockResolvedValue(
      studyQueue({ items: [], total: 0, queued: 0, studied: 0, learned: 0, due: 0 }),
    );

    renderScreen();
    expect(
      await screen.findByText(
        "This view of the bank is empty.",
      ),
    ).toBeTruthy();
    // No hay tarjetas manuales que añadir aquí: no se ofrece el atajo.
    expect(screen.queryByRole("button", { name: "Add cards" })).toBeNull();
  });

  it("el mazo elegido en Tarjetas es el que estudia Estudiar (una sola selección)", async () => {    // Antes cada pestaña tenía su propio `deckId` y Tarjetas arrancaba en
    // `manual[0]`: elegir un mazo en Tarjetas no cambiaba lo que se estudiaba.
    const SECOND = { ...MANUAL, id: 6, name: "Travel", card_count: 0 };
    vi.mocked(listFlashcardDecks).mockResolvedValue({
      auto_deck_id: 0,
      decks: [AUTO, MANUAL, SECOND],
      fsrs_version: "test",
    });
    vi.mocked(listVocabularyCards).mockResolvedValue({ cards: [] } as never);
    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Cards" }));
    fireEvent.change(await screen.findByLabelText("Filter by deck"), {
      target: { value: "6" },
    });
    await waitFor(() =>
      expect(listVocabularyCards).toHaveBeenCalledWith("u1", { deckId: 6 }),
    );

    fireEvent.click(screen.getByRole("tab", { name: "Study" }));
    fireEvent.click(await screen.findByRole("button", { name: "By deck" }));
    await waitFor(() =>
      expect(getStudyQueue).toHaveBeenCalledWith("u1", {
        scope: "deck",
        mode: "pending",
        level: null,
        deckId: 6,
        collectionId: null,
      }),
    );
  });

  // --- V3.80.0: pegar una lista de tarjetas --------------------------------

  it("pegar una lista crea las tarjetas y declara cuántas entraron de verdad", async () => {
    vi.mocked(addFlashcardsBulk).mockResolvedValue({
      deck_id: 5,
      added: ["break a leg", "take off"],
      count: 2,
    });

    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Cards" }));
    await screen.findByText("break a leg");

    fireEvent.change(
      screen.getByPlaceholderText(/break a leg/),
      { target: { value: "break a leg,mucha suerte\ntake off,despegar" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Add all" }));

    await waitFor(() =>
      expect(addFlashcardsBulk).toHaveBeenCalledWith(
        "u1",
        5,
        "break a leg,mucha suerte\ntake off,despegar",
      ),
    );
    // El recuento es el del servidor, no el de las líneas pegadas: con
    // duplicados o líneas inválidas no coinciden, y prometer el segundo sería
    // mentir.
    expect(await screen.findByText("2 cards added.")).toBeTruthy();
  });

  it("si el pegado falla lo dice y no declara un recuento falso", async () => {
    vi.mocked(addFlashcardsBulk).mockRejectedValue(new Error("500"));

    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Cards" }));
    await screen.findByText("break a leg");

    fireEvent.change(
      screen.getByPlaceholderText(/break a leg/),
      { target: { value: "one,uno" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Add all" }));

    expect(await screen.findByText("Could not save the card.")).toBeTruthy();
    expect(screen.queryByText(/cards added/)).toBeNull();
  });

  // --- V3.80.0: mazos listos ----------------------------------------------

  it("un mazo listo sin activar se añade y ya activo se estudia filtrado", async () => {
    const PACK = {
      id: 3,
      kind: "theme_pack",
      slug: "travel",
      title: "Travel",
      title_es: "Viajes",
      cefr_hint: "A2",
      item_count: 12,
      enrolled: false,
      is_global: true,
    };
    // El catálogo se lee en vivo para que la recarga posterior al alta vea el
    // pack ya activo, como lo vería contra el servidor de verdad.
    let enrolled = false;
    vi.mocked(listVocabCollections).mockImplementation(async () => ({
      collections: [{ ...PACK, enrolled }],
    }));
    vi.mocked(enrollVocabCollection).mockResolvedValue({
      collection_id: 3,
      added: ["airport"],
      count: 12,
    });

    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Decks" }));

    expect(await screen.findByText("Ready-made decks")).toBeTruthy();
    const row = screen.getByText("Travel").closest("li") as HTMLElement;
    // Añadir un pack es «añadir a mi diccionario»: se dice qué son y qué pasará.
    expect(within(row).getByText("12 words · A2")).toBeTruthy();
    expect(within(row).queryByText("In your dictionary")).toBeNull();

    enrolled = true;
    fireEvent.click(within(row).getByRole("button", { name: "Add" }));

    await waitFor(() => expect(enrollVocabCollection).toHaveBeenCalledWith("u1", 3));
    // El recuento es el que devolvió el servidor.
    expect(await screen.findByText(/12 added/)).toBeTruthy();

    // Tras activarlo, la acción útil deja de ser «Añadir» (sería idempotente y
    // añadiría 0): pasa a ser estudiar el mazo automático filtrado por el pack.
    const enrolledRow = await waitFor(() => {
      const item = screen.getByText("Travel").closest("li") as HTMLElement;
      expect(within(item).getByText("In your dictionary")).toBeTruthy();
      return item;
    });
    expect(within(enrolledRow).queryByRole("button", { name: "Add" })).toBeNull();
    fireEvent.click(within(enrolledRow).getByRole("button", { name: "Study" }));

    // Se estudia en el mazo automático (es el MISMO vocabulario, no una copia),
    // con el `collection_id` que la cola ya soporta.
    await waitFor(() =>
      expect(getStudyQueue).toHaveBeenCalledWith("u1", {
        scope: "all",
        mode: "pending",
        level: null,
        deckId: 0,
        collectionId: 3,
      }),
    );
  });

  // --- V3.87.0: configuración de estudio ------------------------------------

  it("el panel de estudio arranca plegado y se despliega con el «...»", async () => {
    renderScreen();

    // V3.87.1: las cuatro decisiones no ocupan sitio hasta que se piden; el
    // disparador conserva el nombre accesible y declara su estado.
    const trigger = await screen.findByRole("button", {
      name: "Study settings",
    });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByLabelText("Mode")).toBeNull();

    fireEvent.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(await screen.findByLabelText("Mode")).toBeTruthy();
    expect(screen.getByLabelText("Words today")).toBeTruthy();
    expect(screen.getByText("Meaning always counts.")).toBeTruthy();

    // Y se vuelve a plegar.
    fireEvent.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByLabelText("Mode")).toBeNull();
  });

  it("el panel de estudio guarda el modo y recarga la cola", async () => {
    renderScreen();
    fireEvent.click(
      await screen.findByRole("button", { name: "Study settings" }),
    );
    const mode = (await screen.findByLabelText("Mode")) as HTMLSelectElement;
    fireEvent.change(mode, { target: { value: "production" } });

    await waitFor(() =>
      expect(saveStudyConfig).toHaveBeenCalledWith("u1", { mode: "production" }),
    );
    // Guardar reconstruye la cola con la preferencia nueva; la sesión en curso no
    // se reescribe por detrás.
    await waitFor(() => expect(getStudyQueue).toHaveBeenCalledTimes(2));
  });
});
