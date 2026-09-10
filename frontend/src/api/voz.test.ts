// @vitest-environment jsdom
/**
 * Vitest de la API de voz (V3.39, Fase 2): `transcribe` acepta el idioma del
 * audio y `speak` lo envía al TTS para que el Traductor use voces españolas.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
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
    expect(url).toBe("/api/tts?user_id=u1");
    expect(JSON.parse(init.body as string)).toEqual({
      text: "¿Dónde está el hotel?",
      language: "es",
    });
  });

  it("speak usa inglés por defecto y sin user_id no añade query", async () => {
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
