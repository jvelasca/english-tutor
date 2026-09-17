// @vitest-environment jsdom
/**
 * Vitest del diálogo de consentimiento de descarga de voz (V3.72, RD-04):
 * dice qué voz falta, cuánto ocupa y que se descarga una sola vez; muestra
 * progreso indeterminado (el endpoint es síncrono) y ofrece reintentar si falla.
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
import { I18nProvider } from "../hooks/useI18n";
import {
  confirmVoiceDownload,
  ensureVoiceForTts,
  getVoiceDownloadRequest,
  resetVoiceSession,
} from "../hooks/useVoiceDownload";
import { VoiceDownloadDialog } from "./VoiceDownloadDialog";

vi.mock("../api/voices", () => ({
  getVoices: vi.fn(),
  downloadVoice: vi.fn(),
}));
vi.mock("../api/voz", () => ({
  speak: vi.fn(),
}));

const getVoicesMock = vi.mocked(getVoices);
const downloadVoiceMock = vi.mocked(downloadVoice);

const CATALOG = {
  voices: [{ id: "en_US-lessac-medium", name: "Lessac" }],
  downloadable: [{ id: "es_ES-davefx-medium", name: "DaveFX", size_mb: 63 }],
  default: "en_US-lessac-medium",
  selected: "en_US-lessac-medium",
  defaults: { en: "en_US-lessac-medium", es: "es_ES-davefx-medium" },
};

function renderDialog() {
  return render(
    <I18nProvider lang="es" setLang={() => {}}>
      <VoiceDownloadDialog />
    </I18nProvider>,
  );
}

/** Deja una petición de consentimiento abierta (como haría un TTS sin voz). */
async function openDialog(): Promise<void> {
  getVoicesMock.mockResolvedValue(CATALOG);
  void ensureVoiceForTts("es", "u1");
  await waitFor(() => expect(getVoiceDownloadRequest()).not.toBeNull());
}

describe("VoiceDownloadDialog (V3.72, RD-04)", () => {
  beforeEach(() => {
    resetVoiceSession();
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    resetVoiceSession();
  });

  it("no renderiza nada si no hay descarga pendiente", () => {
    renderDialog();
    expect(screen.queryByTestId("voice-download-dialog")).toBeNull();
  });

  it("avisa del tamaño y descarga solo al aceptar", async () => {
    await openDialog();
    renderDialog();

    const dialog = screen.getByTestId("voice-download-dialog");
    expect(dialog.textContent).toContain("DaveFX");
    expect(dialog.textContent).toContain("63");
    expect(downloadVoiceMock).not.toHaveBeenCalled();

    downloadVoiceMock.mockResolvedValue({ ok: true });
    fireEvent.click(screen.getByRole("button", { name: "Descargar y escuchar" }));

    await waitFor(() =>
      expect(downloadVoiceMock).toHaveBeenCalledWith("es_ES-davefx-medium"),
    );
    expect(screen.queryByTestId("voice-download-dialog")).toBeNull();
  });

  it("«ahora no» cierra sin descargar", async () => {
    await openDialog();
    renderDialog();

    fireEvent.click(screen.getByRole("button", { name: "Ahora no" }));

    expect(screen.queryByTestId("voice-download-dialog")).toBeNull();
    expect(downloadVoiceMock).not.toHaveBeenCalled();
  });

  it("si la descarga falla, explica el error y ofrece reintentar", async () => {
    await openDialog();
    renderDialog();
    downloadVoiceMock.mockRejectedValue(new Error("sin conexión"));

    fireEvent.click(screen.getByRole("button", { name: "Descargar y escuchar" }));

    await waitFor(() =>
      expect(screen.getByTestId("voice-download-dialog").textContent).toContain(
        "sin conexión",
      ),
    );
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeTruthy();

    downloadVoiceMock.mockResolvedValue({ ok: true });
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    await waitFor(() => expect(downloadVoiceMock).toHaveBeenCalledTimes(2));
  });

  it("muestra progreso indeterminado mientras descarga", async () => {
    await openDialog();
    renderDialog();
    let release: (value: { ok: boolean }) => void = () => {};
    downloadVoiceMock.mockImplementation(
      () => new Promise((resolve) => (release = resolve)),
    );

    fireEvent.click(screen.getByRole("button", { name: "Descargar y escuchar" }));

    const status = await screen.findByRole("status");
    expect(status.textContent).toContain("Descargando la voz");
    // Durante la descarga no se puede cerrar por accidente.
    expect(
      screen
        .getByRole("button", { name: "Ahora no" })
        .hasAttribute("disabled"),
    ).toBe(true);

    release({ ok: true });
    await waitFor(() =>
      expect(screen.queryByTestId("voice-download-dialog")).toBeNull(),
    );
  });

  it("acepta la descarga también sin pasar por el diálogo (uso directo)", async () => {
    downloadVoiceMock.mockResolvedValue({ ok: true });
    await confirmVoiceDownload();
    expect(downloadVoiceMock).not.toHaveBeenCalled();
  });
});
