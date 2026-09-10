// @vitest-environment jsdom
/**
 * Vitest de `PersonalDictionary` (V3.19). Corre en jsdom, mockea `fetch` por URL,
 * el micrófono y `MediaRecorder` para simular el flujo del speaking micro-drill:
 *
 * - la sección de candidatas se nutre de la señal del servidor (no de un
 *   recálculo cliente) y pinta un chip por palabra con su acción de micrófono.
 * - error de carga → mensaje de error con reintento (A6-03).
 * - abrir el drill de una palabra, grabarla y producirla → la palabra sale de
 *   la lista y el léxico se refresca.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { I18nProvider } from "../../hooks/useI18n";
import { PersonalDictionary } from "./PersonalDictionary";
import type { Lexicon } from "../../types/api";

// Micrófono disponible en el test: `getMicrophoneStream` devuelve un stream
// fake y `MediaRecorder` es un stub que emite un chunk y llama `onstop`.
vi.mock("../../utils/browserCapabilities", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../utils/browserCapabilities")>();
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
    // V3.21 (V20-16) / V3.22 / V3.23: contadores de la matriz de competencia.
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

/** Mock de fetch por URL; `data` puede ser un valor o una función evaluada en
 * el momento de la llamada (para mutar estado entre llamadas). */
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

function renderPanel(ui: ReactElement) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      {ui}
    </I18nProvider>,
  );
}

const DRILL_OK = {
  word: "travel",
  produced: true,
  expected: "travel",
  heard: "travel",
  score: 100,
  level: "good",
  ok: true,
  word_accuracy: 100,
  phonetic_score: 100,
  phoneme_accuracy_proxy: 100,
  prosody_proxy: 100,
  pronunciation_source: "transcript",
  breakdown: { correct: ["travel"], missing: [], extra: [], substituted: [], total: 1 },
  phoneme_breakdown: { correct: ["t"], missing: [], extra: [], substituted: [], total: 1 },
  fluency: null,
};

describe("PersonalDictionary (V3.19 drill)", () => {
  beforeEach(() => stubMediaRecorder());
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("pinta las candidatas del servidor como chips con acción de micrófono", async () => {
    routeFetch([
      { url: "/api/vocabulary/lexicon", data: LEXICON },
      { url: "/api/vocabulary/drill/candidates", data: { words: ["travel"] } },
    ]);
    renderPanel(<PersonalDictionary userId="u1" />);

    expect(await screen.findByRole("button", { name: "Say travel" })).toBeTruthy();
  });

  it("muestra error de carga con reintento (A6-03)", async () => {
    // Primer arranque: la carga del léxico falla (down=true). Tras el reintento
    // el backend responde y el diccionario se pinta.
    let down = true;
    const fn = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (down) {
        down = false;
        return Promise.reject(new Error("down"));
      }
      if (url.includes("/api/vocabulary/lexicon")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ summary: { total: 0, by_cefr: [] }, items: [] }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({ words: [] }) });
    });
    vi.stubGlobal("fetch", fn);

    renderPanel(<PersonalDictionary userId="u1" />);
    expect(await screen.findByText(/Could not load your dictionary/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() =>
      expect(screen.queryByText(/Could not load your dictionary/)).toBeNull(),
    );
  });

  it("al producir una palabra en el drill sale de la lista de candidatas", async () => {
    // Estado mutable: tras el POST (produced), ya no es candidata.
    const candidates: { words: string[] } = { words: ["travel"] };
    routeFetch([
      { url: "/api/vocabulary/drill/candidates", data: candidates },
      { url: "/api/vocabulary/lexicon", data: LEXICON },
      // V3.33.1: sin pregunta de Recognition el drill degrada a Recall (paso que
      // este test ejercita: prompt oral + grabación).
      {
        url: "/api/vocabulary/drill/recognition",
        data: { word: "travel", available: false, options: [], question_id: "" },
      },
      {
        url: "/api/vocabulary/drill/attempt",
        data: () => {
          candidates.words = [];
          return DRILL_OK;
        },
      },
    ]);

    renderPanel(<PersonalDictionary userId="u1" />);
    const chip = await screen.findByRole("button", { name: "Say travel" });
    fireEvent.click(chip);

    // Se abre el mini-drill con la palabra y su botón de grabar.
    expect(await screen.findByText(/Listen to the word/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Record" }));
    // Detener la grabación dispara submitDrillAttempt → produced.
    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));

    expect(await screen.findByText(/another day to consolidate it/)).toBeTruthy();
    // El chip desaparece (refresh tras producir).
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Say travel" })).toBeNull(),
    );
  });

  it("ofrece el paso Sentence (F6.1) y pasa al decir la palabra dentro de la frase", async () => {
    // Estado mutable: tras el POST de frase (passed), ya no es candidata hoy.
    const candidates: { words: string[] } = { words: ["travel"] };
    routeFetch([
      { url: "/api/vocabulary/drill/candidates", data: candidates },
      { url: "/api/vocabulary/lexicon", data: LEXICON },
      {
        url: "/api/vocabulary/drill/sentence-context",
        data: {
          word: "travel",
          phrase: 'Say the word "travel".',
          source: "template",
          level: "A1",
        },
      },
      {
        url: "/api/vocabulary/drill/sentence-attempt",
        data: () => {
          candidates.words = [];
          return {
            word: "travel",
            phrase: 'Say the word "travel".',
            source: "template",
            produced: true,
            phrase_ok: true,
            passed: true,
            heard: 'say the word "travel"',
            score: 100,
            level: "good",
            fluency: null,
            asr_status: "ok",
          };
        },
      },
    ]);

    renderPanel(<PersonalDictionary userId="u1" />);
    const chip = await screen.findByRole("button", { name: "Say travel" });
    fireEvent.click(chip);

    // Escalera Recognize -> Recall -> Sentence en la misma tarjeta.
    fireEvent.click(screen.getByRole("button", { name: "3 · Sentence" }));
    expect(await screen.findByText('Say the word "travel".')).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Record" }));
    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));

    expect(
      await screen.findByText(/inside the sentence/),
    ).toBeTruthy();
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Say travel" })).toBeNull(),
    );
  });
});

