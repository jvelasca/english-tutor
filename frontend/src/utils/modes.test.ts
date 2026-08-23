import { describe, expect, it } from "vitest";
import { MODES, isTutorMode } from "./modes";

describe("modes", () => {
  it("defines the four tutor modes", () => {
    expect(MODES.map((m) => m.id)).toEqual([
      "conversation",
      "grammar",
      "exercises",
      "pronunciation",
    ]);
  });

  it("isTutorMode validates known modes", () => {
    expect(isTutorMode("grammar")).toBe(true);
    expect(isTutorMode("bogus")).toBe(false);
  });
});
