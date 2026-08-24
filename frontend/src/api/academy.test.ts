import { afterEach, describe, expect, it, vi } from "vitest";
import { getLevels, recordAttempts, submitExam, submitPlacement } from "./academy";

function mockJsonFetch(data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok: true, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("academy api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getLevels incluye user_id en la query", async () => {
    const fn = mockJsonFetch({ levels: [] });
    await getLevels("u1");
    expect(fn.mock.calls[0][0]).toBe("/api/academy/levels?user_id=u1");
  });

  it("submitExam envía answers y user_id", async () => {
    const fn = mockJsonFetch({ passed: true, skills: {}, failed_skills: [] });
    await submitExam("u1", "a1", { "a1f-01": 1 });
    const url = fn.mock.calls[0][0] as string;
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(url).toBe("/api/academy/exam/a1/submit?user_id=u1");
    expect(body).toEqual({ answers: { "a1f-01": 1 } });
  });

  it("submitPlacement envía answers", async () => {
    const fn = mockJsonFetch({ level: "A1", confidence: 0.7 });
    await submitPlacement("u1", { "pl-01": 0 });
    const url = fn.mock.calls[0][0] as string;
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(url).toBe("/api/academy/placement/submit?user_id=u1");
    expect(body).toEqual({ answers: { "pl-01": 0 } });
  });

  it("recordAttempts envía level/objective y results", async () => {
    const fn = mockJsonFetch({ recorded: 2 });
    await recordAttempts("u1", "a1", "o1", [
      { skill: "grammar", result: "correct" },
      { skill: "vocabulary", result: "incorrect" },
    ]);
    const url = fn.mock.calls[0][0] as string;
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(url).toBe("/api/academy/attempts?user_id=u1");
    expect(body).toEqual({
      level_id: "a1",
      objective_id: "o1",
      results: [
        { skill: "grammar", result: "correct" },
        { skill: "vocabulary", result: "incorrect" },
      ],
    });
  });
});
