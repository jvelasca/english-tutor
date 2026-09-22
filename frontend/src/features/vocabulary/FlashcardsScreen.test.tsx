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
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  updateFlashcard: vi.fn(),
  deleteFlashcard: vi.fn(),
  getFlashcardStats: vi.fn(),
}));

vi.mock("../../components/ItemReplayButton", () => ({
  ItemReplayButton: () => <button type="button">audio</button>,
}));

import {
  createFlashcard,
  createFlashcardDeck,
  deleteFlashcard,
  deleteFlashcardDeck,
  getFlashcardQueue,
  getFlashcardStats,
  listFlashcardCards,
  listFlashcardDecks,
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
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("ofrece las cuatro subpestañas y entra por Estudiar", async () => {
    renderScreen();

    expect(
      await screen.findByRole("button", { name: "Study" }),
    ).toBeTruthy();
    for (const name of ["Study", "Decks", "Cards", "Stats"]) {
      expect(screen.getByRole("button", { name })).toBeTruthy();
    }
    expect(screen.getByRole("button", { name: "Study" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
    // La cola se pide para el mazo automático, que es donde cae el defecto.
    await waitFor(() =>
      expect(getFlashcardQueue).toHaveBeenCalledWith("u1", 0, {
        collectionId: null,
      }),
    );
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
    fireEvent.click(await screen.findByRole("button", { name: "Decks" }));

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
    fireEvent.click(await screen.findByRole("button", { name: "Decks" }));

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
    fireEvent.click(await screen.findByRole("button", { name: "Cards" }));

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
    fireEvent.click(await screen.findByRole("button", { name: "Cards" }));
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
    fireEvent.click(await screen.findByRole("button", { name: "Stats" }));

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
    expect(screen.getByRole("button", { name: "Study" }).getAttribute("aria-pressed")).toBe(
      "true",
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
});
