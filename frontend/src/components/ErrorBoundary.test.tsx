// @vitest-environment jsdom
/**
 * Vitest de `ErrorBoundary` (V3.77.2).
 *
 * Lo que se fija: un error lanzado al pintar NO se propaga (no se desmonta el
 * árbol) y el alumno recibe un panel con salida (reintentar / recargar). Sin
 * boundary, React desmonta la app entera ante el mismo throw.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { ErrorBoundary } from "./ErrorBoundary";

function Boom({ explode }: { explode: boolean }) {
  if (explode) throw new Error("contract-undefined");
  return <p>contenido vivo</p>;
}

describe("ErrorBoundary", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("contiene el fallo y ofrece salida en vez de propagarlo", () => {
    // El log de diagnóstico no debe ensuciar la salida del test.
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary scope="route">
        <Boom explode />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("Something went wrong")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reload the app" })).toBeTruthy();
    // El detalle técnico es honesto: el mensaje real, no un texto genérico.
    expect(screen.getByText("contract-undefined")).toBeTruthy();
  });

  it("«Try again» rehace el render y el hijo sano vuelve a pintarse", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    function Recoverable() {
      const [explode, setExplode] = useState(true);
      return (
        <ErrorBoundary scope="route" onReset={() => setExplode(false)}>
          <Boom explode={explode} />
        </ErrorBoundary>
      );
    }

    render(<Recoverable />);
    expect(screen.getByRole("alert")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(screen.getByText("contenido vivo")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("sin error pinta a los hijos tal cual (no añade ruido)", () => {
    render(
      <ErrorBoundary scope="route">
        <Boom explode={false} />
      </ErrorBoundary>,
    );

    expect(screen.getByText("contenido vivo")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
