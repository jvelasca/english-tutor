import { describe, expect, it } from "vitest";
import { fluencyLevelLabel, wpmLabel } from "./fluency";
import { translate } from "./i18n";

// El segundo argumento es el traductor de la UI; en tests usamos el idioma EN.
const t = (k: string) => translate("en", k);

describe("wpmLabel", () => {
  it("formatea palabras por minuto con signo localizado", () => {
    expect(wpmLabel(60, t)).toBe("60 words/min");
    expect(wpmLabel(120.4, t)).toBe("120 words/min");
  });

  it("devuelve guión cuando no hay dato", () => {
    expect(wpmLabel(null, t)).toBe("—");
  });
});

describe("fluencyLevelLabel", () => {
  it("etiqueta cada nivel de fluidez", () => {
    expect(fluencyLevelLabel("fluent", t)).toBe("Fluent");
    expect(fluencyLevelLabel("good", t)).toBe("Good pace");
    expect(fluencyLevelLabel("slow", t)).toBe("Slow");
  });

  it("devuelve guión para niveles desconocidos", () => {
    expect(fluencyLevelLabel("—", t)).toBe("—");
  });
});
