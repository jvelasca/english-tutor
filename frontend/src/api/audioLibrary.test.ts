import { afterEach, describe, expect, it, vi } from "vitest";
import {
  deleteAudioLibraryEntry,
  getAdminPin,
  getAudioLibraryAudit,
  getAudioLibrarySlots,
  getAudioLibraryStatus,
  setAdminPin,
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

  it("getAudioLibraryStatus llama al endpoint de estado", async () => {
    const fn = mockFetch(true, { admin_required: false, version: "1.2.0" });
    await getAudioLibraryStatus();
    expect(fn.mock.calls[0][0]).toBe("/api/audio-library/status");
  });

  it("getAudioLibraryAudit envía el PIN de admin cuando está definido", async () => {
    const storage = {
      getItem: () => "1234",
      setItem: () => {},
      removeItem: () => {},
    };
    vi.stubGlobal("sessionStorage", storage);
    vi.stubGlobal("localStorage", { removeItem: () => {} });
    const fn = mockFetch(true, { ok: true, total_items: 0 });
    await getAudioLibraryAudit();
    const [, init] = fn.mock.calls[0];
    expect(init.headers["X-Admin-Pin"]).toBe("1234");
  });

  it("deleteAudioLibraryEntry envía el PIN de admin cuando está definido", async () => {
    const storage = {
      getItem: () => "1234",
      setItem: () => {},
      removeItem: () => {},
    };
    vi.stubGlobal("sessionStorage", storage);
    vi.stubGlobal("localStorage", { removeItem: () => {} });
    const fn = mockFetch(true, { removed: true, audio_id: "audio-l15" });
    await deleteAudioLibraryEntry("audio-l15");
    const [, init] = fn.mock.calls[0];
    expect(init.headers["X-Admin-Pin"]).toBe("1234");
  });

  // V3.73.x: el PIN es una credencial y no debe quedar en `localStorage`
  // (permanente, en claro y compartido por todos los perfiles del navegador).
  it("getAdminPin lee de la sesión y borra la copia heredada de localStorage", () => {
    const local = { getItem: vi.fn(), setItem: vi.fn(), removeItem: vi.fn() };
    const session = {
      getItem: vi.fn(() => "1234"),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };
    vi.stubGlobal("localStorage", local);
    vi.stubGlobal("sessionStorage", session);

    expect(getAdminPin()).toBe("1234");
    expect(session.getItem).toHaveBeenCalledWith("adminPin");
    expect(local.removeItem).toHaveBeenCalledWith("adminPin");
    expect(local.getItem).not.toHaveBeenCalled();
  });

  it("setAdminPin escribe en la sesión y nunca en localStorage", () => {
    const local = { removeItem: vi.fn() };
    const session = { setItem: vi.fn(), removeItem: vi.fn() };
    vi.stubGlobal("localStorage", local);
    vi.stubGlobal("sessionStorage", session);

    setAdminPin("1234");
    expect(session.setItem).toHaveBeenCalledWith("adminPin", "1234");
    expect(local.removeItem).toHaveBeenCalledWith("adminPin");

    setAdminPin("");
    expect(session.removeItem).toHaveBeenCalledWith("adminPin");
  });
});
