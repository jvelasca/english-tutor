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
  direction: "en-es",
  alternatives: [],
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
  direction: "en-es",
  alternatives: [],
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
  direction: "en-es",
  alternatives: [],
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

/** Respuesta de error forzada por una ruta (V3.84.1): lo que `ApiError` necesita
 *  para reconstruir el `detail` del backend en el cliente. */
export interface RouteErrorSpec {
  status: number;
  detail?: string;
}

/** Mock de fetch por URL; los datos pueden ser un valor o una función evaluada
 * en el momento de la llamada (para mutar estado entre llamadas). V3.84.1:
 * `error` fuerza una respuesta `ok:false` (estática o por llamada, para probar
 * un fallo seguido de un reintento con éxito). */
function routeFetch(
  routes: Array<{
    url: string;
    data?: unknown;
    error?: RouteErrorSpec | (() => RouteErrorSpec | null);
  }>,
) {
  const fn = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    const hit = routes.find((r) => url.includes(r.url));
    if (!hit) return Promise.reject(new Error(`unexpected fetch: ${url}`));
    const err =
      typeof hit.error === "function" ? hit.error() : (hit.error ?? null);
    if (err) {
      return Promise.resolve({
        ok: false,
        status: err.status,
        json: async () => ({ detail: err.detail ?? `HTTP ${err.status}` }),
      });
    }
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

  it("estado vacío: ofrece ejemplos y el ejemplo lanza la consulta (V3.75.8)", async () => {
    const fn = routeFetch([{ url: "/api/vocabulary/dictionary", data: COFFEE }]);
    renderPanel(<DictionaryLookup userId="u1" />);

    expect(screen.getByText("Try an example")).toBeTruthy();
    // Los ejemplos no consultan solos: rellenan el campo y buscan al pulsarlos.
    expect(fn).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "travel" }));

    expect(
      (screen.getByLabelText("Search the dictionary") as HTMLInputElement).value,
    ).toBe("travel");
    expect(
      await screen.findByText("A hot drink made from roasted coffee beans."),
    ).toBeTruthy();
    // Una sola consulta al diccionario (el audio puede pedir su catálogo aparte).
    const calls = fn.mock.calls.map((call) => String(call[0]));
    expect(calls.filter((call) => call.includes("/dictionary")).length).toBe(1);
  });

  it("el botón de borrar aparece con texto, vacía el campo y no consulta (V3.75.8)", () => {
    const fn = routeFetch([{ url: "/api/vocabulary/dictionary", data: COFFEE }]);
    renderPanel(<DictionaryLookup userId="u1" />);

    const input = screen.getByLabelText("Search the dictionary") as HTMLInputElement;
    // Sin texto no hay botón que borrar: no es un botón muerto en reposo.
    expect(screen.queryByRole("button", { name: "Clear the search" })).toBeNull();

    fireEvent.change(input, { target: { value: "coffee" } });
    expect(input.value).toBe("coffee");

    fireEvent.click(screen.getByRole("button", { name: "Clear the search" }));
    expect(input.value).toBe("");
    expect(screen.queryByRole("button", { name: "Clear the search" })).toBeNull();
    expect(fn).not.toHaveBeenCalled();
  });

  it("tras buscar, la X limpia la búsqueda y el resultado, y vuelven los ejemplos (V3.80.1)", async () => {
    // Semántica fijada en V3.80.1: la X es «limpiar búsqueda Y resultado», no
    // «vaciar el campo dejando la tarjeta anterior». Un campo vacío con un
    // resultado viejo debajo es un estado que miente.
    const fn = routeFetch([{ url: "/api/vocabulary/dictionary", data: COFFEE }]);
    renderPanel(<DictionaryLookup userId="u1" />);

    fillAndSubmit("coffee");
    expect(
      await screen.findByRole("heading", { name: "coffee" }),
    ).toBeTruthy();

    const input = screen.getByLabelText("Search the dictionary") as HTMLInputElement;
    fireEvent.click(screen.getByRole("button", { name: "Clear the search" }));

    expect(input.value).toBe("");
    expect(screen.queryByRole("button", { name: "Clear the search" })).toBeNull();
    // El resultado se va con la búsqueda...
    expect(screen.queryByRole("heading", { name: "coffee" })).toBeNull();
    expect(
      screen.queryByText("A hot drink made from roasted coffee beans."),
    ).toBeNull();
    // ...y vuelven los ejemplos, que es el estado honesto de «nueva consulta».
    expect(screen.getByText("Try an example")).toBeTruthy();
    // Borrar no dispara ninguna consulta nueva.
    expect(fn.mock.calls.map((call) => String(call[0])).filter((url) =>
      url.includes("/dictionary"),
    ).length).toBe(1);
  });

  it("el color de la dirección marca el conmutador y la tarjeta del resultado (V3.75.8)", async () => {
    routeFetch([{ url: "/api/vocabulary/dictionary", data: COFFEE }]);
    renderPanel(<DictionaryLookup userId="u1" />);

    // EN→ES activo por defecto: su pastilla lleva la clase de SU dirección y la
    // opción inactiva no. La clase la pinta `styles/legacy.css` (`.dir-*`), cuyo
    // contraste mide y vigila `scripts/contrast_audit.mjs`.
    expect(
      screen.getByRole("button", { name: "English → Spanish" }).className,
    ).toContain("dir-en-es");
    expect(
      screen.getByRole("button", { name: "Spanish → English" }).className,
    ).not.toContain("dir-es-en");

    fillAndSubmit("coffee");

    const headword = await screen.findByRole("heading", { name: "coffee" });
    // La tarjeta se tiñe del color de la dirección con la que se buscó.
    expect(headword.closest(".dir-en-es")).not.toBeNull();
    expect(headword.closest(".dir-es-en")).toBeNull();
  });

  it("sin cabecera propia no repite el título de la pantalla (V3.75.8)", () => {
    // `/diccionario` ya trae su `h1` y su subtítulo: la vista de consulta los
    // apaga para no dejar dos `h1` en la misma página.
    routeFetch([{ url: "/api/vocabulary/dictionary", data: COFFEE }]);
    renderPanel(<DictionaryLookup userId="u1" showHeader={false} />);

    expect(screen.queryByText("Dictionary lookup")).toBeNull();
    expect(screen.getByLabelText("Search the dictionary")).toBeTruthy();
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
    // Frase de ejemplo determinista con su altavoz + audio de la palabra.
    // V3.75.5: el altavoz deja de ser un `ListenButton` mudo y pasa a ser el
    // control de repetición con acentos (aquí solo A: no hay catálogo en el test).
    expect(screen.getByText("I drink coffee every morning.")).toBeTruthy();
    expect(
      screen.getAllByRole("button", { name: /^Repeat with accent A/ }).length,
    ).toBe(2);
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
    routeFetch([
      { url: "/api/vocabulary/dictionary", data: COFFEE },
      {
        url: "/api/vocabulary/drill/recognition",
        data: {
          word: "coffee",
          available: true,
          options: ["café", "a soft drink", "a type of grain"],
          question_id: "q-coffee-1",
        },
      },
    ]);
    renderPanel(<DictionaryLookup userId="u1" />);

    fillAndSubmit("coffee");
    // El CTA de práctica vive junto al audio de la palabra en la tarjeta.
    const practiceCta = await screen.findByRole("button", {
      name: "Practice this word",
    });
    expect(practiceCta).toBeTruthy();

    fireEvent.click(practiceCta);
    // Se monta la escalera de drill (Recognize → Recall → Sentence): mismo
    // arranque en Recognize que en el diccionario personal (V3.33.1).
    expect(await screen.findByText(/What does this word mean/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "1 · Recognize" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "2 · Recall" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "3 · Sentence" })).toBeTruthy();
    // V3.34: Recognize no usa micrófono (el micrófono vive en Sentence).
    expect(screen.queryByRole("button", { name: "Record" })).toBeNull();

    // Cerrar la escalera la desmonta.
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() =>
      expect(screen.queryByText(/What does this word mean/)).toBeNull(),
    );
  });

  it("producir la palabra tras «Practicar» refresca la entrada en silencio (sin desmontar el drill)", async () => {
    // V3.32: la evidencia del drill es real; tras producir, la marca de uso de
    // la tarjeta se refresca con un re-lookup silencioso (mismo endpoint).
    // V3.34: la producción oral vive en el paso Sentence (el paso Word oral se
    // retiró), así que el test recorre Recognize → Recall → Sentence.
    const dictionaryHits = { count: 0 };
    const fn = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/vocabulary/dictionary")) {
        dictionaryHits.count += 1;
        return Promise.resolve({ ok: true, json: async () => COFFEE });
      }
      if (url.includes("/api/vocabulary/drill/recognition")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            word: "coffee",
            available: false,
            options: [],
            question_id: "",
          }),
        });
      }
      if (url.includes("/api/vocabulary/drill/recall")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            word: "coffee",
            available: false,
            cue: "",
            cue_kind: "",
          }),
        });
      }
      if (url.includes("/api/vocabulary/drill/sentence-context")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            word: "coffee",
            phrase: 'Say the word "coffee".',
            source: "template",
            level: "A1",
          }),
        });
      }
      if (url.includes("/api/vocabulary/drill/sentence-attempt")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          }),
        });
      }
      return Promise.reject(new Error(`unexpected fetch: ${url}`));
    });
    vi.stubGlobal("fetch", fn);
    renderPanel(<DictionaryLookup userId="u1" />);

    fillAndSubmit("coffee");
    const cta = await screen.findByRole("button", { name: "Practice this word" });
    fireEvent.click(cta);

    // Sin cue de Recognition ni de Recall la escalera degrada a Sentence.
    await startRecording();

    // Resultado del drill: producción correcta.
    expect(await screen.findByText(/inside the sentence/)).toBeTruthy();
    // El drill sigue montado (el re-lookup no lo desmonta).
    expect(screen.getByRole("button", { name: "Record" })).toBeTruthy();
    // Se produjo un re-lookup silencioso del diccionario para refrescar la marca.
    await waitFor(() => expect(dictionaryHits.count).toBe(2));
  });

  it("la escalera ofrece el paso Sentence y lo supera (F6.1) sin abandonar el lookup", async () => {
    routeFetch([
      { url: "/api/vocabulary/dictionary", data: COFFEE },
      {
        url: "/api/vocabulary/drill/recognition",
        data: { word: "coffee", available: false, options: [], question_id: "" },
      },
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

    fireEvent.click(screen.getByRole("button", { name: "3 · Sentence" }));
    expect(await screen.findByText('Say the word "coffee".')).toBeTruthy();

    await startRecording();

    expect(await screen.findByText(/inside the sentence/)).toBeTruthy();
    // La tarjeta de resultado sigue visible (el drill convive con ella).
    expect(screen.getByText("A hot drink made from roasted coffee beans.")).toBeTruthy();
  });
});

