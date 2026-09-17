// @vitest-environment jsdom
/**
 * Vitest de `ConversationPanel` (V3.45): panel de un idioma del modo
 * Conversación del Traductor. Verifica estados del botón grande, el par
 * texto/traducción, el botón de repetir audio y la rotación «cara a cara».
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { getVoices } from "../../api/voices";
import { speak } from "../../api/voz";
import { I18nProvider } from "../../hooks/useI18n";
import {
  ConversationPanel,
  type ConversationTurn,
} from "./ConversationPanel";
import type { VoiceTurnController } from "./useVoiceTurn";

vi.mock("../../api/voz", () => ({
  speak: vi.fn(),
}));
// V3.72: el altavoz consulta el catálogo de voces antes de reproducir.
vi.mock("../../api/voices", () => ({
  getVoices: vi.fn(),
  downloadVoice: vi.fn(),
}));

const speakMock = vi.mocked(speak);

function controller(
  overrides: Partial<VoiceTurnController> = {},
): VoiceTurnController {
  return {
    status: "idle",
    level: 0,
    micError: null,
    transcribeError: null,
    noSpeech: false,
    toggle: vi.fn(),
    stop: vi.fn(),
    ...overrides,
  };
}

const TURN: ConversationTurn = {
  id: "t1",
  speaker: "es",
  sourceLang: "es",
  source: "¿Dónde está el hotel?",
  targetLang: "en",
  target: "Where is the hotel?",
};

function renderPanel(
  props: Partial<React.ComponentProps<typeof ConversationPanel>> = {},
) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <ConversationPanel
        label="You · Spanish"
        controller={controller()}
        busy={false}
        disabled={false}
        turn={null}
        userId="u1"
        size="base"
        testId="panel-es"
        {...props}
      />
    </I18nProvider>,
  );
}

describe("ConversationPanel · V3.45", () => {
  beforeEach(() => {
    speakMock.mockReset();
    speakMock.mockResolvedValue({
      voice: "es_ES-davefx-medium",
      degraded: false,
    });
    // Voz inglesa y española instaladas: el flujo de consentimiento no se activa.
    vi.mocked(getVoices).mockResolvedValue({
      voices: [
        { id: "en_US-lessac-medium", name: "Lessac" },
        { id: "es_ES-davefx-medium", name: "DaveFX" },
      ],
      downloadable: [],
      default: "en_US-lessac-medium",
      selected: "en_US-lessac-medium",
      defaults: { en: "en_US-lessac-medium", es: "es_ES-davefx-medium" },
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("en reposo invita a hablar y no muestra texto", () => {
    renderPanel();
    expect(screen.getByText("Tap to speak")).toBeTruthy();
    expect(screen.getByText("Nothing said yet.")).toBeTruthy();
    expect(
      screen.getByTestId("panel-es-mic").getAttribute("aria-label"),
    ).toBe("Tap to speak");
  });

  it("escuchando cambia el estado y el botón para hablar", () => {
    renderPanel({ controller: controller({ status: "listening", level: 40 }) });
    expect(screen.getByText("Listening…")).toBeTruthy();
    expect(
      screen.getByTestId("panel-es-mic").getAttribute("aria-label"),
    ).toBe("Tap to stop");
  });

  it("traduciendo deshabilita el micrófono y avisa", () => {
    renderPanel({ busy: true });
    expect(screen.getByText("Translating…")).toBeTruthy();
    expect(
      (screen.getByTestId("panel-es-mic") as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("con un turno muestra lo dicho, la traducción y permite repetir el audio", async () => {
    renderPanel({ turn: TURN });
    expect(screen.getByText("¿Dónde está el hotel?")).toBeTruthy();
    expect(screen.getByText("Where is the hotel?")).toBeTruthy();

    fireEvent.click(
      screen.getByRole("button", { name: "Play the translation again" }),
    );
    // V3.72: el altavoz pasa antes por el consentimiento/catálogo de voces, así
    // que la llamada al TTS deja de ser síncrona con el clic.
    await waitFor(() =>
      expect(speakMock).toHaveBeenCalledWith("Where is the hotel?", "u1", "en"),
    );
  });

  it("rota el panel en el modo cara a cara", () => {
    const { container } = renderPanel({ rotate: true });
    expect((container.firstChild as HTMLElement).className).toContain(
      "rotate-180",
    );
  });

  it("muestra el error de transcripción", () => {
    renderPanel({
      controller: controller({ status: "error", transcribeError: "HTTP 500" }),
    });
    expect(screen.getByRole("alert").textContent).toContain("HTTP 500");
  });
});
