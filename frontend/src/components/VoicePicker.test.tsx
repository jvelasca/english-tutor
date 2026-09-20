// @vitest-environment jsdom
/**
 * Vitest de `VoicePicker` (V3.75.5).
 *
 * El «...» de la tarjeta de audio pasó de **mostrar** la voz a **configurarla**.
 * Aquí se fija lo que eso significa: la fila A escribe `tts_voice`, la fila B
 * escribe `tts_voice_alt` (y nunca ofrece la misma voz que la A), los chips de
 * prueba delegan en el llamador, y una sola voz instalada se explica en vez de
 * mostrar una fila B vacía.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { getVoices } from "../api/voices";
import { getSettings, saveSettings } from "../api/settings";
import { I18nProvider } from "../hooks/useI18n";
import { resetVoiceChoice } from "../hooks/useVoiceChoice";
import { VoicePicker } from "./VoicePicker";

vi.mock("../api/voices", () => ({ getVoices: vi.fn() }));
vi.mock("../api/settings", () => ({
  getSettings: vi.fn(),
  saveSettings: vi.fn(),
}));

const getVoicesMock = vi.mocked(getVoices);
const getSettingsMock = vi.mocked(getSettings);
const saveSettingsMock = vi.mocked(saveSettings);

function catalog(voices: { id: string; name: string }[]) {
  return {
    voices,
    downloadable: [],
    default: voices[0]?.id ?? "",
    selected: voices[0]?.id ?? "",
    defaults: { en: voices[0]?.id ?? "" },
  };
}

const TWO_VOICES = [
  { id: "en_US-lessac-medium", name: "American English · Lessac" },
  { id: "en_GB-alan-medium", name: "British English · Alan" },
];

function renderPicker(onPreview?: () => Promise<void>) {
  return render(
    <I18nProvider lang="es" setLang={() => {}}>
      <VoicePicker userId="user-1" onPreview={onPreview} />
    </I18nProvider>,
  );
}

describe("VoicePicker · V3.75.5", () => {
  beforeEach(() => {
    resetVoiceChoice();
    vi.clearAllMocks();
    getSettingsMock.mockResolvedValue({ settings: {} });
    saveSettingsMock.mockResolvedValue({ settings: {} });
  });

  afterEach(() => {
    cleanup();
    resetVoiceChoice();
  });

  it("muestra las dos filas con las voces instaladas y su acento", async () => {
    getVoicesMock.mockResolvedValue(catalog(TWO_VOICES));
    renderPicker();

    expect(await screen.findByText("Voz A — tu perfil")).toBeTruthy();
    expect(screen.getByText("Voz B — segundo acento")).toBeTruthy();
    // El acento se lee con palabras, no con el id técnico (aparece en las dos filas).
    expect(screen.getAllByText("británica").length).toBeGreaterThan(0);
    expect(screen.getByText("americana")).toBeTruthy();
  });

  it("elegir la voz B la guarda en tts_voice_alt", async () => {
    getVoicesMock.mockResolvedValue(catalog(TWO_VOICES));
    renderPicker();

    const rowB = await screen.findByRole("radiogroup", {
      name: "Voz B — segundo acento",
    });
    fireEvent.click(within(rowB).getByRole("radio", { name: /Alan/ }));

    await waitFor(() =>
      expect(saveSettingsMock).toHaveBeenCalledWith("user-1", {
        tts_voice_alt: "en_GB-alan-medium",
      }),
    );
  });

  it("no ofrece la voz A como voz B (dos acentos, no el mismo dos veces)", async () => {
    getVoicesMock.mockResolvedValue(catalog(TWO_VOICES));
    renderPicker();

    const rowA = await screen.findByRole("radiogroup", {
      name: "Voz A — tu perfil",
    });
    const rowB = screen.getByRole("radiogroup", { name: "Voz B — segundo acento" });
    const options = [
      ...within(rowA).getAllByRole("radio"),
      ...within(rowB).getAllByRole("radio"),
    ];
    // Dos filas × dos voces menos la A repetida: 3 opciones en total.
    expect(options).toHaveLength(3);
    const names = options.map((option) => option.textContent ?? "");
    expect(names.filter((name) => name.includes("Lessac"))).toHaveLength(1);
  });

  it("los chips de prueba delegan en el llamador con el acento pedido", async () => {
    getVoicesMock.mockResolvedValue(catalog(TWO_VOICES));
    const preview = vi.fn().mockResolvedValue(undefined);
    renderPicker(preview);

    fireEvent.click(await screen.findByRole("button", { name: "Probar B" }));

    await waitFor(() => expect(preview).toHaveBeenCalledWith("b"));
  });

  it("con una sola voz explica dónde instalar otra (sin fila B vacía)", async () => {
    getVoicesMock.mockResolvedValue(catalog([TWO_VOICES[0]]));
    renderPicker();

    expect(
      await screen.findByText(/Solo tienes una voz instalada/),
    ).toBeTruthy();
    expect(screen.queryByText("Voz B — segundo acento")).toBeNull();
    // Sin B no tiene sentido ofrecer «Probar B».
    expect(screen.queryByRole("button", { name: "Probar B" })).toBeNull();
  });

  it("un catálogo caído se cuenta en vez de dejar el panel en blanco", async () => {
    getVoicesMock.mockRejectedValue(new Error("offline"));
    renderPicker();

    expect(
      await screen.findByText("No se pudo leer el catálogo de voces."),
    ).toBeTruthy();
  });
});

describe("VoicePicker · V3.75.6 lectura al repetir", () => {
  beforeEach(() => {
    resetVoiceChoice();
    vi.clearAllMocks();
    getSettingsMock.mockResolvedValue({ settings: {} });
    saveSettingsMock.mockResolvedValue({ settings: {} });
    getVoicesMock.mockResolvedValue(catalog(TWO_VOICES));
  });

  afterEach(() => {
    cleanup();
    resetVoiceChoice();
  });

  it("ofrece las tres lecturas y arranca en «el ítem completo»", async () => {
    renderPicker();

    const group = await screen.findByRole("radiogroup", {
      name: "Al repetir, leer",
    });
    const radios = within(group).getAllByRole("radio");
    expect(radios).toHaveLength(3);
    // El orden importa: la primera es el defecto.
    expect(radios.map((radio) => radio.textContent?.trim())).toEqual([
      "El ítem completo",
      "El ítem más las opciones",
      "Solo la respuesta correcta",
    ]);
    expect(radios[0].getAttribute("aria-checked")).toBe("true");
    // El recibo describe las piezas de la lectura activa.
    expect(screen.getByText(/texto del ítem \+ pregunta \+ respuesta correcta/i)).toBeTruthy();
  });

  it("elegir otra lectura la guarda y actualiza el recibo", async () => {
    renderPicker();

    const group = await screen.findByRole("radiogroup", {
      name: "Al repetir, leer",
    });
    const item = within(group).getByRole("radio", { name: /^El ítem completo$/i });
    const withOptions = within(group).getByRole("radio", {
      name: /El ítem más las opciones/i,
    });
    const correct = within(group).getByRole("radio", {
      name: /Solo la respuesta correcta/i,
    });

    fireEvent.click(withOptions);
    await waitFor(() =>
      expect(saveSettingsMock).toHaveBeenCalledWith("user-1", {
        replay_scope: "withOptions",
      }),
    );
    expect(withOptions.getAttribute("aria-checked")).toBe("true");
    expect(item.getAttribute("aria-checked")).toBe("false");
    expect(screen.getByText(/texto del ítem \+ pregunta \+ opciones/i)).toBeTruthy();

    fireEvent.click(correct);
    await waitFor(() =>
      expect(saveSettingsMock).toHaveBeenCalledWith("user-1", {
        replay_scope: "correct",
      }),
    );
    expect(correct.getAttribute("aria-checked")).toBe("true");
    expect(withOptions.getAttribute("aria-checked")).toBe("false");
    expect(screen.getByText(/^Se lee: pregunta \+ respuesta correcta\.$/i)).toBeTruthy();
  });

  it("lee la preferencia guardada del perfil", async () => {
    getSettingsMock.mockResolvedValue({ settings: { replay_scope: "correct" } });
    renderPicker();

    const group = await screen.findByRole("radiogroup", {
      name: "Al repetir, leer",
    });
    await waitFor(() =>
      expect(
        within(group)
          .getByRole("radio", { name: /Solo la respuesta correcta/i })
          .getAttribute("aria-checked"),
      ).toBe("true"),
    );
  });

  it("un valor histórico `all` se muestra como «el ítem más las opciones»", async () => {
    getSettingsMock.mockResolvedValue({ settings: { replay_scope: "all" } });
    renderPicker();

    const group = await screen.findByRole("radiogroup", {
      name: "Al repetir, leer",
    });
    await waitFor(() =>
      expect(
        within(group)
          .getByRole("radio", { name: /El ítem más las opciones/i })
          .getAttribute("aria-checked"),
      ).toBe("true"),
    );
  });

  it("sigue disponible aunque falle el catálogo de voces", async () => {
    getVoicesMock.mockRejectedValue(new Error("offline"));
    renderPicker();

    expect(
      await screen.findByRole("radiogroup", { name: "Al repetir, leer" }),
    ).toBeTruthy();
  });
});
