// @vitest-environment jsdom
/**
 * Vitest del desplegable informativo (V3.48.1): un único disparador «...» que
 * monta el panel solo cuando se abre y lo desmonta al cerrarlo.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { InfoDisclosure } from "./InfoDisclosure";

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
