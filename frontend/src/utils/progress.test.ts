import { describe, expect, it } from "vitest";
import {
  bucketLabel,
  eventLabel,
  formatAverage,
  formatScore,
  pronunciationLevelLabel,
} from "./progress";

describe("formatScore", () => {
  it("rounds to an integer", () => {
    expect(formatScore(95)).toBe("95");
    expect(formatScore(88.4)).toBe("88");
    expect(formatScore(82.6)).toBe("83");
  });

  it("renders a dash for null", () => {
    expect(formatScore(null)).toBe("—");
  });
});

describe("formatAverage", () => {
  it("keeps one decimal when needed", () => {
    expect(formatAverage(82.5)).toBe("82.5");
    expect(formatAverage(90.25)).toBe("90.3");
  });

  it("drops the decimal when it is an integer", () => {
    expect(formatAverage(90)).toBe("90");
    expect(formatAverage(88.0)).toBe("88");
  });

  it("renders a dash for null", () => {
    expect(formatAverage(null)).toBe("—");
  });
});

describe("pronunciationLevelLabel", () => {
  it("maps each level to a Spanish label", () => {
    expect(pronunciationLevelLabel("good")).toBe("Muy bien");
    expect(pronunciationLevelLabel("fair")).toBe("Aceptable");
    expect(pronunciationLevelLabel("needs_practice")).toBe("Sigue practicando");
  });

  it("renders a dash for null", () => {
    expect(pronunciationLevelLabel(null)).toBe("—");
  });
});

describe("bucketLabel", () => {
  it("maps each bucket to a Spanish label", () => {
    expect(bucketLabel("day")).toBe("Día");
    expect(bucketLabel("week")).toBe("Semana");
    expect(bucketLabel("month")).toBe("Mes");
  });
});

describe("eventLabel", () => {
  it("maps each event type to a Spanish label", () => {
    expect(eventLabel("message")).toBe("Mensaje");
    expect(eventLabel("exercise")).toBe("Ejercicio");
    expect(eventLabel("correction")).toBe("Corrección");
    expect(eventLabel("pronunciation")).toBe("Pronunciación");
    expect(eventLabel("conversation")).toBe("Conversación");
  });
});
