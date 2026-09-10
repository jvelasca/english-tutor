// @vitest-environment jsdom
/**
 * Vitest de `TranslatorScreen` (V3.39, Fase 2): traductor de viaje ES↔EN.
 *
 * Es una utilidad AUXILIAR: bidireccional, por voz o texto, con historial
 * reciente persistido en `localStorage`. Se mockean la API de traducción, la de
 * voz (para el altavoz) y el botón de micrófono (MediaRecorder no existe en
 * jsdom) para verificar el cableado de idioma y el auto-traducido del dictado.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { translateText } from "../../api/translate";
import { speak } from "../../api/voz";
import { I18nProvider } from "../../hooks/useI18n";
import { HISTORY_STORAGE_KEY, TranslatorScreen } from "./TranslatorScreen";

vi.mock("../../api/translate", () => ({
  translateText: vi.fn(),
}));
vi.mock("../../api/voz", () => ({
  speak: vi.fn(),
}));
// El micrófono real usa MediaRecorder (no disponible en jsdom): se sustituye por
// un botón que entrega el texto dictado y expone el idioma configurado.
const micLanguages: string[] = [];
vi.mock("../../components/MicButton", () => ({
  MicButton: ({
    onTranscribed,
    language,
  }: {
    onTranscribed: (text: string) => void;
    language?: string;
  }) => {
    micLanguages.push(language ?? "en");
    return (
      <button
        type="button"
        onClick={() => onTranscribed("¿Dónde está el hotel?")}
      >
        dictate
      </button>
    );
  },
}));

const translateMock = vi.mocked(translateText);
const speakMock = vi.mocked(speak);

function renderScreen(userId: string | null = "u1") {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <TranslatorScreen userId={userId} />
    </I18nProvider>,
  );
}

function translateButton() {
  return screen.getByRole("button", { name: "Translate" });
}

function textarea() {
  return screen.getByLabelText("Phrase to translate") as HTMLTextAreaElement;
}

/** El resultado vive en el panel de salida (el historial repite el texto). */
function output() {
  return within(screen.getByTestId("translator-output"));
}

/** La frase en la lista de recientes. */
function history() {
  return within(screen.getByTestId("translator-history"));
}

