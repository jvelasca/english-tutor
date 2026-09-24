import { describe, expect, it } from "vitest";
import { nextDefaultUserName } from "./users";

describe("nextDefaultUserName", () => {
  it("returns the base name when there are no users", () => {
    expect(nextDefaultUserName([])).toBe("Usuario");
  });

  it("returns the base name when it is not taken", () => {
    expect(nextDefaultUserName(["Ana", "Luis"])).toBe("Usuario");
  });

  it("appends a numeric suffix when the base name is taken", () => {
    expect(nextDefaultUserName(["Usuario"])).toBe("Usuario 2");
  });

  it("skips suffixes already in use", () => {
    expect(nextDefaultUserName(["Usuario", "Usuario 2"])).toBe("Usuario 3");
  });
});
