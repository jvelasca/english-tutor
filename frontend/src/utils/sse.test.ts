import { describe, expect, it } from "vitest";
import { parseSseLine } from "./sse";

describe("parseSseLine", () => {
  it("parses a content event", () => {
    expect(parseSseLine('data: {"content":"Hi"}')).toEqual({ content: "Hi" });
  });

  it("parses a done event", () => {
    expect(parseSseLine('data: {"done":true}')).toEqual({ done: true });
  });

  it("parses an error event", () => {
    expect(parseSseLine('data: {"error":"boom"}')).toEqual({ error: "boom" });
  });

  it("ignores non-data lines", () => {
    expect(parseSseLine("")).toBeNull();
    expect(parseSseLine("event: message")).toBeNull();
  });

  it("returns null on invalid JSON", () => {
    expect(parseSseLine("data: not-json")).toBeNull();
  });
});