describe("TranslatorScreen · V3.39 traductor de viaje", () => {
  beforeEach(() => {
    window.localStorage.clear();
    micLanguages.length = 0;
    translateMock.mockReset();
    speakMock.mockReset();
    translateMock.mockResolvedValue("Where is the hotel?");
    speakMock.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("arranca en Español → Inglés (el caso del viajero)", () => {
    renderScreen();
    expect(
      screen
        .getByRole("button", { name: "Spanish → English" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    expect(textarea().getAttribute("lang")).toBe("es");
    // Placeholder propio de la dirección ES→EN (ejemplo en español).
    expect(textarea().getAttribute("placeholder")).toContain(
      "¿Dónde está el hotel?",
    );
  });

  it("traduce por texto con la dirección activa y muestra el resultado", async () => {
    renderScreen();
    fireEvent.change(textarea(), {
      target: { value: "¿Dónde está el hotel?" },
    });
    fireEvent.click(translateButton());

    await waitFor(() =>
      expect(output().getByText("Where is the hotel?")).toBeTruthy(),
    );
    expect(translateMock).toHaveBeenCalledWith("¿Dónde está el hotel?", "es-en");
  });

  it("invertir la dirección cambia el idioma de entrada y limpia el resultado", async () => {
    renderScreen();
    fireEvent.change(textarea(), {
      target: { value: "¿Dónde está el hotel?" },
    });
    fireEvent.click(translateButton());
    await waitFor(() =>
      expect(output().getByText("Where is the hotel?")).toBeTruthy(),
    );

    fireEvent.click(screen.getByRole("button", { name: "English → Spanish" }));

    expect(textarea().getAttribute("lang")).toBe("en");
    // El panel de salida se limpia (el historial conserva la frase anterior).
    expect(output().queryByText("Where is the hotel?")).toBeNull();
    expect(
      screen
        .getByRole("button", { name: "English → Spanish" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("el botón ⇄ intercambia sentido y textos", async () => {
    renderScreen();
    fireEvent.change(textarea(), {
      target: { value: "¿Dónde está el hotel?" },
    });
    fireEvent.click(translateButton());
    await waitFor(() =>
      expect(output().getByText("Where is the hotel?")).toBeTruthy(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Swap direction" }));

    // El sentido se invierte y los textos también: la traducción pasa al origen
    // y el original al panel de salida.
    expect(textarea().value).toBe("Where is the hotel?");
    expect(output().getByText("¿Dónde está el hotel?")).toBeTruthy();
    expect(
      screen
        .getByRole("button", { name: "English → Spanish" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("muestra un error y no deja resultado si el modelo no está disponible", async () => {
    translateMock.mockRejectedValue(new Error("HTTP 502"));
    renderScreen();
    fireEvent.change(textarea(), { target: { value: "Hola" } });
    fireEvent.click(translateButton());

    await waitFor(() =>
      expect(output().getByRole("alert").textContent).toContain(
        "Translation unavailable.",
      ),
    );
    expect(output().queryByText("Where is the hotel?")).toBeNull();
  });

  it("el dictado usa el idioma de origen y auto-traduce lo transcrito", async () => {
    renderScreen();
    expect(micLanguages).toContain("es");

    fireEvent.click(screen.getByRole("button", { name: "dictate" }));

    await waitFor(() =>
      expect(translateMock).toHaveBeenCalledWith(
        "¿Dónde está el hotel?",
        "es-en",
      ),
    );
    await waitFor(() =>
      expect(output().getByText("Where is the hotel?")).toBeTruthy(),
    );
  });

  it("guarda el historial reciente en localStorage", async () => {
    renderScreen();
    fireEvent.change(textarea(), { target: { value: "Hola" } });
    fireEvent.click(translateButton());
    await waitFor(() =>
      expect(output().getByText("Where is the hotel?")).toBeTruthy(),
    );

    await waitFor(() => {
      const items = JSON.parse(
        window.localStorage.getItem(HISTORY_STORAGE_KEY) as string,
      ) as { source: string }[];
      expect(items[0].source).toBe("Hola");
    });
    // La frase aparece también en la lista de recientes.
    expect(history().getByText("Where is the hotel?")).toBeTruthy();
  });

  it("reutiliza una frase del historial", async () => {
    window.localStorage.setItem(
      HISTORY_STORAGE_KEY,
      JSON.stringify([
        {
          id: "h1",
          direction: "en-es",
          source: "Where is the hotel?",
          target: "¿Dónde está el hotel?",
        },
      ]),
    );
    renderScreen();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Reuse “Where is the hotel?”",
      }),
    );

    expect(textarea().value).toBe("Where is the hotel?");
    expect(
      screen
        .getByRole("button", { name: "English → Spanish" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    expect(output().getByText("¿Dónde está el hotel?")).toBeTruthy();
  });

  it("permite borrar el historial", async () => {
    window.localStorage.setItem(
      HISTORY_STORAGE_KEY,
      JSON.stringify([
        { id: "h1", direction: "es-en", source: "Hola", target: "Hello" },
      ]),
    );
    renderScreen();

    fireEvent.click(screen.getByRole("button", { name: "Clear" }));

    expect(screen.queryByTestId("translator-history")).toBeNull();
    await waitFor(() =>
      expect(window.localStorage.getItem(HISTORY_STORAGE_KEY)).toBe("[]"),
    );
  });

  it("funciona sin perfil (utilidad auxiliar)", () => {
    renderScreen(null);
    expect(screen.getByText("Travel translator")).toBeTruthy();
    expect(textarea()).toBeTruthy();
  });
});
