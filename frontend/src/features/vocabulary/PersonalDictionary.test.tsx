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

/**
 * V3.35: en el paso Sentence el botón Record se pinta DESHABILITADO hasta que
 * llega la frase de contexto (fetch asíncrono). Un clic sobre el botón
 * deshabilitado se pierde y el botón Stop no aparece nunca (flake en CI lento),
 * así que se espera a que esté habilitado antes de grabar.
 */
async function startRecording() {
  const record = await screen.findByRole("button", { name: "Record" });
  await waitFor(() =>
    expect((record as HTMLButtonElement).disabled).toBe(false),
  );
  fireEvent.click(record);
  fireEvent.click(await screen.findByRole("button", { name: "Stop" }));
}

function renderPanel(ui: ReactElement) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      {ui}
    </I18nProvider>,
  );
}

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
    // Estado mutable: tras el POST (passed en Sentence), ya no es candidata.
    // V3.34: la producción oral vive en Sentence (se retiró el paso Word oral),
    // así que el drill degrada Recognize → Recall → Sentence.
    const candidates: { words: string[] } = { words: ["travel"] };
    routeFetch([
      { url: "/api/vocabulary/drill/candidates", data: candidates },
      { url: "/api/vocabulary/lexicon", data: LEXICON },
      {
        url: "/api/vocabulary/drill/recognition",
        data: { word: "travel", available: false, options: [], question_id: "" },
      },
      {
        url: "/api/vocabulary/drill/recall",
        data: { word: "travel", available: false, cue: "", cue_kind: "" },
      },
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

    // Se abre el mini-drill y degrada a Sentence (sin cue ni en Recognize ni
    // en Recall), donde vive el micrófono.
    await startRecording();

    expect(await screen.findByText(/inside the sentence/)).toBeTruthy();
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

    await startRecording();

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
      {
        url: "/api/vocabulary/drill/recall",
        data: {
          word: "travel",
          available: true,
          cue: "viajar",
          cue_kind: "translation",
        },
      },
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
    fireEvent.click(screen.getByRole("button", { name: "2 · Recall" }));
    fireEvent.click(screen.getByRole("button", { name: "1 · Recognize" }));

    await waitFor(() => expect(recognitionGets()).toBe(2));
  });

  it("sin significado disponible en Recognition degrada a Recall y no rompe la escalera", async () => {
    routeFetch([
      { url: "/api/vocabulary/drill/candidates", data: { words: ["travel"] } },
      { url: "/api/vocabulary/lexicon", data: LEXICON },
      {
        url: "/api/vocabulary/drill/recognition",
        data: { word: "travel", available: false, options: [], question_id: "" },
      },
      {
        url: "/api/vocabulary/drill/recall",
        data: {
          word: "travel",
          available: true,
          cue: "viajar",
          cue_kind: "translation",
        },
      },
    ]);

    renderPanel(<PersonalDictionary userId="u1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Say travel" }));

    // V3.33.1: sin pregunta disponible el drill degrada a Recall automáticamente
    // (la escalera no se rompe y no exige un clic manual en Recognize). V3.34:
    // Recall es recuperación por TEXTO (cue = significado, sin micrófono).
    expect(
      await screen.findByText(/Type the English word for this translation/),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "1 · Recognize" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "2 · Recall" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "3 · Sentence" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Record" })).toBeNull();
  });
});

