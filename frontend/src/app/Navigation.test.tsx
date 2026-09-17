// @vitest-environment jsdom
/**
 * Vitest de la navegación raíz (V3.39): además de los 3 mundos, el diccionario
 * y el traductor son destinos AUXILIARES separados visualmente del núcleo.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { I18nProvider } from "../hooks/useI18n";
import { Navigation } from "./Navigation";

function renderNav(ui: ReactElement) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      {ui}
    </I18nProvider>,
  );
}

describe("Navigation (V3.39)", () => {
  afterEach(cleanup);

  it("ofrece los 3 mundos más los destinos auxiliares", () => {
    renderNav(<Navigation route="home" onNavigate={() => {}} />);
    for (const name of ["Home", "Course", "Learn", "Dictionary", "Translator"]) {
      expect(screen.getByRole("button", { name })).toBeTruthy();
    }
  });

  it("separa los destinos auxiliares del núcleo con un divisor", () => {
    const { getAllByTestId } = renderNav(
      <Navigation route="home" onNavigate={() => {}} />,
    );
    expect(getAllByTestId("nav-divider")).toHaveLength(1);
  });

  it("navega al diccionario al pulsar su destino", () => {
    const onNavigate = vi.fn();
    renderNav(<Navigation route="home" onNavigate={onNavigate} />);
    fireEvent.click(screen.getByRole("button", { name: "Dictionary" }));
    expect(onNavigate).toHaveBeenCalledWith("dictionary");
  });

  it("navega al traductor al pulsar su destino", () => {
    const onNavigate = vi.fn();
    renderNav(<Navigation route="home" onNavigate={onNavigate} />);
    fireEvent.click(screen.getByRole("button", { name: "Translator" }));
    expect(onNavigate).toHaveBeenCalledWith("translator");
  });

  it("la bottom-nav marca el diccionario como destino activo", () => {
    renderNav(
      <Navigation route="dictionary" onNavigate={() => {}} variant="bottom" />,
    );
    expect(
      screen
        .getByRole("button", { name: "Dictionary" })
        .getAttribute("aria-current"),
    ).toBe("page");
  });

  it("la bottom-nav marca el traductor como destino activo", () => {
    renderNav(
      <Navigation route="translator" onNavigate={() => {}} variant="bottom" />,
    );
    expect(
      screen
        .getByRole("button", { name: "Translator" })
        .getAttribute("aria-current"),
    ).toBe("page");
  });

  it("la bottom-nav mantiene los 5 destinos con divisor y toque completo (V3.73.1)", () => {
    const { getByTestId } = renderNav(
      <Navigation route="home" onNavigate={() => {}} variant="bottom" />,
    );

    // Siguen estando los cinco: el diccionario no se esconde en un menú.
    for (const name of ["Home", "Course", "Learn", "Dictionary", "Translator"]) {
      expect(screen.getByRole("button", { name })).toBeTruthy();
    }

    // La jerarquía se marca con un divisor real entre los 3 mundos y las 2
    // utilidades.
    expect(getByTestId("nav-divider")).toBeTruthy();

    // Ningún destino pierde el tamaño de toque mínimo, auxiliares incluidos.
    for (const name of ["Home", "Dictionary", "Translator"]) {
      const button = screen.getByRole("button", { name });
      expect(button.className).toContain("min-h-14");
      expect(button.className).toContain("flex-1");
      expect(button.className).toContain("min-w-0");
    }
  });
});
