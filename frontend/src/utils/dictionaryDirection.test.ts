import { describe, expect, it } from "vitest";
import {
  DIRECTION_EXAMPLES,
  DIRECTION_OPTIONS,
  directionClass,
  directionLabelKey,
} from "./dictionaryDirection";

describe("directionClass", () => {
  it("devuelve la clase estatica de cada sentido", () => {
    expect(directionClass("en-es")).toBe("dir-en-es");
    expect(directionClass("es-en")).toBe("dir-es-en");
  });

  it("cubre las dos opciones declaradas por DIRECTION_OPTIONS", () => {
    for (const option of DIRECTION_OPTIONS) {
      expect(directionClass(option.id)).toBe(`dir-${option.id}`);
    }
  });

  it("declara una etiqueta i18n por direccion, sin repetir", () => {
    const keys = DIRECTION_OPTIONS.map((option) => option.labelKey);
    expect(new Set(keys).size).toBe(keys.length);
    for (const option of DIRECTION_OPTIONS) {
      expect(directionLabelKey(option.id)).toBe(option.labelKey);
    }
  });
});

describe("DIRECTION_EXAMPLES", () => {
  it("ofrece ejemplos en las dos direcciones y en la lengua de la que se busca", () => {
    expect(DIRECTION_EXAMPLES["en-es"].length).toBeGreaterThan(0);
    expect(DIRECTION_EXAMPLES["es-en"].length).toBeGreaterThan(0);
    // El ejemplo de ES→EN se teclea en espanol; el de EN→ES, en ingles. Se
    // comprueba con un caracter que solo aparece en una de las dos lenguas.
    expect(DIRECTION_EXAMPLES["es-en"]).toContain("casa");
    expect(DIRECTION_EXAMPLES["en-es"]).toContain("travel");
  });

  it("no repite ejemplos dentro de la misma direccion", () => {
    for (const words of Object.values(DIRECTION_EXAMPLES)) {
      expect(new Set(words).size).toBe(words.length);
    }
  });
});