describe("PersonalDictionary · V3.34 paso Recall (texto)", () => {
  beforeEach(() => stubMediaRecorder());
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  const QUESTION = {
    word: "travel",
    available: true,
    options: ["viajar", "comer", "dormir"],
    question_id: "q-travel-1",
  };
  const CUE = {
    word: "travel",
    available: true,
    cue: "viajar",
    cue_kind: "translation",
  };

  it("muestra el significado, oculta la palabra y acredita el recall (sin producción)", async () => {
    // V3.34: el acierto de Recall deja señal léxica de recall, NO producción,
    // así que la palabra sigue siendo candidata al drill oral.
    const candidates: { words: string[] } = { words: ["travel"] };
    routeFetch([
      { url: "/api/vocabulary/drill/candidates", data: candidates },
      { url: "/api/vocabulary/lexicon", data: LEXICON },
      { url: "/api/vocabulary/drill/recognition", data: QUESTION },
      { url: "/api/vocabulary/drill/recall-attempt", data: { word: "travel", correct: true, expected: "travel", delayed: false, recall_days: 1 } },
      { url: "/api/vocabulary/drill/recall", data: CUE },
    ]);

    renderPanel(<PersonalDictionary userId="u1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Say travel" }));
    await screen.findByText(/What does this word mean/);

    // Entrar en Recall: cue visible, sin micrófono y sin la palabra diana.
    fireEvent.click(screen.getByRole("button", { name: "2 · Recall" }));
    expect(await screen.findByText("viajar")).toBeTruthy();
    expect(
      screen.getByText(/Type the English word for this translation/),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Record" })).toBeNull();

    fireEvent.change(screen.getByLabelText("Type the word"), {
      target: { value: "travel" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check" }));

    expect(
      await screen.findByText(/You retrieved the word from its meaning/),
    ).toBeTruthy();
    // Sin producción: la candidata sigue ahí.
    expect(screen.getByRole("button", { name: "Say travel" })).toBeTruthy();
  });

  it("envía la latencia cue→envío como response_time_ms (observacional)", async () => {
    // V3.36: la latencia medida en cliente viaja como dimensión del evento de
    // evidencia. No cambia la puntuación: el acierto se decide en servidor.
    const nowSpy = vi.spyOn(Date, "now").mockReturnValue(1_000);
    const fetchMock = routeFetch([
      { url: "/api/vocabulary/drill/candidates", data: { words: ["travel"] } },
      { url: "/api/vocabulary/lexicon", data: LEXICON },
      { url: "/api/vocabulary/drill/recognition", data: QUESTION },
      {
        url: "/api/vocabulary/drill/recall-attempt",
        data: { word: "travel", correct: true, expected: "travel", delayed: false, recall_days: 1, error_type: "correct" },
      },
      { url: "/api/vocabulary/drill/recall", data: CUE },
    ]);

    renderPanel(<PersonalDictionary userId="u1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Say travel" }));
    await screen.findByText(/What does this word mean/);
    fireEvent.click(screen.getByRole("button", { name: "2 · Recall" }));
    // El cue queda visible con el reloj en 1000 ms.
    expect(await screen.findByText("viajar")).toBeTruthy();

    // El alumno tarda 2,5 s en responder.
    nowSpy.mockReturnValue(3_500);
    fireEvent.change(screen.getByLabelText("Type the word"), {
      target: { value: "travel" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check" }));
    await screen.findByText(/You retrieved the word from its meaning/);

    const call = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("recall-attempt"),
    );
    expect(call).toBeTruthy();
    const body = JSON.parse(
      String((call![1] as RequestInit | undefined)?.body),
    ) as { word: string; answer: string; response_time_ms: number | null };
    expect(body.word).toBe("travel");
    expect(body.response_time_ms).toBe(2_500);
    nowSpy.mockRestore();
  });

  it("falla y revela la palabra correcta en el feedback", async () => {
    routeFetch([
      { url: "/api/vocabulary/drill/candidates", data: { words: ["travel"] } },
      { url: "/api/vocabulary/lexicon", data: LEXICON },
      { url: "/api/vocabulary/drill/recognition", data: QUESTION },
      {
        url: "/api/vocabulary/drill/recall-attempt",
        data: { word: "travel", correct: false, expected: "travel", delayed: false, recall_days: 0 },
      },
      { url: "/api/vocabulary/drill/recall", data: CUE },
    ]);

    renderPanel(<PersonalDictionary userId="u1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Say travel" }));
    await screen.findByText(/What does this word mean/);

    fireEvent.click(screen.getByRole("button", { name: "2 · Recall" }));
    expect(await screen.findByText("viajar")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Type the word"), {
      target: { value: "journey" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check" }));

    expect(await screen.findByText(/the word is "travel"/)).toBeTruthy();
  });
});
