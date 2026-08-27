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
  it("maps each level to an English label", () => {
    expect(pronunciationLevelLabel("good")).toBe("Good");
    expect(pronunciationLevelLabel("fair")).toBe("Fair");
    expect(pronunciationLevelLabel("needs_practice")).toBe("Needs practice");
  });

  it("renders a dash for null", () => {
    expect(pronunciationLevelLabel(null)).toBe("—");
  });
});

describe("bucketLabel", () => {
  it("maps each bucket to an English label", () => {
    expect(bucketLabel("day")).toBe("Day");
    expect(bucketLabel("week")).toBe("Week");
    expect(bucketLabel("month")).toBe("Month");
  });
});

describe("eventLabel", () => {
  it("maps each event type to an English label", () => {
    expect(eventLabel("message")).toBe("Message");
    expect(eventLabel("exercise")).toBe("Exercise");
    expect(eventLabel("correction")).toBe("Correction");
    expect(eventLabel("pronunciation")).toBe("Pronunciation");
    expect(eventLabel("conversation")).toBe("Conversation");
  });
});