describe("PersonalDictionary · V3.33 paso Recognition", () => {
  beforeEach(() => stubMediaRecorder());
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  const QUESTION = {
    word: "travel",
    available: true,
    options: ["viajar", "comer", "dormir"],
    question_id: "q-travel-1",
  };

  it("acierta «1 · Recognize» y NO saca la palabra de candidatas (informativo)", async () => {
    // Estado inmutable: el acierto de reconocimiento no produce (V3.13), así
    // que la palabra sigue siendo candidata al drill oral.
    const candidates: { words: string[] } = { words: ["travel"] };
    routeFetch([
      { url: "/api/vocabulary/drill/candidates", data: candidates },
      { url: "/api/vocabulary/lexicon", data: LEXICON },
      {
        url: "/api/vocabulary/drill/recognition-attempt",
        data: {
          word: "travel",
          correct: true,
          correct_index: 0,
          selected_index: 0,
        },
      },
      { url: "/api/vocabulary/drill/recognition", data: QUESTION },
    ]);

    renderPanel(<PersonalDictionary userId="u1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Say travel" }));

    // V3.33.1: el drill abre directamente en Recognize (primer peldaño) y la
    // pregunta se carga sola, sin clic manual.
    expect(screen.getByRole("button", { name: "1 · Recognize" })).toBeTruthy();
    expect(await screen.findByText(/What does this word mean/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "viajar" }));
    fireEvent.click(screen.getByRole("button", { name: "Check answer" }));

    expect(
      await screen.findByText(/You recognize the meaning/),
    ).toBeTruthy();
    // Informativo: sin onProduced, la candidata sigue ahí.
    expect(screen.getByRole("button", { name: "Say travel" })).toBeTruthy();
  });

  it("reentrar en «1 · Recognize» pide una pregunta nueva (nuevo intento)", async () => {
    // V3.33.1 (P1-01): cada entrada en Recognize genera un `question_id` nuevo,
    // de modo que la posición de la correcta no se puede memorizar.
    const fetchFn = routeFetch([
      { url: "/api/vocabulary/drill/candidates", data: { words: ["travel"] } },
      { url: "/api/vocabulary/lexicon", data: LEXICON },
      { url: "/api/vocabulary/drill/recognition", data: QUESTION },
    ]);
    const recognitionGets = () =>
      fetchFn.mock.calls.filter((call) =>
        String(call[0]).includes("/api/vocabulary/drill/recognition?"),
      ).length;

    renderPanel(<PersonalDictionary userId="u1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Say travel" }));
    expect(await screen.findByText(/What does this word mean/)).toBeTruthy();
    expect(recognitionGets()).toBe(1);

    // Salir a Recall y volver a Recognize dispara un nuevo GET (nuevo intento).
    fireEvent.click(screen.getByRole("button", { name: "2 · Word" }));
    fireEvent.click(screen.getByRole("button", { name: "1 · Recognize" }));

    await waitFor(() => expect(recognitionGets()).toBe(2));
  });

  it("sin significado disponible degrada a Recall y no rompe la escalera", async () => {
    routeFetch([
      { url: "/api/vocabulary/drill/candidates", data: { words: ["travel"] } },
      { url: "/api/vocabulary/lexicon", data: LEXICON },
      {
        url: "/api/vocabulary/drill/recognition",
        data: { word: "travel", available: false, options: [], question_id: "" },
      },
    ]);

    renderPanel(<PersonalDictionary userId="u1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Say travel" }));

    // V3.33.1: sin pregunta disponible el drill degrada a Recall automáticamente
    // (la escalera no se rompe y no exige un clic manual en Recognize).
    expect(
      await screen.findByText(
        /Listen to the word, then record yourself saying it aloud/,
      ),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "1 · Recognize" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "2 · Word" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "3 · Sentence" })).toBeTruthy();
  });
});
