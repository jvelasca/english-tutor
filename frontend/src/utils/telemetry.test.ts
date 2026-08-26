import { describe, expect, it } from "vitest";
import { turnTelemetry } from "./telemetry";

describe("turnTelemetry", () => {
  it("calcula duration y latency con todas las entradas", () => {
    const result = turnTelemetry({
      sentAt: 10000,
      composeStartedAt: 8000,
      lastAssistantAt: 7500,
    });
    expect(result.duration_ms).toBe(2000);
    expect(result.latency_ms).toBe(500);
  });

  it("devuelve null cuando no hay composeStartedAt", () => {
    const result = turnTelemetry({
      sentAt: 10000,
      composeStartedAt: null,
      lastAssistantAt: 7500,
    });
    expect(result.duration_ms).toBeNull();
    // latency usa sentAt como inicio de composición.
    expect(result.latency_ms).toBe(2500);
  });

  it("devuelve null cuando no hay lastAssistantAt", () => {
    const result = turnTelemetry({
      sentAt: 10000,
      composeStartedAt: 8000,
      lastAssistantAt: null,
    });
    expect(result.duration_ms).toBe(2000);
    expect(result.latency_ms).toBeNull();
  });

  it("devuelve null en ambos cuando no hay referencias", () => {
    const result = turnTelemetry({
      sentAt: 10000,
      composeStartedAt: null,
      lastAssistantAt: null,
    });
    expect(result.duration_ms).toBeNull();
    expect(result.latency_ms).toBeNull();
  });

  it("clampa a 0 los valores negativos", () => {
    const result = turnTelemetry({
      sentAt: 1000,
      composeStartedAt: 1500, // negativo
      lastAssistantAt: 2000, // negativo
    });
    expect(result.duration_ms).toBe(0);
    expect(result.latency_ms).toBe(0);
  });

  it("rechaza NaN en duration", () => {
    const result = turnTelemetry({
      sentAt: Number.NaN,
      composeStartedAt: 8000,
      lastAssistantAt: 7500,
    });
    expect(result.duration_ms).toBeNull();
    // latency usa composeStartedAt (presente), así que es finita.
    expect(result.latency_ms).toBe(500);
  });

  it("rechaza NaN en latency cuando no hay composeStartedAt", () => {
    const result = turnTelemetry({
      sentAt: Number.NaN,
      composeStartedAt: null,
      lastAssistantAt: 7500,
    });
    expect(result.duration_ms).toBeNull();
    expect(result.latency_ms).toBeNull();
  });

  it("redondea al entero más cercano", () => {
    const result = turnTelemetry({
      sentAt: 10000.6,
      composeStartedAt: 8000.4,
      lastAssistantAt: 7500,
    });
    expect(result.duration_ms).toBe(2000);
    expect(result.latency_ms).toBe(500);
  });
});
