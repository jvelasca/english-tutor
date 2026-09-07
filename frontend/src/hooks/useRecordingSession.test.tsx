// @vitest-environment jsdom
/**
 * Tests de V3.21 (V20-13): `useRecordingSession` (cronómetro + auto-stop).
 */
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRecordingSession } from "./useRecordingSession";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("useRecordingSession", () => {
  it("arranca el cronómetro al grabar y muestra mm:ss transcurrido", () => {
    const onAutoStop = vi.fn();
    const { result, rerender } = renderHook(
      (props: { recording: boolean }) =>
        useRecordingSession(props.recording, { maxSeconds: 3, onAutoStop }),
      { initialProps: { recording: false } },
    );
    rerender({ recording: true });
    act(() => vi.advanceTimersByTime(1250));
    expect(result.current.formatted).toBe("00:01");
    expect(result.current.remainingFormatted).toBe("00:02");
    act(() => vi.advanceTimersByTime(1000));
    expect(result.current.formatted).toBe("00:02");
  });

  it("invoca onAutoStop una sola vez al alcanzar el límite", () => {
    const onAutoStop = vi.fn();
    const { result, rerender } = renderHook(
      (props: { recording: boolean }) =>
        useRecordingSession(props.recording, { maxSeconds: 3, onAutoStop }),
      { initialProps: { recording: false } },
    );
    rerender({ recording: true });
    act(() => vi.advanceTimersByTime(4000));
    expect(onAutoStop).toHaveBeenCalledTimes(1);
    expect(result.current.elapsed).toBeGreaterThanOrEqual(3);
    // Siguen pasando ticks: el auto-stop no se repite en la misma sesión.
    act(() => vi.advanceTimersByTime(2000));
    expect(onAutoStop).toHaveBeenCalledTimes(1);
  });

  it("reinicia el contador al detener la grabación", () => {
    const onAutoStop = vi.fn();
    const { result, rerender } = renderHook(
      (props: { recording: boolean }) =>
        useRecordingSession(props.recording, { maxSeconds: 5, onAutoStop }),
      { initialProps: { recording: false } },
    );
    rerender({ recording: true });
    act(() => vi.advanceTimersByTime(2000));
    expect(result.current.elapsed).toBe(2);
    rerender({ recording: false });
    expect(result.current.elapsed).toBe(0);
    expect(result.current.formatted).toBe("00:00");
  });

  it("usa 120 s por defecto (máximo que acepta el backend)", () => {
    const { result } = renderHook(() => useRecordingSession(false));
    expect(result.current.limit).toBe(120);
  });
});
