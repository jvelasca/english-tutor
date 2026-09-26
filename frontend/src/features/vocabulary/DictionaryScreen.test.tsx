// @vitest-environment jsdom
/**
 * Vitest de `DictionaryScreen` (V3.39, reorganizado en V3.85.0): persistencia de
 * la pestaña y los DOS modos (Consultar · Flashcards), con el inventario como
 * sub-pestaña «Mi léxico» de Flashcards.
 *
 * El punto delicado es la PROYECCIÓN del valor persistido: `"personal"` sigue
 * siendo un valor válido (cero migración) y abre Flashcards en «Mi léxico»; el
 * resto de sub-pestañas abren Estudiar y persisten `"flashcards"`. Se mockean
 * las vistas hijas (no son el objeto de estas pruebas) y la API de settings para
 * verificar el patrón doble: arranque desde `localStorage`, hidratación desde
 * `GET /api/settings` al montar y escritura a `localStorage` + `PUT
 * /api/settings` al navegar.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { getSettings, saveSettings } from "../../api/settings";
import { I18nProvider } from "../../hooks/useI18n";
import { DICTIONARY_VIEW_STORAGE_KEY } from "../../utils/dictionaryView";
import { setPendingStudyFocus } from "../../utils/studyFocus";
import { DictionaryScreen } from "./DictionaryScreen";

vi.mock("./LexiconInventory", () => ({
  LexiconInventory: () => <div>lexicon-view</div>,
}));
vi.mock("./DictionaryLookup", () => ({
  DictionaryLookup: () => <div>lookup-view</div>,
}));
/**
 * Doble de `FlashcardsScreen`: expone la sub-pestaña CONTROLADA que le pasa la
 * pantalla y dos botones para cambiarla, que es lo único que necesita el
 * contrato de proyección/persistencia.
 */
