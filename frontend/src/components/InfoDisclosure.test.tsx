// @vitest-environment jsdom
/**
 * Vitest del desplegable informativo (V3.48.1 / V3.75.7): un único disparador que
 * monta el panel solo cuando se abre, lo desmonta al cerrarlo y **promete con su
 * icono lo que hay dentro** —(i) para solo notas, (...) para notas y opciones—.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { InfoDisclosure } from "./InfoDisclosure";

/** Clases de los `<svg>` del disparador (lucide marca cada icono). */
function iconClasses(trigger: HTMLElement): string {
  return trigger.querySelector("svg")?.getAttribute("class") ?? "";
}

describe("InfoDisclosure (V3.48.1)", () => {
  afterEach(cleanup);

  it("arranca cerrado y no monta el contenido", () => {
    render(
      <InfoDisclosure label="More information">
        <p>Nota larga</p>
      </InfoDisclosure>,
    );
    const trigger = screen.getByRole("button", { name: "More information" });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("Nota larga")).toBeNull();
  });

  it("abre y cierra el panel al pulsar el disparador", () => {
    render(
      <InfoDisclosure label="More information" id="notes">
        <p>Nota larga</p>
      </InfoDisclosure>,
    );
    const trigger = screen.getByRole("button", { name: "More information" });

    fireEvent.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    const panel = screen.getByText("Nota larga").parentElement;
    expect(panel?.id).toBe("notes");

    fireEvent.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("Nota larga")).toBeNull();
  });
});

describe("InfoDisclosure · el icono promete lo que hay dentro (V3.75.7)", () => {
  afterEach(cleanup);

  it("solo notas ⇒ (i), que es el caso por defecto", () => {
    render(
      <InfoDisclosure label="Más información">
        <p>Nota larga</p>
      </InfoDisclosure>,
    );
    const trigger = screen.getByRole("button", { name: "Más información" });
    expect(iconClasses(trigger)).toMatch(/lucide-info\b/);
    expect(iconClasses(trigger)).not.toMatch(/more-horizontal|ellipsis/);
  });

  it("notas y opciones ⇒ (...)", () => {
    render(
      <InfoDisclosure label="Opciones e información" content="options">
        <p>Nota larga</p>
        <button type="button">Elegir voz</button>
      </InfoDisclosure>,
    );
    const trigger = screen.getByRole("button", { name: "Opciones e información" });
    expect(iconClasses(trigger)).toMatch(/more-horizontal|ellipsis/);
    expect(iconClasses(trigger)).not.toMatch(/lucide-info\b/);
  });
});

describe("InfoDisclosure · el texto no queda debajo del disparador (V3.75.7)", () => {
  afterEach(cleanup);

  /**
   * Píxeles de una utilidad numérica de Tailwind (`size-9`, `pr-12`) con la raíz a
   * 16px. Se lee del `className` **renderizado** y no de una constante del módulo:
   * así el invariante cae si alguien agranda el botón o encoge la reserva, que es
   * exactamente la regresión que este test existe para cazar.
   */
  function px(className: string, utility: RegExp): number {
    const match = className.match(utility);
    if (!match) {
      throw new Error(`sin la utilidad ${utility} en «${className}»`);
    }
    return Number(match[1]) * 4;
  }

  it("en la esquina el panel reserva la columna del botón, con separación", () => {
    render(
      <InfoDisclosure variant="corner" label="Más información" id="notes">
        <p>Nota larga</p>
      </InfoDisclosure>,
    );
    const trigger = screen.getByRole("button", { name: "Más información" });
    fireEvent.click(trigger);

    const panel = screen.getByText("Nota larga").parentElement!;
    // jsdom no calcula layout, así que no se puede medir geometría; lo que sí se
    // puede fijar es la aritmética del contrato: la columna reservada (`pr-12`) tiene
    // que cubrir el ancho del disparador (`size-9`) y dejar al menos 12px de aire.
    const reservado = px(panel.className, /\bpr-(\d+)\b/);
    const disparador = px(trigger.className, /\bsize-(\d+)\b/);
    expect(reservado - disparador).toBeGreaterThanOrEqual(12);
    // La reserva se compone aparte de `px-3` para no depender del orden en que
    // Tailwind emita las dos utilidades de padding-right.
    expect(panel.className).not.toMatch(/\bpx-3\b/);
  });

  it("en el flujo el panel va debajo, sin reservar columna", () => {
    render(
      <InfoDisclosure label="Más información" id="notes">
        <p>Nota larga</p>
      </InfoDisclosure>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Más información" }));

    const panel = screen.getByText("Nota larga").parentElement!;
    expect(panel.className).toMatch(/\bpx-3\b/);
    expect(panel.className).not.toMatch(/\bpr-12\b/);
  });
});
