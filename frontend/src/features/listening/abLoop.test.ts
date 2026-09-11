import { describe, expect, it } from "vitest";

import {
  EMPTY_AB_LOOP,
  MIN_AB_LOOP_SECONDS,
  armLoop,
  canClear,
  clearLoop,
  loopBounds,
  loopFromSegment,
  toggleMark,
  type AbLoopState,
} from "./abLoop";

/**
 * Tests de la máquina de estados del bucle A/B (V3.52.1). Es un módulo puro: se
 * verifica que las transiciones (marcar, armar bucle, quitar marca, quitar
 * bucle, reflejar un bucle externo) mantienen UI y controller coherentes.
 */
describe("abLoop", () => {
  it("toggleMark fija A la primera vez y lo limpia la segunda", () => {
    const marked = toggleMark(EMPTY_AB_LOOP, 3.2);
    expect(marked).toEqual({ markStart: 3.2, loopEnd: null, looping: false });
    // Quitar la marca desarma también el bucle (no deja un residuo activo).
    const looped: AbLoopState = { markStart: 3.2, loopEnd: 5, looping: true };
    expect(toggleMark(looped, 9)).toEqual(EMPTY_AB_LOOP);
  });

  it("toggleMark ignora instantes inválidos", () => {
    expect(toggleMark(EMPTY_AB_LOOP, Number.NaN)).toEqual(EMPTY_AB_LOOP);
    expect(toggleMark(EMPTY_AB_LOOP, -1)).toEqual(EMPTY_AB_LOOP);
    expect(toggleMark(EMPTY_AB_LOOP, null)).toEqual(EMPTY_AB_LOOP);
  });

  it("armLoop exige marca y un segmento suficientemente largo", () => {
    expect(armLoop(EMPTY_AB_LOOP, 5)).toBeNull();
    const marked: AbLoopState = { markStart: 2, loopEnd: null, looping: false };
    expect(armLoop(marked, 2 + MIN_AB_LOOP_SECONDS / 2)).toBeNull();
    expect(armLoop(marked, 4)).toEqual({
      markStart: 2,
      loopEnd: 4,
      looping: true,
    });
  });

  it("clearLoop desarma todo y canClear refleja el estado", () => {
    expect(clearLoop()).toEqual(EMPTY_AB_LOOP);
    expect(canClear(EMPTY_AB_LOOP)).toBe(false);
    expect(canClear({ markStart: 1, loopEnd: null, looping: false })).toBe(true);
    expect(canClear({ markStart: null, loopEnd: null, looping: true })).toBe(
      true,
    );
  });

  it("loopFromSegment refleja un bucle armado fuera de los botones A/B", () => {
    expect(loopFromSegment(1.05, 2.4)).toEqual({
      markStart: 1.05,
      loopEnd: 2.4,
      looping: true,
    });
    expect(loopFromSegment(2, 2.01)).toEqual(EMPTY_AB_LOOP);
    expect(loopFromSegment(null, 2)).toEqual(EMPTY_AB_LOOP);
  });

  it("loopBounds devuelve los límites solo con bucle armado", () => {
    expect(loopBounds(EMPTY_AB_LOOP)).toBeNull();
    expect(
      loopBounds({ markStart: 2, loopEnd: 4, looping: true }),
    ).toEqual([2, 4]);
    expect(
      loopBounds({ markStart: 2, loopEnd: 4, looping: false }),
    ).toBeNull();
  });
});
