import { describe, expect, it } from "vitest";
import { bandLabel, cefrLabel, cefrTone } from "./cefr";

describe("cefrTone", () => {
  it("maps A1/A2 to basic", () => {
    expect(cefrTone("A1")).toBe("basic");
    expect(cefrTone("A2")).toBe("basic");
  });

  it("maps B1/B2 to intermediate", () => {
    expect(cefrTone("B1")).toBe("intermediate");
    expect(cefrTone("B2")).toBe("intermediate");
  });

  it("maps C1/C2 to advanced", () => {
    expect(cefrTone("C1")).toBe("advanced");
    expect(cefrTone("C2")).toBe("advanced");
  });

  it("falls back to basic for unknown levels", () => {
    expect(cefrTone("Z9")).toBe("basic");
  });
});

describe("cefrLabel", () => {
  it("maps each level to an English label", () => {
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
