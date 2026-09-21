import { describe, expect, it } from "vitest";
import { isValidPin, PIN_MAX_DIGITS, PIN_MIN_DIGITS, sanitizePinInput } from "./pin";

/**
 * Espejo de la validación del backend (V3.76). Si los dos lados se separan, la
 * UI ofrece un botón que el servidor rechaza con 400, o peor: deja pasar algo
 * que el servidor considera otro PIN distinto.
 */
describe("forma del PIN (V3.76)", () => {
  it("acepta de 4 a 6 dígitos", () => {
    expect(PIN_MIN_DIGITS).toBe(4);
    expect(PIN_MAX_DIGITS).toBe(6);
    for (const pin of ["0000", "1234", "12345", "123456"]) {
      expect(isValidPin(pin)).toBe(true);
    }
  });

  it("rechaza lo que no tiene esa forma", () => {
    for (const pin of ["", "123", "1234567", "12a4", "12 34", "+1234"]) {
      expect(isValidPin(pin)).toBe(false);
    }
  });

  it("el filtro de tecleo deja solo dígitos y corta a 6", () => {
    expect(sanitizePinInput("12a34b")).toBe("1234");
    expect(sanitizePinInput("1234567890")).toBe("123456");
    expect(sanitizePinInput("a-b c")).toBe("");
  });
});
