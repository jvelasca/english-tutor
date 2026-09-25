// @vitest-environment jsdom
/**
 * Vitest de `FlashcardsScreen` (V3.78.0): la ÚNICA superficie de estudio.
 *
 * Se mockea la frontera de API entera (los clientes ya normalizan, y ese
 * contrato tiene sus propias pruebas). Lo que se fija aquí es el
 * comportamiento de la pantalla:
 *
 * 1. Las cuatro subpestañas existen y Estudiar es la de entrada.
 * 2. Estudiar califica por el endpoint del MAZO con `card_type`/`card_id`, y el
 *    resumen final queda alcanzable.
 * 3. El mazo automático no se puede borrar ni editar (no es una fila).
 * 4. El navegador filtra por texto y estado, y el CRUD llama a lo que dice.
 * 5. El salto desde PERSONAL («Mis listas»/packs) abre Estudiar con la lista
 *    filtrada y arranca la sesión.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { I18nProvider } from "../../hooks/useI18n";
import type { FlashcardDeck, FlashcardQueue } from "../../types/api";
import { FlashcardsScreen } from "./FlashcardsScreen";

vi.mock("../../api/vocabulary", () => ({
  listFlashcardDecks: vi.fn(),
  createFlashcardDeck: vi.fn(),
  updateFlashcardDeck: vi.fn(),
  deleteFlashcardDeck: vi.fn(),
  getFlashcardQueue: vi.fn(),
  reviewFlashcard: vi.fn(),
  listFlashcardCards: vi.fn(),
  createFlashcard: vi.fn(),
  addFlashcardsBulk: vi.fn(),
  updateFlashcard: vi.fn(),
  deleteFlashcard: vi.fn(),
  getFlashcardStats: vi.fn(),
  listVocabCollections: vi.fn(),
  enrollVocabCollection: vi.fn(),
}));

vi.mock("../../components/ItemReplayButton", () => ({
  ItemReplayButton: () => <button type="button">audio</button>,
}));

import {
  createFlashcard,
  createFlashcardDeck,
  addFlashcardsBulk,
  deleteFlashcard,
  deleteFlashcardDeck,
  enrollVocabCollection,
  getFlashcardQueue,
  getFlashcardStats,
  listFlashcardCards,
  listFlashcardDecks,
  listVocabCollections,
  reviewFlashcard,
} from "../../api/vocabulary";

const AUTO: FlashcardDeck = {
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

const MANUAL: FlashcardDeck = {
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

function queue(overrides: Partial<FlashcardQueue> = {}): FlashcardQueue {
  return {
    deck: AUTO,
    items: [
      {
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
      },
    ],
    due_count: 2,
    new_count: 3,
    reviewed_today: 0,
    new_today: 0,
    limits: { new_per_day: 10, review_per_day: 50, new_remaining: 7, review_remaining: 48 },
    fsrs_version: "test",
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
    vi.mocked(getFlashcardQueue).mockResolvedValue(queue());
    vi.mocked(reviewFlashcard).mockResolvedValue({
      card_id: "airport",
      card_type: "lexicon",
      grade: 3,
      due_at: "",
      next_in_days: 2,
      stability: 1,
      retrievability: 1,
      reps: 1,
    } as never);
    vi.mocked(listFlashcardCards).mockResolvedValue({
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
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("ofrece las cuatro subpestañas y entra por Estudiar", async () => {
    renderScreen();

    expect(await screen.findByRole("tab", { name: "Study" })).toBeTruthy();
    for (const name of ["Study", "Decks", "Cards", "Stats"]) {
      expect(screen.getByRole("tab", { name })).toBeTruthy();
    }
    expect(
      screen.getByRole("tab", { name: "Study" }).getAttribute("aria-selected"),
    ).toBe("true");
    // La cola se pide para el mazo automático, que es donde cae el defecto.
    await waitFor(() =>
      expect(getFlashcardQueue).toHaveBeenCalledWith("u1", 0, {
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
    expect(tabs).toHaveLength(4);

    const study = screen.getByRole("tab", { name: "Study" });
    study.focus();
    fireEvent.keyDown(study, { key: "ArrowRight" });

    expect(await screen.findByPlaceholderText("Deck name")).toBeTruthy();
    const decks = screen.getByRole("tab", { name: "Decks" });
    expect(decks.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(decks);
  });

  it("estudiar califica por el endpoint del mazo y el resumen es alcanzable", async () => {
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: /Start session/ }));

    expect(screen.getByText("airport")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Flip card" }));
    fireEvent.click(screen.getByText("Good"));

    await waitFor(() =>
      expect(reviewFlashcard).toHaveBeenCalledWith("u1", 0, {
        card_type: "lexicon",
        card_id: "airport",
        grade: 3,
      }),
    );
    // El resumen final sigue siendo alcanzable (candado de V3.77.2 trasladado).
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
      expect(deleteFlashcard).toHaveBeenCalledWith("u1", 5, 11),
    );
  });

  it("añadir una tarjeta exige anverso y lo envía con el dorso", async () => {
    vi.mocked(createFlashcard).mockResolvedValue({} as never);
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
      expect(createFlashcard).toHaveBeenCalledWith("u1", 5, {
        front: "on the fly",
        back: "sobre la marcha",
      }),
    );
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
    vi.mocked(getFlashcardQueue).mockResolvedValue(queue());
    renderScreen({ focusCollectionId: 42, focusCollectionLabel: "Travel", focusNonce: 1 });

    await waitFor(() =>
      expect(getFlashcardQueue).toHaveBeenCalledWith("u1", 0, {
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
    renderScreen({ focusDeckId: 5, focusNonce: 1 });

    await waitFor(() =>
      expect(getFlashcardQueue).toHaveBeenCalledWith("u1", 5, {
        collectionId: null,
      }),
    );
    expect(await screen.findByText("airport")).toBeTruthy();
  });

  it("la ruta genérica se acota a un pack o lista con el filtro (V3.84.0)", async () => {
    vi.mocked(listVocabCollections).mockResolvedValue({
      collections: [
        {
          id: 3,
          kind: "theme_pack",
          slug: "food",
          title: "Food & Drink",
          title_es: "Comida",
          cefr_hint: "A1",
          item_count: 25,
          enrolled: false,
          is_global: true,
        },
      ],
    } as never);
    renderScreen();

    // El filtro solo existe sobre el mazo automático (el de entrada): acota la
    // ruta genérica a las palabras de un pack o de una lista.
    const filter = await screen.findByLabelText("Study what");
    fireEvent.change(filter, { target: { value: "3" } });

    await waitFor(() =>
      expect(getFlashcardQueue).toHaveBeenCalledWith("u1", 0, {
        collectionId: 3,
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
    vi.mocked(listFlashcardCards).mockResolvedValue({ deck_id: 9, cards: [] } as never);

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
    await waitFor(() => expect(listFlashcardCards).toHaveBeenCalledWith("u1", 9));
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
      expect(listFlashcardCards).toHaveBeenCalledWith("u1", 5),
    );
    expect(
      screen.getByRole("tab", { name: "Cards" }).getAttribute("aria-selected"),
    ).toBe("true");
  });

  it("estudiar un mazo vacío no abre una sesión de 0: ofrece añadir tarjetas", async () => {
    vi.mocked(getFlashcardQueue).mockResolvedValue(
      queue({ deck: { ...MANUAL, card_count: 0 }, items: [] }),
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
    expect(screen.queryByRole("button", { name: /Start session/ })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Add cards" }));
    await waitFor(() => expect(listFlashcardCards).toHaveBeenCalledWith("u1", 5));
  });

  it("el mazo automático vacío manda al diccionario en vez de ofrecer botones inertes", async () => {
    vi.mocked(getFlashcardQueue).mockResolvedValue(
      queue({
        deck: { ...AUTO, card_count: 0, due_count: 0, new_count: 0 },
        items: [],
      }),
    );

    renderScreen();
    expect(
      await screen.findByText(
        "Your dictionary has no words yet. Add them in Personal and they will show up here.",
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
    vi.mocked(listFlashcardCards).mockResolvedValue({ deck_id: 6, cards: [] } as never);
    vi.mocked(getFlashcardQueue).mockResolvedValue(
      queue({ deck: { ...SECOND, card_count: 0 }, items: [] }),
    );

    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Cards" }));
    fireEvent.change(await screen.findByLabelText("Deck"), {
      target: { value: "6" },
    });
    await waitFor(() => expect(listFlashcardCards).toHaveBeenCalledWith("u1", 6));

    fireEvent.click(screen.getByRole("tab", { name: "Study" }));
    await waitFor(() =>
      expect(getFlashcardQueue).toHaveBeenCalledWith("u1", 6, {
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
      expect(getFlashcardQueue).toHaveBeenCalledWith("u1", 0, {
        collectionId: 3,
      }),
    );
  });
});
