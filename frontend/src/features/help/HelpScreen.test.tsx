// @vitest-environment jsdom
/**
 * Vitest de la Ayuda (V3.75.8). Fija las dos cosas que esta pantalla declara y
 * que antes no estaban en ningún test:
 *
 * - la **versión de la compilación** junto al autor, leída del bundle y no de la
 *   API (la Ayuda no pide nada a la red: si un día alguien la cableara a
 *   `/api/health`, este test seguiría pasando solo si el valor viene de
 *   `utils/buildInfo.ts`, que es la fuente que `check_release_consistency.py`
 *   vigila contra `backend/config.py::VERSION`);
 * - que la tarjeta de vocabulario explica el **sentido** de la consulta del
 *   diccionario, que es la parte visible del rediseño de V3.75.8.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { I18nProvider } from "../../hooks/useI18n";
import { APP_VERSION } from "../../utils/buildInfo";
import { HelpScreen } from "./HelpScreen";

function renderHelp() {
  render(
    <I18nProvider lang="en" setLang={() => {}}>
      <HelpScreen />
    </I18nProvider>,
  );
}

describe("HelpScreen (V3.75.8)", () => {
  afterEach(cleanup);

  it("declara la versión de la compilación junto al autor", () => {
    renderHelp();

    expect(screen.getByText("About the author")).toBeTruthy();
    expect(screen.getByText("J. Alberto Velasco")).toBeTruthy();
    expect(screen.getByText(`Build version v${APP_VERSION}`)).toBeTruthy();
  });

  it("la versión declarada es la del paquete, con forma de versión", () => {
    // Si el número deja de salir del `package.json` (o el import se rompe), la
    // línea de la Ayuda diría una versión que no es la que se publicó.
    expect(APP_VERSION).toMatch(/^\d+\.\d+\.\d+$/);
  });

  it("la tarjeta de vocabulario explica el sentido de la consulta", () => {
    renderHelp();

    expect(
      screen.getByText(/each direction has its own colour/i),
    ).toBeTruthy();
  });
});
