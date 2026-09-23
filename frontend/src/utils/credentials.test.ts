/**
 * Forma de la contraseña y del email (V3.81), espejo de `services/credentials.py`.
 *
 * Lo que se fija aquí no es «valida strings»: es que la UI **no ofrezca un botón que
 * el servidor va a rechazar** y que no se invente reglas propias. Por eso el último
 * test comprueba lo que este módulo **no** hace: `12345678` tiene forma aceptable y
 * aun así el servidor lo rechaza (su lista de obvias vive en el backend, y decirla
 * aquí sería duplicar una lista que se desincroniza).
 */
import { describe, expect, it } from "vitest";
import {
  PASSWORD_MAX_CHARS,
  PASSWORD_MIN_CHARS,
  isPlausibleEmail,
  isPlausiblePassword,
} from "./credentials";

describe("forma de la contraseña", () => {
  it("acepta una frase de longitud razonable", () => {
    expect(isPlausiblePassword("caballo-bateria-grapa")).toBe(true);
  });

  it("rechaza por debajo del mínimo y por encima del máximo", () => {
    expect(isPlausiblePassword("a".repeat(PASSWORD_MIN_CHARS - 1))).toBe(false);
    expect(isPlausiblePassword("a".repeat(PASSWORD_MAX_CHARS + 1))).toBe(false);
    // Exactamente el mínimo, y con algo de variedad: sí pasa.
    expect(
      isPlausiblePassword("a".repeat(PASSWORD_MIN_CHARS - 1) + "b"),
    ).toBe(true);
  });

  it("rechaza espacios en los extremos, que casi siempre son un pegote", () => {
    expect(isPlausiblePassword(" caballo-bateria")).toBe(false);
    expect(isPlausiblePassword("caballo-bateria ")).toBe(false);
    expect(isPlausiblePassword("caballo bateria")).toBe(true);
  });

  it("rechaza la contraseña de un solo carácter repetido", () => {
    expect(isPlausiblePassword("aaaaaaaa")).toBe(false);
  });

  it("no juzga si es obvia: esa lista es del servidor", () => {
    expect(isPlausiblePassword("12345678")).toBe(true);
  });
});

describe("forma del email", () => {
  it("acepta uno corriente y en minúsculas o mayúsculas", () => {
    expect(isPlausibleEmail("ana@ejemplo.es")).toBe(true);
    expect(isPlausibleEmail("Ana.Velasco@Ejemplo.ES")).toBe(true);
  });

  it("rechaza lo que no puede ser un email", () => {
    expect(isPlausibleEmail("ana")).toBe(false);
    expect(isPlausibleEmail("ana@ejemplo")).toBe(false);
    expect(isPlausibleEmail("ana@@ejemplo.es")).toBe(false);
    expect(isPlausibleEmail("@ejemplo.es")).toBe(false);
    expect(isPlausibleEmail("ana@.es")).toBe(false);
    expect(isPlausibleEmail("a@b")).toBe(false);
  });

  it("rechaza espacios en los extremos y longitudes imposibles", () => {
    expect(isPlausibleEmail(" ana@ejemplo.es")).toBe(false);
    expect(isPlausibleEmail("ana@ejemplo.es ")).toBe(false);
    expect(isPlausibleEmail("a".repeat(300) + "@ejemplo.es")).toBe(false);
  });
});
