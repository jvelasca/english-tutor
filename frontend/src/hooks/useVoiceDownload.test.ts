// @vitest-environment jsdom
/**
 * Vitest del consentimiento y la descarga de voces (V3.72, RD-04).
 *
 * Antes de V3.72 el Traductor descargaba la voz española (~60 MB) al montarse,
 * sin avisar ni preguntar. Ahora `ensureVoiceForTts` decide: si la voz está
 * instalada no molesta; si falta, abre **una** petición de consentimiento; y si
 * el catálogo o la descarga fallan, el TTS sigue funcionando (fail-open).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { downloadVoice, getVoices } from "../api/voices";
import { speak } from "../api/voz";
import { clearDegradedVoice, getDegradedVoice } from "./useDegradedVoice";
import {
  confirmVoiceDownload,
  dismissVoiceDownload,
  ensureVoiceForTts,
  getVoiceDownloadRequest,
  resetVoiceSession,
  speakWithVoice,
} from "./useVoiceDownload";

vi.mock("../api/voices", () => ({
  getVoices: vi.fn(),
  downloadVoice: vi.fn(),
}));
vi.mock("../api/voz", () => ({
  speak: vi.fn(),
}));

const getVoicesMock = vi.mocked(getVoices);
const downloadVoiceMock = vi.mocked(downloadVoice);
const speakMock = vi.mocked(speak);

/** Catálogo con inglés instalado y español pendiente de descargar. */
function catalog({ spanishInstalled = false } = {}) {
  return {
    voices: spanishInstalled
      ? [
          { id: "en_US-lessac-medium", name: "Lessac" },
          { id: "es_ES-davefx-medium", name: "DaveFX" },
        ]
      : [{ id: "en_US-lessac-medium", name: "Lessac" }],
    downloadable: [{ id: "es_ES-davefx-medium", name: "DaveFX", size_mb: 63 }],
    default: "en_US-lessac-medium",
    selected: "en_US-lessac-medium",
    defaults: { en: "en_US-lessac-medium", es: "es_ES-davefx-medium" },
  };
}

async function gateUntilAsk(language: "en" | "es" = "es"): Promise<void> {
  void ensureVoiceForTts(language, "u1");
  await vi.waitFor(() => expect(getVoiceDownloadRequest()).not.toBeNull());
}

describe("useVoiceDownload · V3.72 consentimiento de descarga", () => {
  beforeEach(() => {
    resetVoiceSession();
    vi.clearAllMocks();
  });

  afterEach(() => {
    resetVoiceSession();
    clearDegradedVoice();
  });

  it("con la voz instalada no pregunta nada", async () => {
    getVoicesMock.mockResolvedValue(catalog({ spanishInstalled: true }));

    await ensureVoiceForTts("es", "u1");

    expect(getVoiceDownloadRequest()).toBeNull();
    expect(downloadVoiceMock).not.toHaveBeenCalled();
  });

  it("sin voz instalada pide consentimiento y no descarga hasta aceptar", async () => {
    getVoicesMock.mockResolvedValue(catalog());

    await gateUntilAsk();

    expect(downloadVoiceMock).not.toHaveBeenCalled();
    const pending = getVoiceDownloadRequest();
    expect(pending?.status).toBe("ask");
    expect(pending?.voice.id).toBe("es_ES-davefx-medium");

    downloadVoiceMock.mockResolvedValue({ ok: true });
    await confirmVoiceDownload();

    expect(downloadVoiceMock).toHaveBeenCalledWith("es_ES-davefx-medium");
    expect(getVoiceDownloadRequest()).toBeNull();
  });

  it("«ahora no» no descarga y no se vuelve a preguntar en la sesión", async () => {
    getVoicesMock.mockResolvedValue(catalog());

    await gateUntilAsk();
    dismissVoiceDownload();

    // El segundo TTS del mismo idioma ya no pregunta ni consulta el catálogo.
    await ensureVoiceForTts("es", "u1");

    expect(getVoiceDownloadRequest()).toBeNull();
    expect(downloadVoiceMock).not.toHaveBeenCalled();
    expect(getVoicesMock).toHaveBeenCalledTimes(1);
  });

  it("un catálogo caído no bloquea el TTS (fail-open)", async () => {
    getVoicesMock.mockRejectedValue(new Error("sin backend"));

    await expect(ensureVoiceForTts("es", "u1")).resolves.toBeUndefined();

    expect(getVoiceDownloadRequest()).toBeNull();
  });

  it("un fallo de descarga se muestra y no deja la promesa colgada", async () => {
    getVoicesMock.mockResolvedValue(catalog());
    downloadVoiceMock.mockRejectedValue(new Error("sin red"));

    const gate = ensureVoiceForTts("es", "u1");
    await vi.waitFor(() => expect(getVoiceDownloadRequest()).not.toBeNull());
    await confirmVoiceDownload();
    await gate; // no se cuelga: el TTS degradado puede continuar

    const request = getVoiceDownloadRequest();
    expect(request?.status).toBe("error");
    expect(request?.error).toBe("sin red");
  });

  it("dos TTS simultáneos comparten una sola pregunta", async () => {
    getVoicesMock.mockResolvedValue(catalog());

    const first = ensureVoiceForTts("es");
    const second = ensureVoiceForTts("es");
    await vi.waitFor(() => expect(getVoiceDownloadRequest()).not.toBeNull());

    expect(getVoicesMock).toHaveBeenCalledTimes(1);
    dismissVoiceDownload();
    await Promise.all([first, second]);
  });
});

describe("useVoiceDownload · V3.72 speakWithVoice", () => {
  beforeEach(() => {
    resetVoiceSession();
    vi.clearAllMocks();
  });

  afterEach(() => {
    resetVoiceSession();
    clearDegradedVoice();
  });

  it("propaga la degradación declarada por el backend al aviso global", async () => {
    getVoicesMock.mockResolvedValue(catalog({ spanishInstalled: true }));
    speakMock.mockResolvedValue({
      voice: "en_US-lessac-medium",
      degraded: true,
    });

    await speakWithVoice("hola", null, "es");

    expect(getDegradedVoice()).toEqual({
      voice: "en_US-lessac-medium",
      language: "es",
    });
  });

  it("no inventa aviso cuando el backend no declara degradación", async () => {
    getVoicesMock.mockResolvedValue(catalog({ spanishInstalled: true }));
    speakMock.mockResolvedValue({ voice: "es_ES-davefx-medium", degraded: false });

    await speakWithVoice("hola", null, "es");

    expect(getDegradedVoice()).toBeNull();
  });
});