vi.mock("./FlashcardsScreen", () => ({
  FlashcardsScreen: ({
    tab,
    onTabChange,
    focusDeckId,
    focusNonce,
  }: {
    tab?: string;
    onTabChange?: (next: string) => void;
    focusDeckId?: number | null;
    focusNonce?: number;
  }) => (
    <div>
      <div>{`flashcards-view:${tab ?? "uncontrolled"}`}</div>
      <div>{`flashcards-focus:${focusDeckId ?? "none"}:${focusNonce ?? 0}`}</div>
      <button type="button" onClick={() => onTabChange?.("study")}>
        goto-study
      </button>
      <button type="button" onClick={() => onTabChange?.("lexicon")}>
        goto-lexicon
      </button>
    </div>
  ),
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

describe("DictionaryScreen · V3.85.0 dos pestañas y proyección", () => {
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
    renderScreen();
    expect(screen.getByText("lookup-view")).toBeTruthy();
    expect(screen.queryByText("lexicon-view")).toBeNull();
    expect(
      screen.getByRole("tab", { name: "Look up" }).getAttribute("aria-selected"),
    ).toBe("true");
  });

  it("solo hay dos pestañas, en el orden Consultar · Flashcards", () => {
    renderScreen();
    expect(tabNames()).toEqual(["Look up", "Flashcards"]);
  });

  it("un `personal` heredado abre Flashcards en «Mi léxico» (cero migración)", () => {
    // El valor guardado por una versión anterior debe seguir abriendo donde el
    // alumno lo dejó: no se migra el dominio persistido, se proyecta.
    window.localStorage.setItem(DICTIONARY_VIEW_STORAGE_KEY, "personal");

    renderScreen();

    expect(screen.getByText("flashcards-view:lexicon")).toBeTruthy();
    expect(
      screen.getByRole("tab", { name: "Flashcards" }).getAttribute("aria-selected"),
    ).toBe("true");
  });

  it("un `flashcards` heredado abre Flashcards en Estudiar", () => {
    window.localStorage.setItem(DICTIONARY_VIEW_STORAGE_KEY, "flashcards");

    renderScreen();

    expect(screen.getByText("flashcards-view:study")).toBeTruthy();
  });

  it("elegir «Mi léxico» persiste `personal` (el recuerdo sigue teniendo sentido)", async () => {
    renderScreen("u1");
    fireEvent.click(screen.getByRole("tab", { name: "Flashcards" }));
    fireEvent.click(screen.getByRole("button", { name: "goto-lexicon" }));

    expect(window.localStorage.getItem(DICTIONARY_VIEW_STORAGE_KEY)).toBe(
      "personal",
    );
    await waitFor(() =>
      expect(saveSettingsMock).toHaveBeenCalledWith("u1", {
        dictionary_view: "personal",
      }),
    );
  });

  it("cualquier otra sub-pestaña persiste `flashcards`", async () => {
    window.localStorage.setItem(DICTIONARY_VIEW_STORAGE_KEY, "personal");

    renderScreen("u1");
    fireEvent.click(screen.getByRole("button", { name: "goto-study" }));

    expect(window.localStorage.getItem(DICTIONARY_VIEW_STORAGE_KEY)).toBe(
      "flashcards",
    );
    await waitFor(() =>
      expect(saveSettingsMock).toHaveBeenCalledWith("u1", {
        dictionary_view: "flashcards",
      }),
    );
  });

  it("al volver a Flashcards se recuerda la sub-pestaña en la que estabas", () => {
    renderScreen();
    fireEvent.click(screen.getByRole("tab", { name: "Flashcards" }));
    fireEvent.click(screen.getByRole("button", { name: "goto-lexicon" }));

    // A Consultar y de vuelta: no se cae al estudio, se vuelve a «Mi léxico».
    fireEvent.click(screen.getByRole("tab", { name: "Look up" }));
    expect(screen.getByText("lookup-view")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Flashcards" }));

    expect(screen.getByText("flashcards-view:lexicon")).toBeTruthy();
    expect(window.localStorage.getItem(DICTIONARY_VIEW_STORAGE_KEY)).toBe(
      "personal",
    );
  });

  it("hidrata desde los settings del usuario al montar", async () => {
    getSettingsMock.mockResolvedValue({ settings: { dictionary_view: "lookup" } });

    renderScreen("u1");

    await waitFor(() => expect(screen.getByText("lookup-view")).toBeTruthy());
    // La hidratación también refresca la copia local (arranque sin parpadeo).
    expect(window.localStorage.getItem(DICTIONARY_VIEW_STORAGE_KEY)).toBe("lookup");
  });

  it("ignora un valor de settings inválido y cae al defecto", async () => {
    getSettingsMock.mockResolvedValue({ settings: { dictionary_view: "nope" } });

    renderScreen("u1");

    await waitFor(() => expect(getSettingsMock).toHaveBeenCalledWith("u1"));
    expect(screen.getByText("lookup-view")).toBeTruthy();
  });

  it("sin perfil sigue persistiendo en localStorage (sin llamada a settings)", () => {
    renderScreen(null);

    fireEvent.click(screen.getByRole("tab", { name: "Flashcards" }));
    fireEvent.click(screen.getByRole("button", { name: "goto-lexicon" }));

    expect(window.localStorage.getItem(DICTIONARY_VIEW_STORAGE_KEY)).toBe(
      "personal",
    );
    expect(saveSettingsMock).not.toHaveBeenCalled();
  });

  it("el salto del diccionario incrustado abre Flashcards en el mazo pedido (V3.86.0)", () => {
    // APRENDER → Vocabulario es otra pantalla: el panel no hospeda la sesión, así
    // que «Estudiar en Flashcards» deja un recado y navega. El mazo elegido tiene
    // que llegar: si se perdiera, el alumno aterrizaría en el mazo automático y
    // creería que su tarjeta no entró.
    window.localStorage.setItem(DICTIONARY_VIEW_STORAGE_KEY, "flashcards");
    setPendingStudyFocus(7);

    renderScreen();

    expect(screen.getByText("flashcards-view:study")).toBeTruthy();
    expect(screen.getByText("flashcards-focus:7:1")).toBeTruthy();
  });

  it("el recado del salto es de UN solo uso y sin mazo pide el automático (V3.86.0)", () => {
    window.localStorage.setItem(DICTIONARY_VIEW_STORAGE_KEY, "flashcards");
    setPendingStudyFocus();

    const first = renderScreen();
    // `null` = el mazo automático, a propósito (una palabra ya rastreada vive
    // allí). Y se consume: no queda vivo para una visita posterior.
    expect(screen.getByText("flashcards-focus:none:1")).toBeTruthy();
    first.unmount();

    renderScreen();
    expect(screen.getByText("flashcards-focus:none:0")).toBeTruthy();
  });

  // --- V3.80.1: los modos son pestañas ARIA reales ---------------------------

  it("los modos son pestañas ARIA con su tabpanel asociado", () => {
    renderScreen();
    const tablist = screen.getByRole("tablist", { name: "Dictionary views" });
    const tabs = within(tablist).getAllByRole("tab");
    expect(tabs).toHaveLength(2);
    // Roving tabindex: solo la activa es tabulable.
    expect(tabs.map((tab) => tab.getAttribute("tabindex"))).toEqual(["0", "-1"]);

    const panel = screen.getByRole("tabpanel");
    expect(panel.getAttribute("aria-labelledby")).toBe("dictionary-tab-lookup");
    expect(tabs[0].getAttribute("aria-controls")).toBe(panel.id);
  });

  it("las flechas mueven la pestaña activa y el foco", () => {
    renderScreen();
    const lookup = screen.getByRole("tab", { name: "Look up" });
    lookup.focus();
    fireEvent.keyDown(lookup, { key: "ArrowRight" });

    expect(screen.getByText("flashcards-view:study")).toBeTruthy();
    const flashcards = screen.getByRole("tab", { name: "Flashcards" });
    expect(flashcards.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(flashcards);
  });
});
