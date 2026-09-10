// @vitest-environment jsdom
/**
 * Vitest de `DictionaryScreen` (V3.39): persistencia de la pestaña
 * Personal/Consultar.
 *
 * Se mockean las dos vistas hijas (no son el objeto de estas pruebas) y la API
 * de settings para verificar el patrón doble: arranque desde `localStorage`,
 * hidratación desde `GET /api/settings` al montar y escritura a
 * `localStorage` + `PUT /api/settings` al cambiar de pestaña.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

  it("arranca en Personal por defecto", () => {
    renderScreen();
    expect(screen.getByText("personal-view")).toBeTruthy();
    expect(screen.queryByText("lookup-view")).toBeNull();
    expect(
      screen.getByRole("button", { name: "Personal" }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("arranca en la pestaña guardada en localStorage", () => {
    window.localStorage.setItem(DICTIONARY_VIEW_STORAGE_KEY, "lookup");

    renderScreen();

    expect(screen.getByText("lookup-view")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Look up" }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("hidrata desde los settings del usuario al montar", async () => {
    getSettingsMock.mockResolvedValue({ settings: { dictionary_view: "lookup" } });

    renderScreen("u1");

    await waitFor(() => expect(screen.getByText("lookup-view")).toBeTruthy());
    // La hidratación también refresca la copia local (arranque sin parpadeo).
    expect(window.localStorage.getItem(DICTIONARY_VIEW_STORAGE_KEY)).toBe("lookup");
  });

  it("ignora un valor de settings inválido y cae a Personal", async () => {
    window.localStorage.clear();
    getSettingsMock.mockResolvedValue({ settings: { dictionary_view: "nope" } });

    renderScreen("u1");

    await waitFor(() => expect(getSettingsMock).toHaveBeenCalledWith("u1"));
    expect(screen.getByText("personal-view")).toBeTruthy();
  });

  it("al cambiar de pestaña persiste en localStorage y en settings", async () => {
    renderScreen("u1");

    fireEvent.click(screen.getByRole("button", { name: "Look up" }));

    expect(screen.getByText("lookup-view")).toBeTruthy();
    expect(window.localStorage.getItem(DICTIONARY_VIEW_STORAGE_KEY)).toBe("lookup");
    await waitFor(() =>
      expect(saveSettingsMock).toHaveBeenCalledWith("u1", {
        dictionary_view: "lookup",
      }),
    );
  });

  it("sin perfil sigue persistiendo en localStorage (sin llamada a settings)", async () => {
    renderScreen(null);

    fireEvent.click(screen.getByRole("button", { name: "Look up" }));

    expect(window.localStorage.getItem(DICTIONARY_VIEW_STORAGE_KEY)).toBe("lookup");
    expect(saveSettingsMock).not.toHaveBeenCalled();
  });
});
