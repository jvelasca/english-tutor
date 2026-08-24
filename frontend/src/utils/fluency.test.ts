import { describe, expect, it } from "vitest";
import { fluencyLevelLabel, wpmLabel } from "./fluency";

describe("wpmLabel", () => {
  it("formatea las palabras por minuto", () => {
    expect(wpmLabel(60)).toBe("60 palabras/min");
    expect(wpmLabel(120.4)).toBe("120 palabras/min");
  });

  it("devuelve guion para null", () => {
    expect(wpmLabel(null)).toBe("—");
  });
});

describe("fluencyLevelLabel", () => {
  it("mapea cada nivel a su etiqueta", () => {
    expect(fluencyLevelLabel("fluent")).toBe("Fluido");
    expect(fluencyLevelLabel("good")).toBe("Buen ritmo");
    expect(fluencyLevelLabel("slow")).toBe("Lento");
  });

  it("devuelve guion para niveles desconocidos", () => {
    expect(fluencyLevelLabel("—")).toBe("—");
  });
});
