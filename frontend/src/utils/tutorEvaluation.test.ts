import { describe, expect, it } from "vitest";
import {
  averageEvaluations,
  concisenessScore,
  engagementScore,
  englishWordRatio,
  evaluateTutorReply,
  normalize,
  spanishWordRatio,
  words,
} from "./tutorEvaluation";

describe("normalize", () => {
  it("baja a minúsculas y quita puntuación", () => {
    const result = normalize("Hello, World!");
    expect(result).toContain("hello");
    expect(result).toContain("world");
  });
});

describe("words", () => {
  it("extrae palabras", () => {
    expect(words("I have twenty years")).toEqual([
      "i",
      "have",
      "twenty",
      "years",
    ]);
  });
});

describe("spanishWordRatio", () => {
  it("detecta español", () => {
    expect(spanishWordRatio("Está muy bien, gracias.")).toBeGreaterThan(0.5);
  });
});

describe("englishWordRatio", () => {
  it("todo inglés → 1", () => {
    expect(englishWordRatio("hello world")).toBe(1);
  });
});

describe("concisenessScore", () => {
  it("50 palabras → 100", () => {
    expect(concisenessScore(50)).toBe(100);
  });

  it("5 palabras → 50", () => {
    expect(concisenessScore(5)).toBe(50);
  });

  it("500 palabras → 40", () => {
    expect(concisenessScore(500)).toBe(40);
  });
});

describe("engagementScore", () => {
  it("pregunta → 100", () => {
    expect(engagementScore("Good! How old are you?")).toBe(100);
  });

  it("marcador amistoso → 70", () => {
    expect(engagementScore("Great work, keep going.")).toBe(70);
  });

  it("marcador con apóstrofe (let's) → 70", () => {
    expect(engagementScore("Let's practice together.")).toBe(70);
  });

  it("sin pregunta ni marcador → 0", () => {
    expect(engagementScore("Just a statement.")).toBe(0);
  });
});

describe("evaluateTutorReply", () => {
  it("respuesta en inglés con pregunta → english 100 y total >= 80", () => {
    const evaluation = evaluateTutorReply("How old are you?");
    expect(evaluation.english).toBe(100);
    expect(evaluation.total).toBeGreaterThanOrEqual(80);
  });

  it("respuesta en español → english < 50", () => {
    const evaluation = evaluateTutorReply("Está muy bien, gracias.");
    expect(evaluation.english).toBeLessThan(50);
  });
});

describe("averageEvaluations", () => {
  it("promedia dos evaluaciones", () => {
    const result = averageEvaluations([
      { english: 100, conciseness: 100, engagement: 100, total: 100 },
      { english: 50, conciseness: 50, engagement: 50, total: 50 },
    ]);
    expect(result).toEqual({
      english: 75,
      conciseness: 75,
      engagement: 75,
      total: 75,
    });
  });

  it("lista vacía → todos null", () => {
    expect(averageEvaluations([])).toEqual({
      english: null,
      conciseness: null,
      engagement: null,
      total: null,
    });
  });
});