describe("DictionaryLookup · V3.33 Recognition (MCQ definición ↔ palabra)", () => {
  beforeEach(() => stubMediaRecorder());
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  const QUESTION = {
    word: "coffee",
    available: true,
    options: ["café", "a soft drink", "a type of grain", "a sweet dessert"],
    question_id: "q-coffee-1",
  };

  it("acierta el paso «1 · Recognize» sin refrescar la tarjeta (informativo)", async () => {
    // V3.33: el MC de reconocimiento no demuestra destreza productiva (V3.13):
    // el acierto NO dispara onProduced y por tanto no hay re-lookup silencioso
    // del diccionario (a diferencia del éxito del paso oral).
    const dictionaryHits = { count: 0 };
    const fn = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/vocabulary/dictionary")) {
        dictionaryHits.count += 1;
        return Promise.resolve({ ok: true, json: async () => COFFEE });
      }
      if (url.includes("/api/vocabulary/drill/recognition-attempt")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            word: "coffee",
            correct: true,
            correct_index: 0,
            selected_index: 0,
          }),
        });
      }
      if (url.includes("/api/vocabulary/drill/recognition")) {
        return Promise.resolve({ ok: true, json: async () => QUESTION });
      }
      return Promise.reject(new Error(`unexpected fetch: ${url}`));
    });
    vi.stubGlobal("fetch", fn);
    renderPanel(<DictionaryLookup userId="u1" />);

    fillAndSubmit("coffee");
    fireEvent.click(
      await screen.findByRole("button", { name: "Practice this word" }),
    );

    // V3.33.1: el drill abre en Recognize (primer peldaño) y carga la pregunta
    // solo, sin clic manual.
    expect(await screen.findByText(/What does this word mean/)).toBeTruthy();
    // Sin micrófono en este paso: se elige una opción y se comprueba.
    expect(screen.queryByRole("button", { name: "Record" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "café" }));
    fireEvent.click(screen.getByRole("button", { name: "Check answer" }));

    expect(await screen.findByText(/You recognize the meaning/)).toBeTruthy();
    // Informativo: no re-lookup para refrescar la marca de uso.
    expect(dictionaryHits.count).toBe(1);
  });

  it("falla y revela la opción correcta en el feedback", async () => {
    routeFetch([
      { url: "/api/vocabulary/dictionary", data: COFFEE },
      {
        url: "/api/vocabulary/drill/recognition-attempt",
        data: {
          word: "coffee",
          correct: false,
          correct_index: 0,
          selected_index: 1,
        },
      },
      { url: "/api/vocabulary/drill/recognition", data: QUESTION },
    ]);
    renderPanel(<DictionaryLookup userId="u1" />);

    fillAndSubmit("coffee");
    fireEvent.click(
      await screen.findByRole("button", { name: "Practice this word" }),
    );
    // V3.33.1: el drill arranca en Recognize; la pregunta se carga sola.
    await screen.findByText(/What does this word mean/);

    fireEvent.click(screen.getByRole("button", { name: "a soft drink" }));
    fireEvent.click(screen.getByRole("button", { name: "Check answer" }));

    // Feedback ko con la opción correcta revelada por el servidor.
    expect(
      await screen.findByText(/Not this one — the meaning is “café”/),
    ).toBeTruthy();
  });
});

