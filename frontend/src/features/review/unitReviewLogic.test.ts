import { describe, expect, it } from "vitest";
import type { UnitReviewPlanUnit } from "../../types/api";
import {
  countReviewableUnits,
  formatPercent,
  hasReviewableWindow,
  isReviewableWindowState,
  optionLetter,
  windowStateTone,
} from "./unitReviewLogic";

function unitWithStates(
  windows: Array<{ window_days: number; state: string }>,
): UnitReviewPlanUnit {
  return {
    level_id: "a1",
    unit_id: "a1-u1",
    module_id: "m1",
    module_title: "Module",
    title: "Unit",
    objectives_total: 1,
    objectives_mastered: 1,
    completed: true,
    anchor: "2026-01-01T00:00:00Z",
    windows: windows.map((w) => ({
      window_days: w.window_days,
      due_at: "2026-01-08T00:00:00Z",
      state: w.state as UnitReviewPlanUnit["windows"][number]["state"],
    })),
  };
}

describe("unitReviewLogic (V3.16)", () => {
  it("solo due_now y failed son ventanas repasables", () => {
    expect(isReviewableWindowState("due_now")).toBe(true);
    expect(isReviewableWindowState("failed")).toBe(true);
    expect(isReviewableWindowState("upcoming")).toBe(false);
    expect(isReviewableWindowState("passed")).toBe(false);
  });

  it("una unidad es repasable si alguna ventana lo es", () => {
    expect(hasReviewableWindow(unitWithStates([{ window_days: 7, state: "passed" }]))).toBe(false);
    expect(
      hasReviewableWindow(
        unitWithStates([
          { window_days: 7, state: "passed" },
          { window_days: 30, state: "due_now" },
        ]),
      ),
    ).toBe(true);
    expect(
      hasReviewableWindow(
        unitWithStates([{ window_days: 90, state: "failed" }]),
      ),
    ).toBe(true);
  });

  it("el tono de estado mapea a verde/ámbar/rojo/neutro", () => {
    expect(windowStateTone("passed")).toBe("passed");
    expect(windowStateTone("due_now")).toBe("due_now");
    expect(windowStateTone("failed")).toBe("failed");
    expect(windowStateTone("upcoming")).toBe("muted");
  });

  it("formatPercent redondea la fracción 0..1 a porcentaje entero", () => {
    expect(formatPercent(0.7)).toBe("70%");
    expect(formatPercent(1)).toBe("100%");
    expect(formatPercent(0)).toBe("0%");
    expect(formatPercent(0.666)).toBe("67%");
  });

  it("optionLetter numera las opciones A, B, C…", () => {
    expect(optionLetter(0)).toBe("A");
    expect(optionLetter(1)).toBe("B");
    expect(optionLetter(2)).toBe("C");
  });

  it("countReviewableUnits cuenta solo unidades con ventana pendiente", () => {
    const units = [
      unitWithStates([{ window_days: 7, state: "passed" }]),
      unitWithStates([{ window_days: 30, state: "due_now" }]),
      unitWithStates([{ window_days: 90, state: "failed" }]),
      unitWithStates([
        { window_days: 7, state: "passed" },
        { window_days: 30, state: "passed" },
        { window_days: 90, state: "passed" },
      ]),
    ];
    expect(countReviewableUnits(units)).toBe(2);
    expect(countReviewableUnits([])).toBe(0);
  });
});
