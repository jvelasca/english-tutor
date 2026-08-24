import { describe, expect, it } from "vitest";
import {
  MAX_CHUNK_MS,
  MIN_SPEECH_MS,
  SILENCE_MS,
  SILENCE_THRESHOLD,
  rms,
  shouldEndUtterance,
} from "./vad";

describe("rms", () => {
  it("returns 0 for an empty buffer", () => {
    expect(rms(new Float32Array(0))).toBe(0);
    expect(rms(new Uint8Array(0))).toBe(0);
  });

  it("returns 0 for silent Float32 samples", () => {
    expect(rms(new Float32Array([0, 0, 0, 0]))).toBe(0);
  });

  it("computes the RMS of a Float32 signal", () => {
    expect(rms(new Float32Array([1, -1, 1, -1]))).toBeCloseTo(1);
  });

  it("returns 0 for Uint8 samples centered at 128", () => {
    expect(rms(new Uint8Array([128, 128, 128, 128]))).toBe(0);
  });

  it("normalizes a full-scale Uint8 signal to ~1", () => {
    expect(rms(new Uint8Array([255, 1, 255, 1]))).toBeCloseTo(127 / 128);
  });
});

describe("shouldEndUtterance", () => {
  it("does not end when there is no speech", () => {
    expect(shouldEndUtterance(false, 1000, 2500)).toBe(false);
  });

  it("does not end when silence has not started", () => {
    expect(shouldEndUtterance(true, null, 2500)).toBe(false);
  });

  it("does not end before SILENCE_MS has elapsed", () => {
    expect(shouldEndUtterance(true, 1000, 1000 + SILENCE_MS - 1)).toBe(false);
  });

  it("ends exactly at SILENCE_MS", () => {
    expect(shouldEndUtterance(true, 1000, 1000 + SILENCE_MS)).toBe(true);
  });

  it("ends after SILENCE_MS has elapsed", () => {
    expect(shouldEndUtterance(true, 1000, 1000 + SILENCE_MS + 500)).toBe(true);
  });
});

describe("constants", () => {
  it("exposes the expected VAD thresholds", () => {
    expect(SILENCE_THRESHOLD).toBe(0.02);
    expect(SILENCE_MS).toBe(1200);
    expect(MIN_SPEECH_MS).toBe(300);
    expect(MAX_CHUNK_MS).toBe(15000);
  });
});
