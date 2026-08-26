import { afterEach, describe, expect, it, vi } from "vitest";
import {
  completeLesson,
  completeSessionStep,
  finishSpeakingAssessment,
  getGoal,
  getLevels,
  getSession,
  getSpeakingAssessment,
  getSpeakingDiagnostic,
  getSpeakingJourney,
  getSpeakingLevel,
  nextAdaptivePlacement,
  putGoal,
  recordAttempts,
  startAdaptivePlacement,
  startSpeakingAssessment,
  submitExam,
  submitObjectiveAssessment,
  submitPlacement,
  submitSpeakingAssessmentPart,
} from "./academy";

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

  it("startAdaptivePlacement llama a placement/start", async () => {
    const fn = mockJsonFetch({
      session_id: 7,
      next_item: null,
      placement_version: "v2",
    });
    await startAdaptivePlacement("u1");
    const url = fn.mock.calls[0][0] as string;
    const method = fn.mock.calls[0][1].method;
    expect(url).toBe("/api/academy/placement/start?user_id=u1");
    expect(method).toBe("POST");
  });

  it("nextAdaptivePlacement envía answers y session_id", async () => {
    const fn = mockJsonFetch({
      session_id: 7,
      next_item: null,
      theta: 0,
      standard_error: null,
      answered: 1,
      done: true,
      result: null,
    });
    await nextAdaptivePlacement("u1", { "pl-01": 0 }, 7);
    const url = fn.mock.calls[0][0] as string;
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(url).toBe("/api/academy/placement/next?user_id=u1");
    expect(body).toEqual({ answers: { "pl-01": 0 }, session_id: 7 });
  });

  it("getGoal llama al endpoint goal", async () => {
    const fn = mockJsonFetch({
      goal_type: "general",
      minutes_per_day: 15,
      days_per_week: 5,
      target_level: "B1",
    });
    await getGoal("u1");
    expect(fn.mock.calls[0][0]).toBe("/api/academy/goal?user_id=u1");
  });

  it("getSession llama al endpoint session", async () => {
    const fn = mockJsonFetch({
      items: [],
      total_minutes: 15,
      review_count: 2,
      practice_count: 1,
    });
    await getSession("u1");
    expect(fn.mock.calls[0][0]).toBe("/api/academy/session?user_id=u1");
  });

  it("completeSessionStep envía step_key por POST", async () => {
    const fn = mockJsonFetch({
      items: [],
      total_minutes: 10,
      review_count: 1,
      practice_count: 1,
    });
    await completeSessionStep("u1", "review:grammar");
    const url = fn.mock.calls[0][0] as string;
    const method = fn.mock.calls[0][1].method;
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(url).toBe("/api/academy/session/complete?user_id=u1");
    expect(method).toBe("POST");
    expect(body).toEqual({ step_key: "review:grammar" });
  });

  it("putGoal envía el objetivo con PUT", async () => {
    const fn = mockJsonFetch({
      goal_type: "travel",
      minutes_per_day: 20,
      days_per_week: 6,
      target_level: "B2",
    });
    await putGoal("u1", {
      goal_type: "travel",
      minutes_per_day: 20,
      days_per_week: 6,
      target_level: "B2",
    });
    const url = fn.mock.calls[0][0] as string;
    const method = fn.mock.calls[0][1].method;
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(url).toBe("/api/academy/goal?user_id=u1");
    expect(method).toBe("PUT");
    expect(body).toEqual({
      goal_type: "travel",
      minutes_per_day: 20,
      days_per_week: 6,
      target_level: "B2",
    });
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

  it("completeLesson envía level/objective", async () => {
    const fn = mockJsonFetch({ level_id: "a1", objective_id: "o1", recorded: true });
    await completeLesson("u1", "a1", "o1");
    const url = fn.mock.calls[0][0] as string;
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(url).toBe("/api/academy/lessons/complete?user_id=u1");
    expect(body).toEqual({ level_id: "a1", objective_id: "o1" });
  });

  it("getSpeakingDiagnostic incluye user_id en la query", async () => {
    const fn = mockJsonFetch({
      criteria: [],
      weak: [],
      recommendation: "",
      attempts: 0,
      overall_mean: null,
      trend: { direction: "n/a" },
      rubric_version: "1.0.0",
    });
    await getSpeakingDiagnostic("u1");
    expect(fn.mock.calls[0][0]).toBe(
      "/api/academy/speaking/diagnostic?user_id=u1",
    );
  });

  it("getSpeakingLevel incluye user_id en la query", async () => {
    const fn = mockJsonFetch({
      level: "B1",
      numeric: 3.1,
      score: 0.62,
      confidence: 0.86,
      attempts: 12,
    });
    await getSpeakingLevel("u1");
    expect(fn.mock.calls[0][0]).toBe("/api/academy/speaking/level?user_id=u1");
  });

  it("getSpeakingJourney incluye user_id en la query", async () => {
    const fn = mockJsonFetch({
      current_level: "B1",
      current_numeric: 3.1,
      current_confidence: 0.86,
      attempts: 12,
      steps: [],
    });
    await getSpeakingJourney("u1");
    expect(fn.mock.calls[0][0]).toBe(
      "/api/academy/speaking/journey?user_id=u1",
    );
  });

  it("startSpeakingAssessment llama a assessment/start por POST", async () => {
    const fn = mockJsonFetch({
      session_id: 1,
      assessment_version: "1.0.0",
      total_parts: 4,
      part: null,
    });
    await startSpeakingAssessment("u1");
    const url = fn.mock.calls[0][0] as string;
    const method = fn.mock.calls[0][1].method;
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(url).toBe("/api/academy/speaking/assessment/start?user_id=u1");
    expect(method).toBe("POST");
    expect(body).toEqual({});
  });

  it("submitSpeakingAssessmentPart envía session_id, heard y duration", async () => {
    const fn = mockJsonFetch({
      session_id: 1,
      part_index: 1,
      task_type: "Interview",
      cefr_target: "B1",
      prompt: "Tell me about yourself.",
      part_scores: { overall: 0.7, criteria: {}, observed: {} },
      done: false,
      next_part: null,
    });
    await submitSpeakingAssessmentPart("u1", 1, "hello", 12.5);
    const url = fn.mock.calls[0][0] as string;
    const method = fn.mock.calls[0][1].method;
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(url).toBe("/api/academy/speaking/assessment/part?user_id=u1");
    expect(method).toBe("POST");
    expect(body).toEqual({ session_id: 1, heard: "hello", duration_seconds: 12.5 });
  });

  it("submitSpeakingAssessmentPart omite duration_seconds si no se pasa", async () => {
    const fn = mockJsonFetch({
      session_id: 1,
      part_index: 1,
      task_type: "Interview",
      cefr_target: "B1",
      prompt: "Tell me about yourself.",
      part_scores: { overall: 0.7, criteria: {}, observed: {} },
      done: false,
      next_part: null,
    });
    await submitSpeakingAssessmentPart("u1", 1, "hello");
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(body).toEqual({ session_id: 1, heard: "hello" });
  });

  it("finishSpeakingAssessment envía session_id por POST", async () => {
    const fn = mockJsonFetch({
      session_id: 1,
      level: "B1",
      numeric: 3.1,
      score: 0.62,
      confidence: 0.86,
      attempts: 4,
      criteria: [],
      weak: [],
      recommendation: "",
      assessment_version: "1.0.0",
      rubric_version: "1.0.0",
    });
    await finishSpeakingAssessment("u1", 1);
    const url = fn.mock.calls[0][0] as string;
    const method = fn.mock.calls[0][1].method;
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(url).toBe("/api/academy/speaking/assessment/finish?user_id=u1");
    expect(method).toBe("POST");
    expect(body).toEqual({ session_id: 1 });
  });

  it("getSpeakingAssessment usa el id en la ruta y user_id en la query", async () => {
    const fn = mockJsonFetch({
      session_id: 1,
      status: "in_progress",
      assessment_version: "1.0.0",
      total_parts: 4,
      next_part_index: 2,
      final_result: null,
    });
    await getSpeakingAssessment("u1", 1);
    const url = fn.mock.calls[0][0] as string;
    const method = fn.mock.calls[0][1]?.method;
    expect(url).toBe("/api/academy/speaking/assessment/1?user_id=u1");
    expect(method).toBeUndefined();
  });

  it("submitObjectiveAssessment envía respuestas, no scores", async () => {
    const fn = mockJsonFetch({
      level_id: "a1",
      objective_id: "o1",
      overall: 1,
      correct: 2,
      total: 2,
      skills: {},
      mastery: {},
    });
    await submitObjectiveAssessment("u1", "a1", "o1", { c1: 1, c2: 0 });
    const url = fn.mock.calls[0][0] as string;
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(url).toBe("/api/academy/objective/assessment?user_id=u1");
    expect(body).toEqual({
      level_id: "a1",
      objective_id: "o1",
      answers: { c1: 1, c2: 0 },
    });
  });
});
