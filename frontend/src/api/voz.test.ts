// @vitest-environment jsdom
/**
 * Vitest de la API de voz (V3.39, Fase 2): `transcribe` acepta el idioma del
 * audio y `speak` lo envía al TTS para que el Traductor use voces españolas.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { speak, transcribe } from "./voz";

function mockFetch(data: unknown) {
  const fn = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => data,
    blob: async () => new Blob(["wav"], { type: "audio/wav" }),
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

/** Respuesta con cabeceras reales (`Headers`), como la del endpoint de TTS. */
function mockTtsResponse(headers: Record<string, string>) {
  const fn = vi.fn().mockResolvedValue({
    ok: true,
    headers: new Headers(headers),
    blob: async () => new Blob(["wav"], { type: "audio/wav" }),
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

class FakeAudio {
  onended: (() => void) | null = null;
  onerror: (() => void) | null = null;
  src = "";
  constructor(url: string) {
    this.src = url;
  }
  play() {
    this.onended?.();
    return Promise.resolve();
  }
}

describe("api/voz · V3.39 idioma de la voz", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("transcribe envía el idioma inglés por defecto (contrato histórico)", async () => {
    const fn = mockFetch({ text: "hello" });
    await transcribe(new Blob(["x"]));
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/transcribe");
    const form = init.body as FormData;
    expect(form.get("language")).toBe("en");
  });

  it("transcribe acepta el idioma español (Traductor)", async () => {
    const fn = mockFetch({ text: "hola" });
    await transcribe(new Blob(["x"]), "es");
    const [, init] = fn.mock.calls[0];
    expect((init.body as FormData).get("language")).toBe("es");
  });

  it("speak envía el idioma en el cuerpo del TTS", async () => {
    vi.stubGlobal("Audio", FakeAudio);
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:fake");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const fn = mockFetch({});

    await speak("¿Dónde está el hotel?", "u1", "es");

    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/tts");
    expect(JSON.parse(init.body as string)).toEqual({
      text: "¿Dónde está el hotel?",
      language: "es",
    });
  });

  it("speak usa inglés por defecto y no añade query", async () => {
    vi.stubGlobal("Audio", FakeAudio);
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:fake");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const fn = mockFetch({});

    await speak("Hello");

    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/tts");
    expect(JSON.parse(init.body as string)).toEqual({
      text: "Hello",
      language: "en",
    });
  });
});

describe("api/voz · V3.72 (RD-04) voz declarada y degradación", () => {
  beforeEach(() => {
    vi.stubGlobal("Audio", FakeAudio);
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:fake");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("devuelve la voz realmente usada y sin degradación", async () => {
    mockTtsResponse({
      "X-TTS-Voice": "es_ES-davefx-medium",
      "X-TTS-Degraded": "0",
    });

    await expect(speak("hola", null, "es")).resolves.toEqual({
      voice: "es_ES-davefx-medium",
      degraded: false,
    });
  });

  it("marca la degradación cuando el backend sirvió otro idioma", async () => {
    mockTtsResponse({
      "X-TTS-Voice": "en_US-hfc_female-medium",
      "X-TTS-Degraded": "1",
    });

    await expect(speak("hola", null, "es")).resolves.toEqual({
      voice: "en_US-hfc_female-medium",
      degraded: true,
    });
  });

  it("sin cabeceras no inventa degradación (fail-open)", async () => {
    mockTtsResponse({});

    await expect(speak("hello")).resolves.toEqual({
      voice: "",
      degraded: false,
    });
  });

  it("`AbortController`: la petición se aborta si el backend no responde", async () => {
    vi.useFakeTimers();
    // El `fetch` real rechaza al abortar el signal; el mock lo imita para
    // comprobar que `speak` **pasa** el signal (hoy no lo hacía: `withTimeout`
    // no abortaba la petición y el botón quedaba "sonando" para siempre).
    const fn = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );
    vi.stubGlobal("fetch", fn);

    const pending = speak("hello", null, "en", { timeoutMs: 5_000 });
    const assertion = expect(pending).rejects.toThrow(/Timeout \(TTS\)/);
    await vi.advanceTimersByTimeAsync(5_001);
    await assertion;

    expect(fn.mock.calls[0][1]?.signal).toBeInstanceOf(AbortSignal);
  });
});
