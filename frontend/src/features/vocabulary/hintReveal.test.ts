import { describe, expect, it } from "vitest";

import { mnemonicSlice } from "./hintReveal";

describe("mnemonicSlice", () => {
  const phrase = "la tercera sílaba son los dientes";

  it("empieza vacío y descubre la frase por tercios", () => {
    expect(mnemonicSlice(phrase, 0)).toBe("");
    expect(mnemonicSlice(phrase, 1)).toBe("la tercera");
    expect(mnemonicSlice(phrase, 2)).toBe("la tercera sílaba son");
    expect(mnemonicSlice(phrase, 3)).toBe(phrase);
    expect(mnemonicSlice(phrase, 4)).toBe(phrase);
  });

  it("una sola palabra se descubre entera en el primer paso", () => {
    expect(mnemonicSlice("dientes", 1)).toBe("dientes");
  });
});
