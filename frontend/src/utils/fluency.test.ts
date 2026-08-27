import { describe, expect, it } from "vitest";
import { fluencyLevelLabel, wpmLabel } from "./fluency";

describe("wpmLabel", () => {
  it("formatea las palabras por minuto", () => {
    expect(wpmLabel(60)).toBe("60 words/min");
    expect(wpmLabel(120.4)).toBe("120 words/min");
  });

  it("devuelve guion para null", () => {
    expect(wpmLabel(null)).toBe("—");
  });
});

describe("fluencyLevelLabel", () => {
  it("mapea cada nivel a su etiqueta", () => {
    expect(fluencyLevelLabel("fluent")).toBe("Fluent");
    expect(fluencyLevelLabel("good")).toBe("Good pace");
    expect(fluencyLevelLabel("slow")).toBe("Slow");
  });

  it("devuelve guion para niveles desconocidos", () => {
    expect(fluencyLevelLabel("—")).toBe("—");
  });
});
