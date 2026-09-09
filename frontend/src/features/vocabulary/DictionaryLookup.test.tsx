// @vitest-environment jsdom
/**
 * Vitest de `DictionaryLookup` (V3.30). Corre en jsdom y mockea `fetch` por URL:
 *
 * - estados de la vista: vacío, carga, error de red con retry y degradación de
 *   contenido (modelo caído → `definition_source="none"`) con la marca de uso
 *   servida igualmente;
 * - validación local de la palabra (sin petición para entradas inválidas);
 * - render de la tarjeta de resultado (definición/traducción, ejemplo del banco
 *   y botones de audio) y de la marca de uso (forma exacta y agregado por
 *   unidad canónica).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { I18nProvider } from "../../hooks/useI18n";
import { DictionaryLookup } from "./DictionaryLookup";

// V3.32: la escalera de drill montada desde el lookup usa el micrófono y
// `MediaRecorder`; se mockean igual que en `PersonalDictionary.test.tsx`.
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

const COFFEE = {
  word: "coffee",
  kind: "word",
  cefr: "A1",
  definition_source: "llm",
  pos: "noun",
  definition: "A hot drink made from roasted coffee beans.",
  translation: "café",
  example: {
    phrase: "I drink coffee every morning.",
    source: "pronunciation_corpus",
    level: "A1",
  },
  usage: {
    tracked: true,
    surface: {
      status: "known",
      mastery: 0.6,
      recall: 0.8,
      next_review_days: 3,
      production_count: 1,
      exposure_count: 4,
      production_channels: ["chat"],
      competence: {
        recognition: true,
        production: true,
        production_channels: ["chat"],
        transfer_contexts: 2,
        transfer: true,
        retention: false,
        spaced_exposure: true,
        spaced_production: true,
        retrieval_successes: 1,
        retrieval_days: 1,
        production_gap: false,
        transfer_gap: false,
      },
      last_activity_at: "2026-09-01T10:00:00Z",
    },
    unit: null,
  },
};

const NEBULA = {
  word: "nebula",
  kind: "word",
  cefr: "",
  definition_source: "none",
  pos: "",
  definition: null,
  translation: null,
  example: null,
  usage: { tracked: false, surface: null, unit: null },
};

const GO_UNIT = {
  word: "go",
  kind: "word",
  cefr: "A1",
  definition_source: "llm",
  pos: "verb",
  definition: "to move or travel somewhere",
  translation: "ir",
  example: null,
  usage: {
    tracked: true,
    surface: null,
    unit: {
      lexical_unit: "go",
      status: "learning",
      mastery: 0.3,
      recall: 0.4,
      surface_count: 2,
      mastered_surfaces: 0,
      recognized: true,
      produced: true,
      transfer: false,
      production_count: 1,
      exposure_count: 5,
    },
  },
};

/** Mock de fetch por URL; los datos pueden ser un valor o una función evaluada
 * en el momento de la llamada (para mutar estado entre llamadas). */
function routeFetch(routes: Array<{ url: string; data: unknown }>) {
  const fn = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    const hit = routes.find((r) => url.includes(r.url));
    if (!hit) return Promise.reject(new Error(`unexpected fetch: ${url}`));
    const data = typeof hit.data === "function" ? hit.data() : hit.data;
    return Promise.resolve({ ok: true, json: async () => data });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

function renderPanel(ui: ReactElement) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      {ui}
    </I18nProvider>,
  );
}

function fillAndSubmit(word: string) {
  fireEvent.change(screen.getByLabelText("Search the dictionary"), {
    target: { value: word },
  });
  fireEvent.click(screen.getByRole("button", { name: "Look up" }));
}

function stubMediaRecorder() {
  class FakeRecorder {
    mimeType = "audio/webm";
    ondataavailable: ((e: { data: Blob }) => void) | null = null;
    onstop: (() => void) | null = null;
    start() {
      this.ondataavailable?.({ data: new Blob(["audio"], { type: "audio/webm" }) });
    }
    stop() {
      this.onstop?.();
    }
  }
  vi.stubGlobal("MediaRecorder", FakeRecorder);
}

