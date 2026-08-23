import { describe, expect, it } from "vitest";
import { resolveInitialTheme } from "./theme";

describe("resolveInitialTheme", () => {
  it("prioritises a stored light theme over the system preference", () => {
    expect(resolveInitialTheme("light", "dark")).toBe("light");
  });

  it("prioritises a stored dark theme over the system preference", () => {
    expect(resolveInitialTheme("dark", "light")).toBe("dark");
  });

  it("falls back to a light system preference when nothing is stored", () => {
    expect(resolveInitialTheme(null, "light")).toBe("light");
  });

  it("falls back to a dark system preference when nothing is stored", () => {
    expect(resolveInitialTheme(null, "dark")).toBe("dark");
  });

  it("ignores invalid stored values and uses the system preference", () => {
    expect(resolveInitialTheme("sepia", "dark")).toBe("dark");
    expect(resolveInitialTheme("", "light")).toBe("light");
  });
});
