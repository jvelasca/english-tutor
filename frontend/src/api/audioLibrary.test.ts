import { afterEach, describe, expect, it, vi } from "vitest";
import {
  deleteAudioLibraryEntry,
  getAudioLibrarySlots,
  uploadAudioLibraryWav,
} from "./audioLibrary";

function mockFetch(ok: boolean, data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("audioLibrary api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getAudioLibrarySlots llama al endpoint de slots", async () => {
    const fn = mockFetch(true, { slots: [] });
    await getAudioLibrarySlots();
    expect(fn.mock.calls[0][0]).toBe("/api/audio-library/slots");
  });

  it("uploadAudioLibraryWav envía archivo y metadatos como FormData", async () => {
    const fn = mockFetch(true, { audio_id: "audio-l15" });
    const file = new Blob(["wav-bytes"], { type: "audio/wav" }) as File;

    await uploadAudioLibraryWav(file, {
      audio_id: "audio-l15",
      cefr: "B1",
      speech_rate: 140,
      noise_level: 0,
      transcript: "Hello",
      region: "",
    });

    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/audio-library/upload");
    expect(init.method).toBe("POST");
    const form = init.body as FormData;
    expect(form.get("file")).not.toBeNull();
    expect(form.get("audio_id")).toBe("audio-l15");
    expect(form.get("cefr")).toBe("B1");
    expect(form.get("speech_rate")).toBe("140");
    expect(form.get("transcript")).toBe("Hello");
    // Los valores vacíos se omiten del FormData.
    expect(form.get("region")).toBeNull();
  });

  it("deleteAudioLibraryEntry llama a DELETE con el id", async () => {
    const fn = mockFetch(true, { removed: true, audio_id: "audio-l15" });
    await deleteAudioLibraryEntry("audio-l15");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/audio-library/audio-l15");
    expect(init.method).toBe("DELETE");
  });
});
