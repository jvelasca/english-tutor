// @vitest-environment jsdom
/**
 * Vitest de `ItemReplayButton` (V3.75.5 / V3.75.6).
 *
 * El altavoz de después de responder ya no relee solo el enunciado: compone la
 * lectura —texto del ítem, pregunta, opciones y respuesta correcta— y ofrece un
 * botón por acento. Aquí se fija **qué texto viaja al TTS en cada una de las tres
 * lecturas del perfil**, que el botón B pide la segunda voz, que el STOP corta la
 * locución en curso y que con una sola voz instalada no aparece un botón B que no
 * podría sonar.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { getVoices } from "../api/voices";
import { getSettings } from "../api/settings";
import { speak, stopSpeaking } from "../api/voz";
import { I18nProvider } from "../hooks/useI18n";
import { resetVoiceChoice } from "../hooks/useVoiceChoice";
import { resetVoiceSession } from "../hooks/useVoiceDownload";
import { ItemReplayButton } from "./ItemReplayButton";

vi.mock("../api/voz", () => ({ speak: vi.fn(), stopSpeaking: vi.fn() }));
vi.mock("../api/voices", () => ({ getVoices: vi.fn(), downloadVoice: vi.fn() }));
vi.mock("../api/settings", () => ({
  getSettings: vi.fn(),
  saveSettings: vi.fn(),
}));

const getVoicesMock = vi.mocked(getVoices);
const getSettingsMock = vi.mocked(getSettings);
const speakMock = vi.mocked(speak);

function catalog(ids: string[]) {
  return {
    voices: ids.map((id) => ({ id, name: id })),
    downloadable: [],
    default: ids[0],
    selected: ids[0],
    defaults: { en: ids[0] },
  };
}

function renderReplay() {
  return render(
    <I18nProvider lang="es" setLang={() => {}}>
      <ItemReplayButton
        prompt="Where is the station?"
        script="The station is next to the bank."
        options={["Next to the bank", "Behind the hotel"]}
        correctIndex={0}
        userId="user-1"
      />
    </I18nProvider>,
  );
}

describe("ItemReplayButton · V3.75.5", () => {
  beforeEach(() => {
    resetVoiceChoice();
    resetVoiceSession();
    vi.clearAllMocks();
    getSettingsMock.mockResolvedValue({ settings: {} });
    speakMock.mockResolvedValue({ voice: "en_US-lessac-medium", degraded: false });
  });

  afterEach(() => {
    cleanup();
    resetVoiceChoice();
    resetVoiceSession();
  });

  it("por defecto lee el texto del ítem, la pregunta y la respuesta correcta", async () => {
    getVoicesMock.mockResolvedValue(
      catalog(["en_US-lessac-medium", "en_GB-alan-medium"]),
    );
    renderReplay();

    const buttonA = await screen.findByRole("button", { name: /accent A|acento A/i });
    fireEvent.click(buttonA);

    await waitFor(() =>
      expect(speakMock).toHaveBeenCalledWith(
        "The station is next to the bank. Where is the station?. Next to the bank.",
        "user-1",
        "en",
        { voice: "en_US-lessac-medium" },
      ),
    );
  });

  it("con `replay_scope: withOptions` enumera las opciones antes de la clave", async () => {
    getSettingsMock.mockResolvedValue({ settings: { replay_scope: "withOptions" } });
    getVoicesMock.mockResolvedValue(
      catalog(["en_US-lessac-medium", "en_GB-alan-medium"]),
    );
    renderReplay();

    const buttonA = await screen.findByRole("button", { name: /acento A/i });
    fireEvent.click(buttonA);

    await waitFor(() =>
      expect(speakMock).toHaveBeenCalledWith(
        "The station is next to the bank. Where is the station?. " +
          "A: Next to the bank. B: Behind the hotel. A: Next to the bank.",
        "user-1",
        "en",
        { voice: "en_US-lessac-medium" },
      ),
    );
  });

  it("el acento B pide la segunda voz y la misma lectura", async () => {
    getVoicesMock.mockResolvedValue(
      catalog(["en_US-lessac-medium", "en_GB-alan-medium"]),
    );
    renderReplay();

    const buttonB = await screen.findByRole("button", { name: /acento B/i });
    fireEvent.click(buttonB);

    await waitFor(() =>
      expect(speakMock).toHaveBeenCalledWith(
        "The station is next to the bank. Where is the station?. Next to the bank.",
        "user-1",
        "en",
        { voice: "en_GB-alan-medium" },
      ),
    );
  });

  it("con una sola voz instalada no hay botón B", async () => {
    getVoicesMock.mockResolvedValue(catalog(["en_US-lessac-medium"]));
    renderReplay();

    await screen.findByRole("button", { name: /acento A/i });
    expect(screen.queryByRole("button", { name: /acento B/i })).toBeNull();
  });

  it("sin opciones no promete opciones: etiqueta de frase", async () => {
    getVoicesMock.mockResolvedValue(
      catalog(["en_US-lessac-medium", "en_GB-alan-medium"]),
    );
    render(
      <I18nProvider lang="es" setLang={() => {}}>
        <ItemReplayButton prompt="coffee" userId="user-1" />
      </I18nProvider>,
    );

    const buttonB = await screen.findByRole("button", {
      name: /Repetir con el acento B/,
    });
    // Una palabra suelta no es «un ítem con opciones»: el grupo se anuncia como
    // repetición de frase, no como repetición de ítem.
    expect(screen.getByRole("group", { name: /Volver a escuchar/i })).toBeTruthy();
    fireEvent.click(buttonB);

    await waitFor(() =>
      expect(speakMock).toHaveBeenCalledWith("coffee.", "user-1", "en", {
        voice: "en_GB-alan-medium",
      }),
    );
  });

  it("sin texto no renderiza nada", () => {
    getVoicesMock.mockResolvedValue(catalog(["en_US-lessac-medium"]));
    const { container } = render(
      <I18nProvider lang="es" setLang={() => {}}>
        <ItemReplayButton prompt="" options={[]} userId="user-1" />
      </I18nProvider>,
    );
    expect(container.querySelector("button")).toBeNull();
  });
});

describe("ItemReplayButton · V3.75.6 STOP y lectura corta", () => {
  beforeEach(() => {
    resetVoiceChoice();
    resetVoiceSession();
    vi.clearAllMocks();
    getSettingsMock.mockResolvedValue({ settings: {} });
    getVoicesMock.mockResolvedValue(
      catalog(["en_US-lessac-medium", "en_GB-alan-medium"]),
    );
  });

  afterEach(() => {
    cleanup();
    resetVoiceChoice();
    resetVoiceSession();
  });

  it("mientras suena el ítem ofrece STOP y al pulsarlo corta la locución", async () => {
    // Una síntesis que no termina sola: el estado «sonando» se puede observar.
    let release: (() => void) | undefined;
    speakMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          release = () => resolve({ voice: "", degraded: false });
        }),
    );
    renderReplay();

    const buttonA = await screen.findByRole("button", { name: /acento A/i });
    fireEvent.click(buttonA);
    const stop = await screen.findByRole("button", { name: /Parar la lectura/i });

    fireEvent.click(stop);
    expect(vi.mocked(stopSpeaking)).toHaveBeenCalledTimes(1);

    // Con la locución cortada, el STOP desaparece (ya no hay nada que parar).
    await act(async () => {
      release?.();
      await Promise.resolve();
    });
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /Parar la lectura/i })).toBeNull(),
    );
  });

  it("sin locución en curso no hay STOP", async () => {
    speakMock.mockResolvedValue({ voice: "", degraded: false });
    renderReplay();

    await screen.findByRole("button", { name: /acento A/i });
    expect(screen.queryByRole("button", { name: /Parar la lectura/i })).toBeNull();
  });

  it("con `replay_scope: correct` lee solo la pregunta y la respuesta correcta", async () => {
    getSettingsMock.mockResolvedValue({ settings: { replay_scope: "correct" } });
    speakMock.mockResolvedValue({ voice: "", degraded: false });
    renderReplay();

    const buttonA = await screen.findByRole("button", { name: /acento A/i });
    fireEvent.click(buttonA);

    await waitFor(() =>
      expect(speakMock).toHaveBeenCalledWith(
        // Ni el texto del ítem ni las opciones: la letra no situaría nada.
        "Where is the station?. Next to the bank.",
        "user-1",
        "en",
        { voice: "en_US-lessac-medium" },
      ),
    );
  });

  it("el valor histórico `all` sigue leyendo el ítem con las opciones", async () => {
    getSettingsMock.mockResolvedValue({ settings: { replay_scope: "all" } });
    speakMock.mockResolvedValue({ voice: "", degraded: false });
    renderReplay();

    const buttonA = await screen.findByRole("button", { name: /acento A/i });
    fireEvent.click(buttonA);

    await waitFor(() =>
      expect(speakMock).toHaveBeenCalledWith(
        expect.stringContaining("A: Next to the bank. B: Behind the hotel."),
        "user-1",
        "en",
        { voice: "en_US-lessac-medium" },
      ),
    );
  });
});
