// @vitest-environment jsdom
/**
 * Vitest de `ListenButton` en el flujo de voz de V3.72 (RD-04).
 *
 * El altavoz es el punto por el que pasa la mayoría del TTS de la app: aquí se
 * comprueba que (a) no reproduce en un idioma sin voz instalada hasta que el
 * alumno acepta la descarga y (b) si el backend acaba usando otra voz, el aviso
 * de degradación llega a la pantalla.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { downloadVoice, getVoices } from "../api/voices";
import { speak } from "../api/voz";
import { I18nProvider } from "../hooks/useI18n";
import { resetVoiceSession } from "../hooks/useVoiceDownload";
import { DegradedVoiceNotice } from "./DegradedVoiceNotice";
import { ListenButton } from "./ListenButton";
import { VoiceDownloadDialog } from "./VoiceDownloadDialog";

vi.mock("../api/voz", () => ({
  speak: vi.fn(),
}));
vi.mock("../api/voices", () => ({
  getVoices: vi.fn(),
  downloadVoice: vi.fn(),
}));

const getVoicesMock = vi.mocked(getVoices);
const downloadVoiceMock = vi.mocked(downloadVoice);
const speakMock = vi.mocked(speak);

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

function renderSpeaker() {
  return render(
    <I18nProvider lang="es" setLang={() => {}}>
      <ListenButton text="¿Dónde está el hotel?" label="Escuchar" language="es" />
      <DegradedVoiceNotice />
      <VoiceDownloadDialog />
    </I18nProvider>,
  );
}

describe("ListenButton · V3.72 consentimiento y degradación", () => {
  beforeEach(() => {
    resetVoiceSession();
    vi.clearAllMocks();
    speakMock.mockResolvedValue({ voice: "es_ES-davefx-medium", degraded: false });
  });

  afterEach(() => {
    cleanup();
    resetVoiceSession();
  });

  it("no reproduce hasta que el alumno acepta descargar la voz que falta", async () => {
    getVoicesMock.mockResolvedValue(catalog());
    renderSpeaker();

    fireEvent.click(screen.getByRole("button", { name: "Escuchar" }));

    await waitFor(() =>
      expect(screen.getByTestId("voice-download-dialog")).toBeTruthy(),
    );
    expect(speakMock).not.toHaveBeenCalled();

    downloadVoiceMock.mockResolvedValue({ ok: true });
    fireEvent.click(screen.getByRole("button", { name: "Descargar y escuchar" }));

    await waitFor(() =>
      expect(speakMock).toHaveBeenCalledWith(
        "¿Dónde está el hotel?",
        undefined,
        "es",
      ),
    );
  });

  it("si el usuario dice «ahora no», reproduce degradado y lo avisa", async () => {
    getVoicesMock.mockResolvedValue(catalog());
    speakMock.mockResolvedValue({
      voice: "en_US-lessac-medium",
      degraded: true,
    });
    renderSpeaker();

    fireEvent.click(screen.getByRole("button", { name: "Escuchar" }));
    await waitFor(() =>
      expect(screen.getByTestId("voice-download-dialog")).toBeTruthy(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Ahora no" }));

    await waitFor(() =>
      expect(screen.getByTestId("degraded-voice-notice")).toBeTruthy(),
    );
    expect(downloadVoiceMock).not.toHaveBeenCalled();
  });

  it("con la voz instalada reproduce sin preguntar nada", async () => {
    getVoicesMock.mockResolvedValue(catalog({ spanishInstalled: true }));
    renderSpeaker();

    fireEvent.click(screen.getByRole("button", { name: "Escuchar" }));

    await waitFor(() => expect(speakMock).toHaveBeenCalled());
    expect(screen.queryByTestId("voice-download-dialog")).toBeNull();
    expect(downloadVoiceMock).not.toHaveBeenCalled();
  });
});
