import { describe, expect, it } from "vitest";
import { deriveTitle } from "./title";

describe("deriveTitle", () => {
  it("returns the default when there is no user message", () => {
    expect(deriveTitle([])).toBe("Nueva conversación");
  });

  it("uses the first user message", () => {
    const messages = [
      { role: "assistant" as const, content: "Hi!" },
      { role: "user" as const, content: "Hello" },
    ];
    expect(deriveTitle(messages)).toBe("Hello");
  });

  it("truncates long titles to 40 chars plus ellipsis", () => {
    const messages = [{ role: "user" as const, content: "a".repeat(60) }];
    const title = deriveTitle(messages);
    expect(title.endsWith("…")).toBe(true);
    expect(title.length).toBe(41);
  });
});
