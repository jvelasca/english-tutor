// @vitest-environment jsdom
/**
 * Vitest de `DictionaryScreen` · contrato de LAYOUT (V3.77.2).
 *
 * `DictionaryScreen` es el dueño del layout de la página: pinta el `h1`, el
 * subtítulo y el contenedor `max-w-3xl/px-4/py-6`, y las vistas incrustadas
 * (`DictionaryLookup`, y desde V3.77.2 también `PersonalDictionary`) no deben
 * repetirlos.
 *
 * A diferencia de `DictionaryScreen.test.tsx`, que mockea las vistas para
 * probar la persistencia de la pestaña, aquí se montan las vistas REALES: el
 * defecto (dos `h1` y ancho aplicado dos veces) solo existe cuando las dos
 * capas se componen de verdad. Por eso este es un test de integración de
 * frontera, con `fetch` mockeado.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { I18nProvider } from "../../hooks/useI18n";
import { DICTIONARY_VIEW_STORAGE_KEY } from "../../utils/dictionaryView";
import { DictionaryScreen } from "./DictionaryScreen";
import type { Lexicon } from "../../types/api";

vi.mock("../../utils/browserCapabilities", async (importOriginal) => {
  const original =
    await importOriginal<typeof import("../../utils/browserCapabilities")>();
  return {
    ...original,
    getMicrophoneStream: vi.fn().mockResolvedValue({
      getTracks: () => [{ stop: vi.fn() }],
    }),
  };
});

const LEXICON: Lexicon = {
  summary: {
    total: 1,
    known: 1,
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
  items: [
    {
      word: "travel",
      lemma: "travel",
      cefr: "A1",
      kind: "word",
      source: "curriculum",
      status: "known",
      recall: 0.5,
      next_review_days: 3,
      production_count: 0,
      exposure_count: 3,
      chat_prod: 0,
      speaking_prod: 0,
      writing_prod: 0,
      conversation_prod: 0,
    },
  ],
  coverage: null,
};

function routeFetch() {
  const routes: Array<{ url: string; data: unknown }> = [
    { url: "/api/settings", data: { settings: {} } },
    { url: "/api/vocabulary/lexicon", data: LEXICON },
    { url: "/api/vocabulary/drill/candidates", data: { words: [] } },
    {
      url: "/api/vocabulary/decks",
      data: {
        auto_deck_id: 0,
        decks: [
          {
            id: 0,
            name: "auto",
            is_auto: true,
            new_per_day: 10,
            review_per_day: 50,
            card_count: 0,
            due_count: 0,
            new_count: 0,
          },
        ],
      },
    },
    { url: "/api/vocabulary/collections", data: { collections: [] } },
    { url: "/api/learning/review", data: { items: [], units: [] } },
  ];
  const fn = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    const hit = routes.find((r) => url.includes(r.url));
    if (!hit) return Promise.reject(new Error(`unexpected fetch: ${url}`));
    return Promise.resolve({ ok: true, json: async () => hit.data });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("DictionaryScreen · un solo h1 con las vistas reales (V3.77.2)", () => {
  beforeEach(() => {
    window.localStorage.clear();
    routeFetch();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("la vista Personal incrustada no duplica la cabecera de la página", async () => {
    // V3.78.0: el defecto es `lookup`, así que la vista Personal se pide
    // explícitamente para seguir midiendo lo mismo que se medía en V3.77.2.
    window.localStorage.setItem(DICTIONARY_VIEW_STORAGE_KEY, "personal");

    render(
      <I18nProvider lang="en" setLang={() => {}}>
        <DictionaryScreen userId="u1" />
      </I18nProvider>,
    );

    // Espera a que el léxico (vista real) termine de cargar.
    await waitFor(() =>
      expect(document.body.textContent).toContain("My lexicon"),
    );

    const headings = Array.from(document.querySelectorAll("h1"));
    expect(headings).toHaveLength(1);
    expect(headings[0].textContent).toBe("Dictionary");
    // El título de la vista incrustada ya no aparece como cabecera propia.
    expect(document.querySelectorAll("h1")).toHaveLength(1);
  });

  it("la vista Consultar tampoco añade un segundo h1", async () => {
    window.localStorage.setItem(DICTIONARY_VIEW_STORAGE_KEY, "lookup");

    render(
      <I18nProvider lang="en" setLang={() => {}}>
        <DictionaryScreen userId="u1" />
      </I18nProvider>,
    );

    await waitFor(() =>
      expect(screen.getByLabelText("Search the dictionary")).toBeTruthy(),
    );

    expect(document.querySelectorAll("h1")).toHaveLength(1);
  });
});