/** Respuesta determinista de `POST /api/vocabulary/drill/attempt` (V3.32). */
const DRILL_OK = {
  word: "coffee",
  produced: true,
  expected: "coffee",
  heard: "coffee",
  score: 100,
  level: "good",
  ok: true,
  word_accuracy: 100,
  phonetic_score: 100,
  phoneme_accuracy_proxy: 100,
  prosody_proxy: 100,
  pronunciation_source: "transcript",
  breakdown: { correct: ["coffee"], missing: [], extra: [], substituted: [], total: 1 },
  phoneme_breakdown: {
    correct: ["c"],
    missing: [],
    extra: [],
    substituted: [],
    total: 1,
  },
  fluency: null,
  asr_status: "ok",
};

describe("DictionaryLookup (V3.30)", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("estado vacío: no hace ninguna petición hasta buscar", () => {
    const fn = routeFetch([{ url: "/api/vocabulary/dictionary", data: COFFEE }]);
    renderPanel(<DictionaryLookup userId="u1" />);

    expect(screen.getByText("Dictionary lookup")).toBeTruthy();
    expect(
      screen.getByPlaceholderText(/Type a word/),
    ).toBeTruthy();
    expect(fn).not.toHaveBeenCalled();
  });

  it("muestra definición, traducción, ejemplo y marca de uso de una palabra conocida", async () => {
    routeFetch([{ url: "/api/vocabulary/dictionary", data: COFFEE }]);
    renderPanel(<DictionaryLookup userId="u1" />);

    fillAndSubmit("coffee");

    // Contenido del diccionario (Fase B).
    expect(
      await screen.findByText("A hot drink made from roasted coffee beans."),
    ).toBeTruthy();
    expect(screen.getByText("café")).toBeTruthy();
    expect(screen.getByText("Definition")).toBeTruthy();
    // Frase de ejemplo determinista con su botón de audio + audio de la palabra.
    expect(screen.getByText("I drink coffee every morning.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Hear the word" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Listen to the example" })).toBeTruthy();
    // Badge POS + CEFR.
    expect(screen.getByText("Noun")).toBeTruthy();

    // Marca de uso (solo lectura).
    expect(screen.getByText("Known")).toBeTruthy();
    expect(screen.getByText("Produced 1×")).toBeTruthy();
    expect(screen.getByText("Seen 4×")).toBeTruthy();
    expect(screen.getByText("Retention")).toBeTruthy();
  });

  it("palabra no registrada: degrade a definition_source=none y marca «Not met yet»", async () => {
    routeFetch([{ url: "/api/vocabulary/dictionary", data: NEBULA }]);
    renderPanel(<DictionaryLookup userId="u1" />);

    fillAndSubmit("nebula");

    expect(
      await screen.findByText(/The dictionary content isn't available right now/),
    ).toBeTruthy();
    expect(screen.queryByText("Definition")).toBeNull();
    expect(screen.getByText("Not met yet")).toBeTruthy();
    expect(
      screen.getByText(/You haven't met this word in the app yet/),
    ).toBeTruthy();
  });

  it("buscar la unidad canónica muestra el agregado por formas (sin forma exacta)", async () => {
    routeFetch([{ url: "/api/vocabulary/dictionary", data: GO_UNIT }]);
    renderPanel(<DictionaryLookup userId="u1" />);

    fillAndSubmit("go");

    expect(await screen.findByText(/forms of the unit/)).toBeTruthy();
    expect(screen.getByText("2 form(s) in this unit")).toBeTruthy();
    expect(screen.getByText("Produced 1×")).toBeTruthy();
  });

  it("palabra inválida: error determinista sin petición al backend", async () => {
    const fn = routeFetch([{ url: "/api/vocabulary/dictionary", data: COFFEE }]);
    renderPanel(<DictionaryLookup userId="u1" />);

    fillAndSubmit("???");

    expect(
      await screen.findByText(/That doesn't look like a valid word or phrase/),
    ).toBeTruthy();
    expect(fn).not.toHaveBeenCalled();
  });

  it("error de red muestra retry y reintenta la misma consulta", async () => {
    let down = true;
    const fn = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (!url.includes("/api/vocabulary/dictionary")) {
        return Promise.reject(new Error(`unexpected fetch: ${url}`));
      }
      if (down) {
        down = false;
        return Promise.reject(new Error("backend down"));
      }
      return Promise.resolve({ ok: true, json: async () => COFFEE });
    });
    vi.stubGlobal("fetch", fn);
    renderPanel(<DictionaryLookup userId="u1" />);

    fillAndSubmit("coffee");

    expect(
      await screen.findByText(/Could not look up the word/),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByText("A hot drink made from roasted coffee beans."),
    ).toBeTruthy();
    await waitFor(() =>
      expect(screen.queryByText(/Could not look up the word/)).toBeNull(),
    );
    // El reintento reutiliza la última consulta (sin volver a teclear).
    const calls = fn.mock.calls.map((c) => String(c[0]));
    expect(calls.filter((c) => c.includes("/dictionary")).length).toBe(2);
  });
});

describe("DictionaryLookup · V3.32 Dictionary → Learning Bridge", () => {
  beforeEach(() => stubMediaRecorder());
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("muestra la acción «Practice this word» y al pulsarla monta la escalera de drill", async () => {
    routeFetch([{ url: "/api/vocabulary/dictionary", data: COFFEE }]);
    renderPanel(<DictionaryLookup userId="u1" />);

    fillAndSubmit("coffee");
    // El CTA de práctica vive junto al audio de la palabra en la tarjeta.
    const practiceCta = await screen.findByRole("button", {
      name: "Practice this word",
    });
    expect(practiceCta).toBeTruthy();

    fireEvent.click(practiceCta);
    // Se monta la escalera de drill oral (Recal → Sentence): mismo prompt que
    // en el diccionario personal.
    expect(await screen.findByText(/Listen to the word/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "1 · Word" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "2 · Sentence" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Record" })).toBeTruthy();

    // Cerrar la escalera la desmonta.
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Record" })).toBeNull(),
    );
  });

  it("producir la palabra tras «Practicar» refresca la entrada en silencio (sin desmontar el drill)", async () => {
    // V3.32: la evidencia del drill es real; tras producir, la marca de uso de
    // la tarjeta se refresca con un re-lookup silencioso (mismo endpoint).
    const dictionaryHits = { count: 0 };
    const fn = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/vocabulary/dictionary")) {
        dictionaryHits.count += 1;
        return Promise.resolve({ ok: true, json: async () => COFFEE });
      }
      if (url.includes("/api/vocabulary/drill/attempt")) {
        return Promise.resolve({ ok: true, json: async () => DRILL_OK });
      }
      return Promise.reject(new Error(`unexpected fetch: ${url}`));
    });
    vi.stubGlobal("fetch", fn);
    renderPanel(<DictionaryLookup userId="u1" />);

    fillAndSubmit("coffee");
    const cta = await screen.findByRole("button", { name: "Practice this word" });
    fireEvent.click(cta);

    fireEvent.click(await screen.findByRole("button", { name: "Record" }));
    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));

    // Resultado del drill: producción correcta.
    expect(await screen.findByText(/another day to consolidate it/)).toBeTruthy();
    // El drill sigue montado (el re-lookup no lo desmonta).
    expect(screen.getByRole("button", { name: "Record" })).toBeTruthy();
    // Se produjo un re-lookup silencioso del diccionario para refrescar la marca.
    await waitFor(() => expect(dictionaryHits.count).toBe(2));
  });

  it("la escalera ofrece el paso Sentence y lo supera (F6.1) sin abandonar el lookup", async () => {
    routeFetch([
      { url: "/api/vocabulary/dictionary", data: COFFEE },
      {
        url: "/api/vocabulary/drill/sentence-context",
        data: {
          word: "coffee",
          phrase: 'Say the word "coffee".',
          source: "template",
          level: "A1",
        },
      },
      {
        url: "/api/vocabulary/drill/sentence-attempt",
        data: {
          word: "coffee",
          phrase: 'Say the word "coffee".',
          source: "template",
          produced: true,
          phrase_ok: true,
          passed: true,
          heard: 'say the word "coffee"',
          score: 100,
          level: "good",
          fluency: null,
          asr_status: "ok",
        },
      },
    ]);
    renderPanel(<DictionaryLookup userId="u1" />);

    fillAndSubmit("coffee");
    fireEvent.click(
      await screen.findByRole("button", { name: "Practice this word" }),
    );

    fireEvent.click(screen.getByRole("button", { name: "2 · Sentence" }));
    expect(await screen.findByText('Say the word "coffee".')).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Record" }));
    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));

    expect(await screen.findByText(/inside the sentence/)).toBeTruthy();
    // La tarjeta de resultado sigue visible (el drill convive con ella).
    expect(screen.getByText("A hot drink made from roasted coffee beans.")).toBeTruthy();
  });
});
