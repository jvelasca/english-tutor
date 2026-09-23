// @vitest-environment jsdom
/**
 * Vitest de `DictionaryScreen` (V3.39, ampliado en V3.78.0): persistencia de la
 * pestaña y los TRES modos (Consultar · Personal · Flashcards).
 *
 * Se mockean las tres vistas hijas (no son el objeto de estas pruebas) y la API
 * de settings para verificar el patrón doble: arranque desde `localStorage`,
 * hidratación desde `GET /api/settings` al montar y escritura a
 * `localStorage` + `PUT /api/settings` al cambiar de pestaña.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { getSettings, saveSettings } from "../../api/settings";
import { I18nProvider } from "../../hooks/useI18n";
import { DICTIONARY_VIEW_STORAGE_KEY } from "../../utils/dictionaryView";
import { DictionaryScreen } from "./DictionaryScreen";

vi.mock("./PersonalDictionary", () => ({
  PersonalDictionary: () => <div>personal-view</div>,
}));
vi.mock("./DictionaryLookup", () => ({
  DictionaryLookup: () => <div>lookup-view</div>,
}));
vi.mock("./FlashcardsScreen", () => ({
  FlashcardsScreen: () => <div>flashcards-view</div>,
}));
vi.mock("../../api/settings", () => ({
  getSettings: vi.fn(),
  saveSettings: vi.fn(),
}));

const getSettingsMock = vi.mocked(getSettings);
const saveSettingsMock = vi.mocked(saveSettings);

function renderScreen(userId: string | null = "u1") {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <DictionaryScreen userId={userId} />
    </I18nProvider>,
  );
}

/** Pestañas del tablist de vistas, en el orden en que se pintan. */
function tabNames(): string[] {
  return screen.getAllByRole("tab").map((b) => b.textContent ?? "");
}

describe("DictionaryScreen · V3.39 persistencia de la pestaña", () => {
  beforeEach(() => {
    window.localStorage.clear();
    getSettingsMock.mockResolvedValue({ settings: {} });
    saveSettingsMock.mockResolvedValue({ settings: {} });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("arranca en Consultar por defecto", () => {
    // V3.78.0: el defecto cambió de `personal` a `lookup`: es el primer modo del
    // orden y el que responde a la pregunta con la que se abre un diccionario.
    renderScreen();
    expect(screen.getByText("lookup-view")).toBeTruthy();
    expect(screen.queryByText("personal-view")).toBeNull();
    expect(
      screen
        .getByRole("tab", { name: "Look up" })
        .getAttribute("aria-selected"),
    ).toBe("true");
  });

  it("las tres pestañas se ofrecen en el orden Consultar · Personal · Flashcards", () => {
    renderScreen();
    expect(tabNames()).toEqual(["Look up", "Personal", "Flashcards"]);
  });

  it("la pestaña Flashcards monta la superficie de estudio y la persiste", async () => {
    renderScreen("u1");

    fireEvent.click(screen.getByRole("tab", { name: "Flashcards" }));

    expect(screen.getByText("flashcards-view")).toBeTruthy();
    expect(window.localStorage.getItem(DICTIONARY_VIEW_STORAGE_KEY)).toBe(
      "flashcards",
    );
    await waitFor(() =>
      expect(saveSettingsMock).toHaveBeenCalledWith("u1", {
        dictionary_view: "flashcards",
      }),
    );
  });

  it("arranca en la pestaña guardada en localStorage", () => {
    window.localStorage.setItem(DICTIONARY_VIEW_STORAGE_KEY, "flashcards");

    renderScreen();

    expect(screen.getByText("flashcards-view")).toBeTruthy();
    expect(
      screen
        .getByRole("tab", { name: "Flashcards" })
        .getAttribute("aria-selected"),
    ).toBe("true");
  });

  it("hidrata desde los settings del usuario al montar", async () => {
    getSettingsMock.mockResolvedValue({ settings: { dictionary_view: "lookup" } });

    renderScreen("u1");

    await waitFor(() => expect(screen.getByText("lookup-view")).toBeTruthy());
    // La hidratación también refresca la copia local (arranque sin parpadeo).
    expect(window.localStorage.getItem(DICTIONARY_VIEW_STORAGE_KEY)).toBe("lookup");
  });

  it("ignora un valor de settings inválido y cae al defecto", async () => {
    window.localStorage.clear();
    getSettingsMock.mockResolvedValue({ settings: { dictionary_view: "nope" } });

    renderScreen("u1");

    await waitFor(() => expect(getSettingsMock).toHaveBeenCalledWith("u1"));
    expect(screen.getByText("lookup-view")).toBeTruthy();
  });

  it("al cambiar de pestaña persiste en localStorage y en settings", async () => {
    renderScreen("u1");

    fireEvent.click(screen.getByRole("tab", { name: "Personal" }));

    expect(screen.getByText("personal-view")).toBeTruthy();
    expect(window.localStorage.getItem(DICTIONARY_VIEW_STORAGE_KEY)).toBe(
      "personal",
    );
    await waitFor(() =>
      expect(saveSettingsMock).toHaveBeenCalledWith("u1", {
        dictionary_view: "personal",
      }),
    );
  });

  it("sin perfil sigue persistiendo en localStorage (sin llamada a settings)", async () => {
    renderScreen(null);

    fireEvent.click(screen.getByRole("tab", { name: "Personal" }));

    expect(window.localStorage.getItem(DICTIONARY_VIEW_STORAGE_KEY)).toBe(
      "personal",
    );
    expect(saveSettingsMock).not.toHaveBeenCalled();
  });

  // --- V3.80.1: los modos son pestañas ARIA reales ---------------------------

  it("los modos son pestañas ARIA con su tabpanel asociado", () => {
    renderScreen();
    const tablist = screen.getByRole("tablist", { name: "Dictionary views" });
    const tabs = within(tablist).getAllByRole("tab");
    expect(tabs).toHaveLength(3);
    // Roving tabindex: solo la activa es tabulable.
    expect(tabs.map((tab) => tab.getAttribute("tabindex"))).toEqual([
      "0",
      "-1",
      "-1",
    ]);

    const panel = screen.getByRole("tabpanel");
    expect(panel.getAttribute("aria-labelledby")).toBe("dictionary-tab-lookup");
    expect(tabs[0].getAttribute("aria-controls")).toBe(panel.id);
  });

  it("las flechas mueven la pestaña activa y el foco", () => {
    renderScreen();
    const lookup = screen.getByRole("tab", { name: "Look up" });
    lookup.focus();
    fireEvent.keyDown(lookup, { key: "ArrowRight" });

    expect(screen.getByText("personal-view")).toBeTruthy();
    const personal = screen.getByRole("tab", { name: "Personal" });
    expect(personal.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(personal);
  });
});
