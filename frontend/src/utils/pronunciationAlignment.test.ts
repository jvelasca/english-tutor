import { describe, expect, it } from "vitest";
import { alignWords } from "./pronunciationAlignment";

describe("alignWords (paridad con backend services/phonetics.word_alignment)", () => {
  it("exact match", () => {
    const r = alignWords("Hello world", "Hello world");
    expect(r.expected.map((w) => [w.word, w.state])).toEqual([
      ["Hello", "ok"],
      ["world", "ok"],
    ]);
    expect(r.extras).toEqual([]);
  });

  it("substitution", () => {
    const r = alignWords("I have twenty years old", "I am twenty years old");
    expect(r.expected.map((w) => [w.word, w.state])).toEqual([
      ["I", "ok"],
      ["have", "sub"],
      ["twenty", "ok"],
      ["years", "ok"],
      ["old", "ok"],
    ]);
    expect(r.expected[1].heard).toBe("am");
  });

  it("missing words", () => {
    const r = alignWords("Hello world", "Hello");
    expect(r.expected.map((w) => [w.word, w.state])).toEqual([
      ["Hello", "ok"],
      ["world", "miss"],
    ]);
    expect(r.extras).toEqual([]);
  });

  it("extra words", () => {
    const r = alignWords("Hello", "Hello world");
    expect(r.expected).toEqual([{ word: "Hello", state: "ok" }]);
    expect(r.extras).toEqual(["world"]);
  });

  it("preserves punctuation in displayed words", () => {
    const r = alignWords("Book a table, please.", "Book the table, please.");
    expect(r.expected.map((w) => w.word)).toEqual([
      "Book",
      "a",
      "table,",
      "please.",
    ]);
    expect(r.expected.find((w) => w.state === "sub")?.word).toBe("a");
  });

  it("duplicated word with one substitution keeps counts consistent", () => {
    // Aunque la colocación exacta con repeticiones es esquiva, el recuento de
    // estados debe coincidir con el breakdown del backend (1 ok + 1 sub).
    const r = alignWords("look look", "look see");
    const counts = r.expected.reduce<Record<string, number>>((acc, w) => {
      acc[w.state] = (acc[w.state] ?? 0) + 1;
      return acc;
    }, {});
    expect(counts.ok).toBe(1);
    expect(counts.sub).toBe(1);
  });
});