describe("DictionaryLookup · V3.39 diccionario reversible ES→EN", () => {
  beforeEach(() => stubMediaRecorder());
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  const CASA_REVERSE = {
    word: "casa",
    kind: "word",
    cefr: "A1",
    definition_source: "llm",
    pos: "noun",
    definition: "A building where people live.",
    translation: "house",
    direction: "es-en",
    alternatives: ["home", "place"],
    example: null,
    usage: {
      tracked: true,
      surface: {
        status: "known",
        mastery: 0.5,
        recall: 0.7,
        next_review_days: 4,
        production_count: 1,
        exposure_count: 2,
        production_channels: ["speaking"],
        competence: {
          recognition: true,
          production: true,
          production_channels: ["speaking"],
          transfer_contexts: 0,
          transfer: false,
          retention: false,
          spaced_exposure: false,
          spaced_production: false,
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

  const CASA_NO_EQUIVALENT = {
    ...CASA_REVERSE,
    definition_source: "none",
    definition: null,
    translation: null,
    alternatives: [],
    example: null,
  };

  it("conmutador: busca ES→EN, reetiqueta el resultado y lista alternativas", async () => {
    const fn = routeFetch([
      { url: "/api/vocabulary/dictionary", data: CASA_REVERSE },
    ]);
    renderPanel(<DictionaryLookup userId="u1" />);

    // Por defecto EN→ES: la etiqueta de la traducción es «In Spanish».
    fireEvent.click(screen.getByRole("button", { name: "Spanish → English" }));

    fillAndSubmit("casa");

    expect(await screen.findByText("A building where people live.")).toBeTruthy();
    // El equivalente inglés llega como `translation` con la etiqueta inversa.
    expect(screen.getByText("house")).toBeTruthy();
    expect(screen.getByText("In English")).toBeTruthy();
    expect(screen.queryByText("In Spanish")).toBeNull();
    expect(screen.getByText("Other translations")).toBeTruthy();
    expect(screen.getByText("home · place")).toBeTruthy();
    // La petición viaja con la dirección inversa.
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(body).toEqual({ word: "casa", direction: "es-en" });
  });

  it("en ES→EN la tarjeta se tiñe del color de la dirección inversa (V3.75.8)", async () => {
    routeFetch([{ url: "/api/vocabulary/dictionary", data: CASA_REVERSE }]);
    renderPanel(<DictionaryLookup userId="u1" />);

    fireEvent.click(screen.getByRole("button", { name: "Spanish → English" }));
    expect(
      screen.getByRole("button", { name: "Spanish → English" }).className,
    ).toContain("dir-es-en");

    fillAndSubmit("casa");

    const headword = await screen.findByRole("heading", { name: "casa" });
    expect(headword.closest(".dir-es-en")).not.toBeNull();
    expect(headword.closest(".dir-en-es")).toBeNull();
  });

  it("sin equivalente inglés no ofrece practicar ni audio", async () => {
    routeFetch([
      { url: "/api/vocabulary/dictionary", data: CASA_NO_EQUIVALENT },
    ]);
    renderPanel(<DictionaryLookup userId="u1" />);

    fireEvent.click(screen.getByRole("button", { name: "Spanish → English" }));
    fillAndSubmit("casa");

    expect(
      await screen.findByText(/The dictionary content isn't available right now/),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Practice this word" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Hear the word" })).toBeNull();
  });

  it("en ES→EN el drill practica el equivalente inglés, no el término español", async () => {
    routeFetch([
      { url: "/api/vocabulary/dictionary", data: CASA_REVERSE },
      {
        url: "/api/vocabulary/drill/recognition",
        data: {
          word: "house",
          available: true,
          options: ["casa", "a vehicle", "a meal"],
          question_id: "q-house-1",
        },
      },
    ]);
    renderPanel(<DictionaryLookup userId="u1" />);

    fireEvent.click(screen.getByRole("button", { name: "Spanish → English" }));
    fillAndSubmit("casa");

    fireEvent.click(
      await screen.findByRole("button", { name: "Practice this word" }),
    );

    // La escalera arranca con la palabra INGLESA.
    expect(await screen.findByText(/What does this word mean/)).toBeTruthy();
    const recognitionCall = (
      globalThis.fetch as unknown as { mock: { calls: unknown[][] } }
    ).mock.calls.find((call) => String(call[0]).includes("drill/recognition"));
    expect(String(recognitionCall?.[0])).toContain("word=house");
  });
});

describe("DictionaryLookup · contratos incompletos (V3.77.2)", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("una entrada sin `usage` no revienta la tarjeta de resultado", async () => {
    // El `setEntry(data)` sin validar dejaba `entry.usage.surface` a `undefined`
    // y la marca de uso `.tracked` lanzaba al pintar la tarjeta.
    routeFetch([
      {
        url: "/api/vocabulary/dictionary",
        data: {
          word: "coffee",
          kind: "word",
          cefr: "A1",
          definition_source: "llm",
          pos: "noun",
          definition: "A hot drink.",
        },
      },
    ]);
    renderPanel(<DictionaryLookup userId="u1" />);
    fillAndSubmit("coffee");

    expect(await screen.findByText("A hot drink.")).toBeTruthy();
    // `usage` ausente se degrada a «no registrada»: bloque informativo vacío,
    // no un acceso a `.tracked` de `undefined`.
    expect(screen.getByText("This word in your learning")).toBeTruthy();
    expect(screen.getByText("Not met yet")).toBeTruthy();
  });

  it("una entrada con `usage` no-objeto y sin `alternatives` tampoco", async () => {
    routeFetch([
      {
        url: "/api/vocabulary/dictionary",
        data: {
          word: "coffee",
          kind: "word",
          cefr: "A1",
          definition_source: "llm",
          pos: "noun",
          definition: "A hot drink.",
          translation: "café",
          usage: "raro",
          alternatives: "café",
        },
      },
    ]);
    renderPanel(<DictionaryLookup userId="u1" />);
    fillAndSubmit("coffee");

    expect(await screen.findByText("A hot drink.")).toBeTruthy();
  });
});

describe("DictionaryLookup · V3.83.0 Diccionario → Flashcards", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  // Una lista propia (destino de archivo) y un pack curado (NO es destino).
  // V3.84.0: el destino del alta es un MAZO manual, no una lista. El mazo
  // automático (id 0) no se ofrece: es una vista del léxico, no un destino.
  const AUTO_DECK = {
    id: 0,
    name: "auto",
    slug: "",
    is_auto: true,
    new_per_day: 10,
    review_per_day: 50,
    card_count: 0,
    due_count: 0,
    new_count: 0,
    reviewed_today: 0,
  };
  const MANUAL_DECK = {
    ...AUTO_DECK,
    id: 7,
    name: "Mi mazo",
    slug: "mi-mazo",
    is_auto: false,
  };

  it("añade la palabra como aprendizaje y como tarjeta en los mazos marcados (V3.86.0)", async () => {
    const onOpenFlashcards = vi.fn();
    const fn = routeFetch([
      { url: "/api/vocabulary/dictionary", data: NEBULA },
      // OJO al orden: `routeFetch` casa por `includes`, así que la ruta de las
      // tarjetas (más específica) va ANTES que la de la lista de mazos.
      {
        url: "/api/vocabulary/cards",
        data: {
          id: 11,
          deck_id: 7,
          deck_ids: [7],
          front: "nebula",
          back: "",
          mnemonic: "",
          state: "new",
          reps: 0,
          due_at: "",
          created_at: "2026-09-25T10:00:00Z",
        },
      },
      {
        url: "/api/vocabulary/decks",
        data: {
          decks: [AUTO_DECK, MANUAL_DECK],
          auto_deck_id: 0,
          fsrs_version: "test",
        },
      },
      {
        url: "/api/vocabulary/items",
        data: {
          added: ["nebula"],
          item: { word: "nebula", translation: "", definition: "" },
        },
      },
    ]);
    renderPanel(
      <DictionaryLookup userId="u1" onOpenFlashcards={onOpenFlashcards} />,
    );

    fillAndSubmit("nebula");
    fireEvent.click(
      await screen.findByRole("button", { name: "Add to Flashcards" }),
    );

    // El panel declara el vínculo ANTES de confirmar: la palabra entra en el
    // proceso de estudio (PERSONAL + mazo automático), no es un cajón aparte.
    expect(
      screen.getByText(/The word always joins your study flow/),
    ).toBeTruthy();
    // Solo se ofrecen mazos MANUALES, y como casillas (la ficha puede nacer en
    // varios a la vez): el automático no es un destino.
    expect(await screen.findByLabelText("Mi mazo")).toBeTruthy();
    expect(screen.queryByLabelText("auto")).toBeNull();
    // V3.86.0: sin equivalente la consulta no se queda sin salida — se pide el
    // reverso a mano para que la tarjeta sirva.
    expect(screen.getByText(/No equivalent was found/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Back of the card"), {
      target: { value: "nebulosa" },
    });

    fireEvent.click(screen.getByLabelText("Mi mazo"));
    fireEvent.click(
      screen.getByRole("button", { name: "Add and start learning" }),
    );

    // El éxito llega cuando terminan LAS DOS escrituras (léxico + tarjeta), así
    // que se espera a él antes de inspeccionar las llamadas: la segunda va en un
    // microtask posterior al `await` de la primera.
    expect(
      await screen.findByText("nebula is now learning."),
    ).toBeTruthy();

    // 1) El alta de léxico: léxico + carta FSRS, sin colección.
    const addCall = fn.mock.calls.find((call) =>
      String(call[0]).includes("/api/vocabulary/items"),
    );
    expect(JSON.parse(String(addCall?.[1]?.body))).toEqual({
      word: "nebula",
      translation: "",
      collection_id: null,
    });

    // 2) La tarjeta manual: UNA escritura que la crea en TODOS los mazos
    //    marcados (tabla puente), con su recordatorio.
    const cardCall = fn.mock.calls.find((call) =>
      String(call[0]).includes("/api/vocabulary/cards"),
    );
    expect(cardCall).toBeTruthy();
    expect(JSON.parse(String(cardCall?.[1]?.body))).toEqual({
      front: "nebula",
      back: "nebulosa",
      mnemonic: "",
      deck_ids: [7],
    });

    // Éxito honesto: «ya está en aprendizaje» + dónde se guardó + salida a
    // estudiar ESE mazo.
    expect(screen.getByText(/Saved as a card in/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Study in Flashcards" }));
    expect(onOpenFlashcards).toHaveBeenCalledWith(7);
  });

  it("permite crear un mazo desde el propio panel y lo deja marcado (V3.86.0)", async () => {
    const onOpenFlashcards = vi.fn();
    // La misma URL responde distinto según sea el GET (lista) o el POST (alta):
    // se cuentan las llamadas porque `routeFetch` casa por URL, no por método.
    let deckCalls = 0;
    const fn = routeFetch([
      { url: "/api/vocabulary/dictionary", data: NEBULA },
      {
        url: "/api/vocabulary/decks",
        data: () => {
          deckCalls += 1;
          if (deckCalls === 1) {
            return {
              decks: [AUTO_DECK],
              auto_deck_id: 0,
              fsrs_version: "test",
            };
          }
          return {
            ...AUTO_DECK,
            id: 7,
            name: "Verbos",
            slug: "verbos",
            is_auto: false,
          };
        },
      },
    ]);
    renderPanel(
      <DictionaryLookup userId="u1" onOpenFlashcards={onOpenFlashcards} />,
    );

    fillAndSubmit("nebula");
    fireEvent.click(
      await screen.findByRole("button", { name: "Add to Flashcards" }),
    );

    fireEvent.click(screen.getByRole("button", { name: "New deck" }));
    fireEvent.change(screen.getByLabelText("New deck name"), {
      target: { value: "Verbos" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create deck" }));

    // El mazo recién creado queda marcado: no hay que volver a elegirlo.
    await waitFor(() =>
      expect(
        (screen.getByLabelText("Verbos") as HTMLInputElement).checked,
      ).toBe(true),
    );
    const createCall = fn.mock.calls.find(
      (call) =>
        String(call[0]).includes("/api/vocabulary/decks") &&
        call[1]?.method === "POST",
    );
    expect(JSON.parse(String(createCall?.[1]?.body))).toEqual({
      name: "Verbos",
    });
  });

  it("una palabra ya rastreada ya no se queda sin salida: añade la ficha y ofrece estudiar (V3.86.0)", async () => {
    // COFFEE ya está en el léxico (`usage.tracked`). Antes el alta se escondía y
    // solo quedaba estudiar; ahora se puede crear la ficha sin reescribir el
    // léxico, y el panel lo declara.
    const onOpenFlashcards = vi.fn();
    routeFetch([
      { url: "/api/vocabulary/dictionary", data: COFFEE },
      {
        url: "/api/vocabulary/decks",
        data: {
          decks: [AUTO_DECK, MANUAL_DECK],
          auto_deck_id: 0,
          fsrs_version: "test",
        },
      },
    ]);
    renderPanel(
      <DictionaryLookup userId="u1" onOpenFlashcards={onOpenFlashcards} />,
    );

    fillAndSubmit("coffee");
    expect(
      await screen.findByText(/Already in your dictionary/),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Add to Flashcards" }));
    expect(
      await screen.findByText(/only the card and its decks are saved/),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Study in Flashcards" }));
    expect(onOpenFlashcards).toHaveBeenCalledTimes(1);
  });

  // V3.86.0: «lima → la capital del Perú» deja de ser una trampa. La consulta ES→EN
  // trae los significados candidatos y el alumno elige: el nombre propio va
  // marcado y NUNCA por defecto.
  const LIMA = {
    word: "lima",
    kind: "word",
    cefr: "A1",
    definition_source: "llm",
    pos: "noun",
    definition: "A tool with a rough surface used for smoothing.",
    translation: "file",
    direction: "es-en",
    alternatives: [],
    meanings: [
      {
        term: "file",
        pos: "noun",
        gloss: "Herramienta con superficie rugosa.",
        domain: "tools",
        proper_noun: false,
      },
      {
        term: "lime",
        pos: "noun",
        gloss: "Cítrico verde.",
        domain: "food",
        proper_noun: false,
      },
      {
        term: "Lima",
        pos: "noun",
        gloss: "Capital del Perú.",
        domain: "geography",
        proper_noun: true,
      },
    ],
    example: null,
    usage: { tracked: false, surface: null, unit: null },
  };

  it("V3.86.0: elige el significado y el elegido manda en la práctica y en el alta", async () => {
    const fn = routeFetch([
      { url: "/api/vocabulary/dictionary", data: LIMA },
      {
        url: "/api/vocabulary/cards",
        data: {
          id: 21,
          deck_id: 7,
          deck_ids: [7],
          front: "Lima",
          back: "lima",
          mnemonic: "",
          state: "new",
          reps: 0,
          due_at: "",
          created_at: "2026-09-25T10:00:00Z",
        },
      },
      {
        url: "/api/vocabulary/decks",
        data: {
          decks: [AUTO_DECK, MANUAL_DECK],
          auto_deck_id: 0,
          fsrs_version: "test",
        },
      },
      {
        url: "/api/vocabulary/items",
        data: {
          added: ["Lima"],
          item: { word: "Lima", translation: "lima", definition: "" },
        },
      },
    ]);
    renderPanel(<DictionaryLookup userId="u1" />);

    fireEvent.click(screen.getByRole("button", { name: "Spanish → English" }));
    fillAndSubmit("lima");

    // El defecto es el primer significado que NO es nombre propio, aunque el
    // nombre propio venga el último (y estaría disponible a un clic).
    const fileRadio = (await screen.findByRole("radio", {
      name: "Meaning: file · noun",
    })) as HTMLInputElement;
    const properRadio = screen.getByRole("radio", {
      name: "Meaning: Lima · noun",
    }) as HTMLInputElement;
    expect(fileRadio.checked).toBe(true);
    expect(properRadio.checked).toBe(false);
    // El nombre propio se marca, no se disimula.
    expect(screen.getByText("Proper noun")).toBeTruthy();

    // Elegir «Lima» cambia el equivalente de la tarjeta…
    fireEvent.click(properRadio);
    expect(
      (screen.getByRole("radio", { name: "Meaning: Lima · noun" }) as HTMLInputElement)
        .checked,
    ).toBe(true);

    // …y el alta: la ficha y el léxico se crean con el significado ELEGIDO, no
    // con el de por defecto.
    fireEvent.click(screen.getByRole("button", { name: "Add to Flashcards" }));
    fireEvent.click(await screen.findByLabelText("Mi mazo"));
    fireEvent.click(
      screen.getByRole("button", { name: "Add and start learning" }),
    );
    expect(await screen.findByText("Lima is now learning.")).toBeTruthy();

    const cardCall = fn.mock.calls.find((call) =>
      String(call[0]).includes("/api/vocabulary/cards"),
    );
    expect(JSON.parse(String(cardCall?.[1]?.body))).toEqual({
      front: "Lima",
      back: "lima",
      mnemonic: "",
      deck_ids: [7],
    });
    const addCall = fn.mock.calls.find((call) =>
      String(call[0]).includes("/api/vocabulary/items"),
    );
    expect(JSON.parse(String(addCall?.[1]?.body))).toEqual({
      word: "Lima",
      translation: "lima",
      collection_id: null,
    });
  });

  it("V3.86.0: el recordatorio viaja en la ficha y los mazos marcados van juntos", async () => {
    const EXTRA_DECK = { ...MANUAL_DECK, id: 8, name: "Cocina", slug: "cocina" };
    const fn = routeFetch([
      { url: "/api/vocabulary/dictionary", data: COFFEE },
      {
        url: "/api/vocabulary/cards",
        data: {
          id: 31,
          deck_id: 7,
          deck_ids: [7, 8],
          front: "coffee",
          back: "café",
          mnemonic: "café con leche",
          state: "new",
          reps: 0,
          due_at: "",
          created_at: "2026-09-25T10:00:00Z",
        },
      },
      {
        url: "/api/vocabulary/decks",
        data: {
          decks: [AUTO_DECK, MANUAL_DECK, EXTRA_DECK],
          auto_deck_id: 0,
          fsrs_version: "test",
        },
      },
    ]);
    renderPanel(<DictionaryLookup userId="u1" />);

    fillAndSubmit("coffee");
    // COFFEE ya está rastreada: no se reescribe el léxico, solo la ficha.
    fireEvent.click(
      await screen.findByRole("button", { name: "Add to Flashcards" }),
    );
    fireEvent.click(await screen.findByLabelText("Mi mazo"));
    fireEvent.click(screen.getByLabelText("Cocina"));
    fireEvent.change(screen.getByLabelText("Reminder (optional)"), {
      target: { value: "  café con leche  " },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Add and start learning" }),
    );

    const cardCall = await waitFor(() => {
      const call = fn.mock.calls.find((c) =>
        String(c[0]).includes("/api/vocabulary/cards"),
      );
      expect(call).toBeTruthy();
      return call;
    });
    // El recordatorio se recorta y los DOS mazos viajan en una sola escritura.
    expect(JSON.parse(String(cardCall?.[1]?.body))).toEqual({
      front: "coffee",
      back: "café",
      mnemonic: "café con leche",
      deck_ids: [7, 8],
    });
    // Palabra rastreada: el léxico NO se vuelve a dar de alta.
    expect(
      fn.mock.calls.filter((call) =>
        String(call[0]).includes("/api/vocabulary/items"),
      ),
    ).toHaveLength(0);
    // El éxito nombra los dos mazos y abre el principal en el estudio.
    expect(await screen.findByText(/Saved as a card in/)).toBeTruthy();
    expect(screen.getByText(/“Mi mazo, Cocina”/)).toBeTruthy();
  });

  it("V3.84.1/V3.86.0: si falla la tarjeta, declara el estado PARCIAL y reintenta solo la tarjeta", async () => {
    const onOpenFlashcards = vi.fn();
    // La PRIMERA llamada de la tarjeta falla y la segunda entra: es justo el
    // reintento que ofrece el panel. El alta del léxico nunca falla.
    let cardCalls = 0;
    const fn = routeFetch([
      { url: "/api/vocabulary/dictionary", data: NEBULA },
      {
        url: "/api/vocabulary/cards",
        error: () => {
          cardCalls += 1;
          return cardCalls === 1 ? { status: 500, detail: "boom" } : null;
        },
        data: {
          id: 11,
          deck_id: 7,
          deck_ids: [7],
          front: "nebula",
          back: "",
          mnemonic: "",
          state: "new",
          reps: 0,
          due_at: "",
          created_at: "2026-09-25T10:00:00Z",
        },
      },
      {
        url: "/api/vocabulary/decks",
        data: {
          decks: [AUTO_DECK, MANUAL_DECK],
          auto_deck_id: 0,
          fsrs_version: "test",
        },
      },
      {
        url: "/api/vocabulary/items",
        data: {
          added: ["nebula"],
          item: { word: "nebula", translation: "", definition: "" },
        },
      },
    ]);
    renderPanel(<DictionaryLookup userId="u1" onOpenFlashcards={onOpenFlashcards} />);

    fillAndSubmit("nebula");
    fireEvent.click(
      await screen.findByRole("button", { name: "Add to Flashcards" }),
    );
    fireEvent.click(await screen.findByLabelText("Mi mazo"));
    fireEvent.change(screen.getByLabelText("Back of the card"), {
      target: { value: "nebulosa" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Add and start learning" }),
    );

    // Estado PARCIAL declarado: ni «ok» (mentiría) ni un «error» genérico que
    // oculta que el aprendizaje sí se completó.
    expect(
      await screen.findByText(/is now learning, but it could not be saved in/),
    ).toBeTruthy();
    expect(
      screen.getByText(/Your word is saved in learning and follows the study flow/),
    ).toBeTruthy();
    // La primera escritura (léxico) sí ocurrió y la segunda falló una vez.
    expect(
      fn.mock.calls.filter((call) =>
        String(call[0]).includes("/api/vocabulary/items"),
      ),
    ).toHaveLength(1);
    expect(cardCalls).toBe(1);
    // El estudio sigue disponible: la palabra ya está en el flujo.
    fireEvent.click(screen.getByRole("button", { name: "Study in Flashcards" }));
    expect(onOpenFlashcards).toHaveBeenCalledTimes(1);
    expect(onOpenFlashcards.mock.calls[0][0]).toBeUndefined();

    // Reintento: SOLO la tarjeta del mazo, y cierra en el éxito completo.
    fireEvent.click(
      screen.getByRole("button", { name: "Retry saving to the deck" }),
    );
    expect(await screen.findByText("nebula is now learning.")).toBeTruthy();
    expect(screen.getByText(/Saved as a card in/)).toBeTruthy();
    expect(cardCalls).toBe(2);
    // El reintento no repite el alta del léxico: sigue habiendo UNA sola.
    expect(
      fn.mock.calls.filter((call) =>
        String(call[0]).includes("/api/vocabulary/items"),
      ),
    ).toHaveLength(1);
  });

  it("V3.84.1/V3.86.0: un nombre de mazo duplicado se declara y NO oculta los mazos", async () => {
    // La llamada 1 es el GET de la lista (al abrir el panel) y la 2 el POST de
    // creación: solo la creación falla, con el código que manda el backend.
    let deckCalls = 0;
    routeFetch([
      { url: "/api/vocabulary/dictionary", data: NEBULA },
      {
        url: "/api/vocabulary/decks",
        error: () => {
          deckCalls += 1;
          return deckCalls === 2
            ? { status: 400, detail: "DECK_NAME_TAKEN" }
            : null;
        },
        data: {
          decks: [AUTO_DECK, MANUAL_DECK],
          auto_deck_id: 0,
          fsrs_version: "test",
        },
      },
    ]);
    renderPanel(<DictionaryLookup userId="u1" />);

    fillAndSubmit("nebula");
    fireEvent.click(
      await screen.findByRole("button", { name: "Add to Flashcards" }),
    );
    expect(await screen.findByLabelText("Mi mazo")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "New deck" }));
    fireEvent.change(screen.getByLabelText("New deck name"), {
      target: { value: "Verbos" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create deck" }));

    expect(
      await screen.findByText("You already have a deck with that name. Pick another one."),
    ).toBeTruthy();
    // El fallo de creación NO es un fallo de carga: los mazos siguen visibles y
    // no se pinta el mensaje de «no se pudieron cargar tus mazos».
    expect(screen.getByLabelText("Mi mazo")).toBeTruthy();
    expect(screen.queryByText(/could not be loaded/)).toBeNull();
  });
});
