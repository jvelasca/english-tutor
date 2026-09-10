// @vitest-environment jsdom
/**
 * Vitest de la navegación raíz (V3.38.1): además de los 3 mundos, el
 * diccionario es un 4.º destino AUXILIAR separado visualmente del núcleo.
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

describe("Navigation (V3.38.1)", () => {
  afterEach(cleanup);

  it("ofrece los 3 mundos más el diccionario auxiliar", () => {
    renderNav(<Navigation route="home" onNavigate={() => {}} />);
    for (const name of ["Home", "Course", "Learn", "Dictionary"]) {
      expect(screen.getByRole("button", { name })).toBeTruthy();
    }
  });

  it("separa el diccionario del núcleo con un divisor", () => {
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
});
