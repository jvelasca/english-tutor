// @vitest-environment jsdom
/**
 * Vitest de `WhyThisActivity` (V3.72, deuda UX «por qué esta actividad»): la
 * pieza compartida que presenta el `why` **declarado por el servidor** en las
 * superficies donde faltaba (pie «Next» del bucle de práctica y filas de la
 * cola de repaso).
 *
 * Contrato que se fija aquí (premisa 21: el cliente NO recalcula señales):
 * 1. Sin `why` ni `because` no se pinta nada: nunca se inventa una explicación.
 * 2. La frase se pinta **verbatim** (contrato `why` del proyecto: inglés, frases
 *    deterministas); la UI solo añade la etiqueta traducida.
 * 3. `compact` (pies y filas) muestra solo la frase; el `because[]` completo
 *    sigue viviendo en `NextBestCard`.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { I18nProvider } from "../hooks/useI18n";
import { WhyThisActivity } from "./WhyThisActivity";

function renderWhy(ui: React.ReactElement) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      {ui}
    </I18nProvider>,
  );
}

describe("WhyThisActivity (V3.72)", () => {
  afterEach(() => {
    cleanup();
  });

  it("sin `why` ni `because` no pinta nada (nunca inventa la explicación)", () => {
    const { container } = renderWhy(<WhyThisActivity />);

    expect(container.textContent).toBe("");
    expect(screen.queryByText("Why?")).toBeNull();
  });

  it("pinta la frase declarada con la etiqueta traducida, verbatim", () => {
    renderWhy(<WhyThisActivity why="due for review (memory decayed)" />);

    const line = screen.getByText(/due for review \(memory decayed\)/);
    expect(line.textContent).toContain("Why?");
    // El texto es del servidor: la UI no lo traduce ni lo reescribe.
    expect(line.textContent).toContain("due for review (memory decayed)");
  });

  it("une en una sola frase el `why` en lista del planner (contrato V3.64)", () => {
    renderWhy(
      <WhyThisActivity
        why={["large competence gap in the limiting modality", "review is due"]}
      />,
    );

    const line = screen.getByText(/large competence gap in the limiting modality/);
    expect(line.textContent).toBe(
      "Why? large competence gap in the limiting modality; review is due",
    );
  });

  it("compact: solo la frase declarada, sin la lista `because[]`", () => {
    renderWhy(
      <WhyThisActivity
        variant="compact"
        why="scheduled maintenance"
        because={["Grammar is your weakest skill right now."]}
      />,
    );

    expect(screen.getByText(/scheduled maintenance/).textContent).toBe(
      "Why? scheduled maintenance",
    );
    expect(screen.queryByText("Because:")).toBeNull();
    expect(
      screen.queryByText("Grammar is your weakest skill right now."),
    ).toBeNull();
  });

  it("full: pinta `because[]` y el factor limitante con su score", () => {
    renderWhy(
      <WhyThisActivity
        why="Grammar is your weakest skill right now, so it comes first today."
        because={["Only 2 of 6 objectives mastered."]}
        limitingFactor={{ id: "grammar", score: 0.42 }}
      />,
    );

    expect(screen.getByText("Because:")).toBeTruthy();
    expect(screen.getByText("Only 2 of 6 objectives mastered.")).toBeTruthy();
    expect(screen.getByText(/Limiting factor/)).toBeTruthy();
    expect(screen.getByText(/42%/)).toBeTruthy();
  });

  it("full: sin medida declarada el factor limitante se marca como `missing`", () => {
    renderWhy(
      <WhyThisActivity
        why="New material."
        because={["Steady progress."]}
        limitingFactor={{ id: "grammar", score: 0, missing: true }}
      />,
    );

    expect(screen.getByText(/missing/)).toBeTruthy();
    expect(screen.queryByText(/0%/)).toBeNull();
  });

  it("un `because[]` sin frase declarada sigue pintando la explicación", () => {
    renderWhy(<WhyThisActivity because={["Steady progress."]} />);

    expect(screen.queryByText("Why?")).toBeNull();
    expect(screen.getByText("Because:")).toBeTruthy();
    expect(screen.getByText("Steady progress.")).toBeTruthy();
  });
});
