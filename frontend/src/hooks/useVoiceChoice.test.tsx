// @vitest-environment jsdom
/**
 * Vitest del store de voz A/B (V3.75.5).
 *
 * El alumno pidió oír el mismo ítem con **dos acentos**; aquí se fija el
 * contrato que sostiene eso: la B se sugiere sola con otra locale, la elección
 * persiste en `tts_voice_alt` por el mismo `PUT /api/settings`, cambiar la A
 * reajusta la B, y un catálogo caído **no** deja la app muda (fail-open).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { getVoices } from "../api/voices";
import { getSettings, saveSettings } from "../api/settings";
import {
  ensureVoiceChoice,
  getVoiceChoice,
  refreshVoiceChoice,
  resetVoiceChoice,
  setAltVoice,
  setPrimaryVoice,
  setReplayScope,
  useVoiceChoice,
} from "./useVoiceChoice";

vi.mock("../api/voices", () => ({ getVoices: vi.fn() }));
vi.mock("../api/settings", () => ({
  getSettings: vi.fn(),
  saveSettings: vi.fn(),
}));

const getVoicesMock = vi.mocked(getVoices);
const getSettingsMock = vi.mocked(getSettings);
const saveSettingsMock = vi.mocked(saveSettings);

function catalog() {
  return {
    voices: [
      { id: "en_US-lessac-medium", name: "American English · Lessac" },
      { id: "en_GB-alan-medium", name: "British English · Alan" },
      { id: "es_MX-ald-medium", name: "Español (México) · Ald" },
    ],
    downloadable: [],
    default: "en_US-lessac-medium",
    selected: "en_US-lessac-medium",
    defaults: { en: "en_US-lessac-medium", es: "es_MX-ald-medium" },
  };
}

describe("useVoiceChoice: voz A y voz B (V3.75.5)", () => {
  beforeEach(() => {
    resetVoiceChoice();
    vi.clearAllMocks();
    getVoicesMock.mockResolvedValue(catalog());
    getSettingsMock.mockResolvedValue({ settings: {} });
    saveSettingsMock.mockResolvedValue({ settings: {} });
  });

  afterEach(() => {
    cleanup();
    resetVoiceChoice();
  });

  it("sugiere la voz B de otra locale cuando no hay nada guardado", async () => {
    const { result } = renderHook(() => useVoiceChoice("user-1"));

    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.primary).toBe("en_US-lessac-medium");
    // Misma lengua, otra locale: los dos acentos suenan distintos de verdad.
    expect(result.current.alt).toBe("en_GB-alan-medium");
    // Y se declara como sugerencia, no como elección del alumno.
    expect(result.current.savedAlt).toBe("");
    // Solo se ofrecen voces del idioma de la voz A.
    expect(result.current.voices.map((v) => v.id)).toEqual([
      "en_US-lessac-medium",
      "en_GB-alan-medium",
    ]);
  });

  it("respeta la voz B elegida y la marca como guardada", async () => {
    getSettingsMock.mockResolvedValue({
      settings: { tts_voice_alt: "en_GB-alan-medium" },
    });
    const { result } = renderHook(() => useVoiceChoice("user-1"));

    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.alt).toBe("en_GB-alan-medium");
    expect(result.current.savedAlt).toBe("en_GB-alan-medium");
  });

  it("ignora una voz B que ya no está instalada (cae a la sugerencia)", async () => {
    getSettingsMock.mockResolvedValue({
      settings: { tts_voice_alt: "en_GB-ghost-medium" },
    });
    const { result } = renderHook(() => useVoiceChoice("user-1"));

    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.alt).toBe("en_GB-alan-medium");
    expect(result.current.savedAlt).toBe("");
  });

  it("guardar la voz B la persiste en tts_voice_alt (mismo PUT de settings)", async () => {
    getSettingsMock.mockResolvedValue({
      settings: { tts_voice_alt: "en_GB-alan-medium" },
    });
    renderHook(() => useVoiceChoice("user-1"));
    await waitFor(() => expect(getVoiceChoice().status).toBe("ready"));

    await act(() => setAltVoice("user-1", "en_GB-alan-medium"));

    expect(saveSettingsMock).toHaveBeenCalledWith("user-1", {
      tts_voice_alt: "en_GB-alan-medium",
    });
    expect(getVoiceChoice().savedAlt).toBe("en_GB-alan-medium");
  });

  it("no deja que la voz B sea la misma que la A", async () => {
    renderHook(() => useVoiceChoice("user-1"));
    await waitFor(() => expect(getVoiceChoice().status).toBe("ready"));

    await act(() => setAltVoice("user-1", "en_US-lessac-medium"));

    expect(saveSettingsMock).not.toHaveBeenCalled();
    expect(getVoiceChoice().alt).toBe("en_GB-alan-medium");
  });

  it("cambiar la voz A guarda tts_voice y reajusta la B si era la elegida", async () => {
    getSettingsMock.mockResolvedValue({
      settings: { tts_voice_alt: "en_GB-alan-medium" },
    });
    renderHook(() => useVoiceChoice("user-1"));
    await waitFor(() => expect(getVoiceChoice().status).toBe("ready"));

    await act(() => setPrimaryVoice("user-1", "en_GB-alan-medium"));

    expect(getVoiceChoice().primary).toBe("en_GB-alan-medium");
    // La B elegida era justo la nueva A: se limpia y se vuelve a sugerir.
    expect(getVoiceChoice().alt).toBe("en_US-lessac-medium");
    expect(getVoiceChoice().savedAlt).toBe("");
    expect(saveSettingsMock).toHaveBeenCalledWith("user-1", {
      tts_voice: "en_GB-alan-medium",
      tts_voice_alt: "",
    });
  });

  it("con una sola voz instalada no hay B (la UI no muestra un botón vacío)", async () => {
    getVoicesMock.mockResolvedValue({
      ...catalog(),
      voices: [{ id: "en_US-lessac-medium", name: "Lessac" }],
      selected: "en_US-lessac-medium",
    });
    const { result } = renderHook(() => useVoiceChoice("user-1"));

    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.alt).toBe("");
    expect(result.current.voiceFor("a")).toBe("en_US-lessac-medium");
    expect(result.current.voiceFor("b")).toBe("");
  });

  it("un catálogo caído no deja muda la app (fail-open) y no lanza", async () => {
    getVoicesMock.mockRejectedValue(new Error("offline"));
    await expect(ensureVoiceChoice("user-1")).resolves.toBeUndefined();
    expect(getVoiceChoice().status).toBe("error");
    expect(getVoiceChoice().primary).toBe("");
  });

  it("lee el catálogo una sola vez aunque haya varios altavoces en pantalla", async () => {
    const a = renderHook(() => useVoiceChoice("user-1"));
    const b = renderHook(() => useVoiceChoice("user-1"));
    await waitFor(() => expect(a.result.current.status).toBe("ready"));
    await act(() => ensureVoiceChoice("user-1"));
    expect(b.result.current.status).toBe("ready");
    expect(getVoicesMock).toHaveBeenCalledTimes(1);
  });

  it("releer tras instalar una voz vuelve a emparejar A/B con el catálogo nuevo", async () => {
    const first = renderHook(() => useVoiceChoice("user-1"));
    await waitFor(() => expect(first.result.current.status).toBe("ready"));
    expect(getVoiceChoice().alt).toBe("en_GB-alan-medium");

    // Instalación nueva (Configuración → Voces): ahora también hay una irlandesa,
    // que es la primera alternativa de otra locale para la voz A americana.
    getVoicesMock.mockResolvedValue({
      ...catalog(),
      voices: [
        { id: "en_US-lessac-medium", name: "American English · Lessac" },
        { id: "en_IE-orla-medium", name: "Irish English · Orla" },
        { id: "en_GB-alan-medium", name: "British English · Alan" },
      ],
    });
    await act(() => refreshVoiceChoice("user-1"));

    expect(getVoicesMock).toHaveBeenCalledTimes(2);
    expect(getVoiceChoice().alt).toBe("en_IE-orla-medium");
  });

  it("cambiar de perfil no deja a la vista la voz del anterior", async () => {
    const first = renderHook(() => useVoiceChoice("user-1"));
    await waitFor(() => expect(first.result.current.status).toBe("ready"));
    expect(getVoiceChoice().primary).toBe("en_US-lessac-medium");

    getVoicesMock.mockResolvedValue({
      ...catalog(),
      selected: "es_MX-ald-medium",
    });
    getSettingsMock.mockResolvedValue({ settings: { tts_voice_alt: "" } });
    await act(() => ensureVoiceChoice("user-2"));

    expect(getVoiceChoice().primary).toBe("es_MX-ald-medium");
    // Solo el idioma de la voz A: la voz inglesa del perfil anterior no se cuela.
    expect(getVoiceChoice().voices.map((v) => v.id)).toEqual(["es_MX-ald-medium"]);
    expect(getVoiceChoice().alt).toBe("");
  });
});

describe("useVoiceChoice: alcance de la repetición (V3.75.6)", () => {
  beforeEach(() => {
    resetVoiceChoice();
    vi.clearAllMocks();
    getVoicesMock.mockResolvedValue(catalog());
    getSettingsMock.mockResolvedValue({ settings: {} });
    saveSettingsMock.mockResolvedValue({ settings: {} });
  });

  afterEach(() => {
    cleanup();
    resetVoiceChoice();
  });

  it("sin preferencia guardada lee el ítem completo (el defecto nuevo)", async () => {
    const { result } = renderHook(() => useVoiceChoice("user-1"));

    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.replayScope).toBe("item");
  });

  it("lee `replay_scope` del perfil, también tras un refresh", async () => {
    getSettingsMock.mockResolvedValue({ settings: { replay_scope: "correct" } });
    const { result } = renderHook(() => useVoiceChoice("user-1"));

    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.replayScope).toBe("correct");

    getSettingsMock.mockResolvedValue({ settings: { replay_scope: "withOptions" } });
    await act(() => refreshVoiceChoice("user-1"));
    expect(getVoiceChoice().replayScope).toBe("withOptions");
  });

  it("el valor histórico `all` se conserva como «ítem + opciones»", async () => {
    // Un perfil que eligió la lectura larga cuando era la única opción no la pierde
    // al cambiar el juego de valores.
    getSettingsMock.mockResolvedValue({ settings: { replay_scope: "all" } });
    renderHook(() => useVoiceChoice("user-1"));

    await waitFor(() => expect(getVoiceChoice().status).toBe("ready"));
    expect(getVoiceChoice().replayScope).toBe("withOptions");
  });

  it("un valor desconocido cae a `item` (una preferencia rota no cambia la lectura)", async () => {
    getSettingsMock.mockResolvedValue({ settings: { replay_scope: "??" } });
    const { result } = renderHook(() => useVoiceChoice("user-1"));

    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.replayScope).toBe("item");
  });

  it("cambiarla la persiste en `replay_scope` (mismo PUT de settings)", async () => {
    renderHook(() => useVoiceChoice("user-1"));
    await waitFor(() => expect(getVoiceChoice().status).toBe("ready"));

    await act(() => setReplayScope("user-1", "correct"));

    expect(getVoiceChoice().replayScope).toBe("correct");
    expect(saveSettingsMock).toHaveBeenCalledWith("user-1", {
      replay_scope: "correct",
    });
  });

  it("cambiarla dos veces al mismo valor no escribe dos veces", async () => {
    getSettingsMock.mockResolvedValue({ settings: { replay_scope: "correct" } });
    renderHook(() => useVoiceChoice("user-1"));
    await waitFor(() => expect(getVoiceChoice().status).toBe("ready"));

    await act(() => setReplayScope("user-1", "correct"));

    expect(saveSettingsMock).not.toHaveBeenCalled();
  });

  it("sin perfil la preferencia vive solo en memoria (no hay dónde guardarla)", async () => {
    await act(() => setReplayScope(null, "correct"));

    expect(getVoiceChoice().replayScope).toBe("correct");
    expect(saveSettingsMock).not.toHaveBeenCalled();
  });
});
