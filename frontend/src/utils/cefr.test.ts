import { describe, expect, it } from "vitest";
import {
  bandLabel,
  bandToLevelKey,
  cefrLabel,
  cefrLevelKey,
  levelClass,
  LEVEL_KEYS,
} from "./cefr";

describe("cefrLevelKey", () => {
  it("mapea cada nivel a su propia clave (siete pasos, no tres tramos)", () => {
    expect(cefrLevelKey("Pre-A1")).toBe("pre-a1");
    expect(cefrLevelKey("A1")).toBe("a1");
    expect(cefrLevelKey("A2")).toBe("a2");
    expect(cefrLevelKey("B1")).toBe("b1");
    expect(cefrLevelKey("B2")).toBe("b2");
    expect(cefrLevelKey("C1")).toBe("c1");
    expect(cefrLevelKey("C2")).toBe("c2");
  });

  it("tolera mayusculas, espacios y separadores", () => {
    expect(cefrLevelKey("pre a1")).toBe("pre-a1");
    expect(cefrLevelKey("PRE_A1")).toBe("pre-a1");
    expect(cefrLevelKey(" b1 ")).toBe("b1");
  });

  it("trata la ausencia de dato como unknown, sin inventar nivel", () => {
    expect(cefrLevelKey("—")).toBe("unknown");
    expect(cefrLevelKey("")).toBe("unknown");
    expect(cefrLevelKey("Z9")).toBe("unknown");
  });

  it("no se rompe con valores nulos", () => {
    expect(cefrLevelKey(null as unknown as string)).toBe("unknown");
    expect(cefrLevelKey(undefined as unknown as string)).toBe("unknown");
  });

  it("acepta una posicion numerica (escala 0-6) ademas de la etiqueta", () => {
    expect(cefrLevelKey(2.4)).toBe("a2");
    expect(cefrLevelKey(4)).toBe("b2");
    expect(cefrLevelKey(Number.NaN)).toBe("unknown");
  });
});

describe("levelClass", () => {
  it("devuelve la clase estatica de la rampa", () => {
    expect(levelClass("A2")).toBe("lv-a2");
    expect(levelClass("Pre-A1")).toBe("lv-pre-a1");
    expect(levelClass("—")).toBe("lv-unknown");
  });

  it("cubre los siete pasos declarados por LEVEL_KEYS", () => {
    for (const key of LEVEL_KEYS) {
      expect(levelClass(key)).toBe(`lv-${key}`);
    }
  });
});

describe("bandToLevelKey", () => {
  it("reparte la escala numerica 0-6 en los siete pasos", () => {
    expect(bandToLevelKey(0)).toBe("pre-a1");
    expect(bandToLevelKey(1)).toBe("a1");
    expect(bandToLevelKey(2)).toBe("a2");
    expect(bandToLevelKey(3)).toBe("b1");
    expect(bandToLevelKey(4)).toBe("b2");
    expect(bandToLevelKey(5)).toBe("c1");
    expect(bandToLevelKey(6)).toBe("c2");
  });

  it("redondea al paso mas cercano", () => {
    expect(bandToLevelKey(2.4)).toBe("a2");
    expect(bandToLevelKey(2.6)).toBe("b1");
  });

  it("recorta fuera de rango y descarta valores no finitos", () => {
    expect(bandToLevelKey(-3)).toBe("pre-a1");
    expect(bandToLevelKey(99)).toBe("c2");
    expect(bandToLevelKey(Number.NaN)).toBe("unknown");
    expect(bandToLevelKey(Number.POSITIVE_INFINITY)).toBe("unknown");
  });
});

describe("cefrLabel", () => {
  it("maps each level to an English label", () => {
    expect(cefrLabel("Pre-A1")).toBe("Pre-beginner");
    expect(cefrLabel("A1")).toBe("Beginner");
    expect(cefrLabel("A2")).toBe("Elementary");
    expect(cefrLabel("B1")).toBe("Intermediate");
    expect(cefrLabel("B2")).toBe("Upper-intermediate");
    expect(cefrLabel("C1")).toBe("Advanced");
    expect(cefrLabel("C2")).toBe("Mastery");
  });

  it("returns the raw value for unknown levels", () => {
    expect(cefrLabel("Z9")).toBe("Z9");
  });
});

describe("bandLabel", () => {
  it("mapea cada destreza a su etiqueta", () => {
    expect(bandLabel("vocabulary")).toBe("Vocabulary");
    expect(bandLabel("grammar")).toBe("Grammar");
    expect(bandLabel("pronunciation")).toBe("Pronunciation");
    expect(bandLabel("listening")).toBe("Listening");
    expect(bandLabel("speaking")).toBe("Speaking");
    expect(bandLabel("reading")).toBe("Reading");
    expect(bandLabel("writing")).toBe("Writing");
  });

  it("devuelve el valor crudo para destrezas desconocidas", () => {
    expect(bandLabel("spelling")).toBe("spelling");
  });
});
