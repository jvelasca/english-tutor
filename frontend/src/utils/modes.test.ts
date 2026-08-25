import { describe, expect, it } from "vitest";
import { MODES, isTutorMode, modeCefrBand, modeCefrLevel } from "./modes";

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

  it("maps each mode to its CEFR band", () => {
    expect(modeCefrBand("conversation")).toBe("fluency");
    expect(modeCefrBand("grammar")).toBe("grammar");
    expect(modeCefrBand("exercises")).toBe("vocabulary");
    expect(modeCefrBand("pronunciation")).toBe("pronunciation");
  });

  it("modeCefrLevel returns the level from the bands", () => {
    const bands = {
      vocabulary: "A1",
      grammar: "A2",
      fluency: "B1",
      pronunciation: "A2",
      listening: "A1",
    };
    expect(modeCefrLevel("grammar", bands)).toBe("A2");
    expect(modeCefrLevel("conversation", bands)).toBe("B1");
  });

  it("modeCefrLevel returns null without bands or level", () => {
    expect(modeCefrLevel("grammar", null)).toBeNull();
    expect(modeCefrLevel("grammar", { vocabulary: "", grammar: "" } as never)).toBeNull();
  });
});
