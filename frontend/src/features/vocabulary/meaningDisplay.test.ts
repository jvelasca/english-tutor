import { describe, expect, it } from "vitest";

import { meaningLines } from "./meaningDisplay";

describe("meaningLines", () => {
  it("en la consulta inversa la glosa española precede al inglés", () => {
    const lines = meaningLines(
      { term: "saw", gloss: "herramienta de corte" },
      true,
    );
    expect(lines.title).toBe("herramienta de corte");
    expect(lines.titleLang).toBe("es");
    expect(lines.subtitle).toBe("saw");
    expect(lines.subtitleLang).toBe("en");
  });

  it("sin glosa el título sigue siendo el término", () => {
    const lines = meaningLines({ term: "saw", gloss: "" }, true);
    expect(lines.title).toBe("saw");
    expect(lines.subtitle).toBe("");
  });

  it("en EN→ES el término va primero y la glosa debajo", () => {
    const lines = meaningLines(
      { term: "sierra", gloss: "cutting tool" },
      false,
    );
    expect(lines.title).toBe("sierra");
    expect(lines.titleLang).toBe("es");
    expect(lines.subtitle).toBe("cutting tool");
  });
});
