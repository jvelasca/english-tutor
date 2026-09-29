// @vitest-environment jsdom
/**
 * Vitest de `LoadingNotice` (V3.88.0).
 *
 * El proyecto ya sabía decir «cargando» (`PanelState`, `TabLoading`), pero no
 * distinguía una consulta instantánea de una que se alarga. Este componente
 * protege esa distinción: spinner → reloj + aviso al vencer el umbral, con el
 * contrato de accesibilidad (`role="status"`, `aria-busy`, `aria-live`).
 */
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../hooks/useI18n";
import { LoadingNotice } from "./LoadingNotice";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function renderNotice(props: Parameters<typeof LoadingNotice>[0] = {}) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <LoadingNotice {...props} />
    </I18nProvider>,
  );
}

describe("LoadingNotice", () => {
  it("arranca como estado anunciado, sin aviso de lentitud", () => {
    renderNotice();

    const status = screen.getByRole("status");
    expect(status.getAttribute("aria-busy")).toBe("true");
    expect(status.getAttribute("aria-live")).toBe("polite");
    expect(status.textContent).toContain("Loading…");
    expect(status.textContent).not.toContain("Still working");
  });

  it("cambia a reloj y añade el aviso cuando la espera supera el umbral", () => {
    renderNotice({ slowAfterMs: 4000 });
    expect(screen.queryByText(/Still working/)).toBeNull();

    act(() => vi.advanceTimersByTime(4000));

    expect(screen.getByText(/Still working/)).toBeTruthy();
  });

  it("no declara lentitud antes de tiempo (umbral configurable)", () => {
    renderNotice({ slowAfterMs: 8000 });

    act(() => vi.advanceTimersByTime(7900));
    expect(screen.queryByText(/Still working/)).toBeNull();

    act(() => vi.advanceTimersByTime(100));
    expect(screen.getByText(/Still working/)).toBeTruthy();
  });

  it("no deja el aviso colgando si se desmonta antes del umbral", () => {
    const { unmount } = renderNotice({ slowAfterMs: 4000 });
    unmount();

    act(() => vi.advanceTimersByTime(10000));

    // El temporizador se cancela al desmontar: no queda nada que anunciar.
    expect(screen.queryByText(/Still working/)).toBeNull();
  });

  it("acepta etiqueta y aviso propios (para la carga de mazos)", () => {
    renderNotice({
      label: "Loading your decks…",
      slowLabel: "Almost there",
      slowAfterMs: 1000,
    });

    expect(screen.getByText("Loading your decks…")).toBeTruthy();
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByText("Almost there")).toBeTruthy();
  });
});
