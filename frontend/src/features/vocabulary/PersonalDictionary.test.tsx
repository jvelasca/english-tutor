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
    // V3.21 (V20-16) / V3.22: contadores de la matriz de competencia.
    recognized: 0,
    produced: 0,
    transfer: 0,
    retention: 0,
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
      exposures: 3,
      appearances: 0,
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

    // Escalera Recall -> Sentence en la misma tarjeta.
    fireEvent.click(screen.getByRole("button", { name: "2 · Sentence" }));
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
