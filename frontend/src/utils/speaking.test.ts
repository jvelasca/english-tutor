import { describe, expect, it } from "vitest";
import type { SpeakingCriterionProgress } from "../types/api";
import {
  criterionLabel,
  formatConfidence,
  formatDurationTarget,
  formatScorePct,
  formatTrendDelta,
  nextFocus,
  numericToCefr,
} from "./speaking";

function criterion(
  criterion: string,
  overrides: Partial<SpeakingCriterionProgress> = {},
): SpeakingCriterionProgress {
  return {
    criterion,
    attempts: 1,
    mean: null,
    min: null,
    max: null,
    review_due: false,
    ...overrides,
  };
}

describe("numericToCefr", () => {
  it("compone nivel + décima", () => {
    expect(numericToCefr(3.1)).toBe("B1.1");
    expect(numericToCefr(2.7)).toBe("A2.7");
    expect(numericToCefr(3.3)).toBe("B1.3");
  });

  it("cubre los extremos del rango", () => {
    expect(numericToCefr(1)).toBe("A1.0");
    expect(numericToCefr(6)).toBe("C2.0");
  });

  it("acota fuera del rango 1..6", () => {
    expect(numericToCefr(0)).toBe("A1.0");
    expect(numericToCefr(7)).toBe("C2.0");
  });

  it("redondea a la décima y arrastra al nivel siguiente", () => {
    expect(numericToCefr(3.96)).toBe("B2.0");
    expect(numericToCefr(2.96)).toBe("B1.0");
  });
});

describe("formatConfidence", () => {
  it("redondea la confianza 0..1 a porcentaje entero", () => {
    expect(formatConfidence(0.86)).toBe("86%");
    expect(formatConfidence(0.5)).toBe("50%");
    expect(formatConfidence(0.724)).toBe("72%");
    expect(formatConfidence(1)).toBe("100%");
  });
});

describe("formatTrendDelta", () => {
  it("añade signo positivo", () => {
    expect(formatTrendDelta(0.12)).toBe("+12%");
  });

  it("usa signo negativo tipográfico", () => {
    expect(formatTrendDelta(-0.05)).toBe("−5%");
  });

  it("devuelve 0% para delta cero", () => {
    expect(formatTrendDelta(0)).toBe("0%");
  });

  it("devuelve guion para null", () => {
    expect(formatTrendDelta(null)).toBe("—");
  });
});

describe("formatScorePct", () => {
  it("convierte una puntuación 0..1 a porcentaje entero", () => {
    expect(formatScorePct(0.62)).toBe("62%");
    expect(formatScorePct(1)).toBe("100%");
    expect(formatScorePct(0)).toBe("0%");
  });

  it("devuelve guion para null", () => {
    expect(formatScorePct(null)).toBe("—");
  });
});

describe("formatDurationTarget", () => {
  it("formatea segundos sueltos", () => {
    expect(formatDurationTarget(45)).toBe("45 s");
    expect(formatDurationTarget(30)).toBe("30 s");
  });

  it("formatea minutos exactos", () => {
    expect(formatDurationTarget(60)).toBe("1 min");
    expect(formatDurationTarget(120)).toBe("2 min");
  });

  it("formatea minutos y segundos", () => {
    expect(formatDurationTarget(90)).toBe("1:30");
    expect(formatDurationTarget(75)).toBe("1:15");
  });

  it("devuelve guion para valores no positivos", () => {
    expect(formatDurationTarget(0)).toBe("—");
    expect(formatDurationTarget(-5)).toBe("—");
    expect(formatDurationTarget(Number.NaN)).toBe("—");
  });
});

describe("criterionLabel", () => {
  it("mapea cada criterio a su etiqueta", () => {
    expect(criterionLabel("task_achievement")).toBe("Tarea");
    expect(criterionLabel("grammatical_control")).toBe("Gramática");
    expect(criterionLabel("lexical_resource")).toBe("Léxico");
    expect(criterionLabel("fluency")).toBe("Fluidez");
    expect(criterionLabel("pronunciation")).toBe("Pronunciación");
    expect(criterionLabel("coherence")).toBe("Coherencia");
    expect(criterionLabel("interaction")).toBe("Interacción");
  });

  it("devuelve el valor crudo para criterios desconocidos", () => {
    expect(criterionLabel("spelling")).toBe("spelling");
  });
});

describe("nextFocus", () => {
  it("prioriza los criterios con review_due, ordenados por menor puntuación", () => {
    const criteria = [
      criterion("fluency", { recent_score: 0.9 }),
      criterion("grammar", { review_due: true, recent_score: 0.8 }),
      criterion("lexis", { review_due: true, recent_score: 0.6 }),
    ];
    expect(nextFocus(criteria)).toEqual(["lexis", "grammar"]);
  });

  it("sin review_due elige la menor puntuación", () => {
    const criteria = [
      criterion("fluency", { recent_score: 0.8 }),
      criterion("grammar", { recent_score: 0.4 }),
      criterion("lexis", { mean: 0.5 }),
    ];
    expect(nextFocus(criteria)).toEqual(["grammar", "lexis"]);
  });

  it("usa recent_score antes que mean", () => {
    const criteria = [
      criterion("fluency", { recent_score: 0.7, mean: 0.3 }),
      criterion("grammar", { mean: 0.4 }),
    ];
    expect(nextFocus(criteria)).toEqual(["grammar", "fluency"]);
  });

  it("ignora criterios sin evidencia", () => {
    const criteria = [
      criterion("fluency", { recent_score: 0.7 }),
      criterion("grammar"),
    ];
    expect(nextFocus(criteria)).toEqual(["fluency"]);
  });

  it("devuelve vacío si no hay criterios", () => {
    expect(nextFocus([])).toEqual([]);
  });

  it("devuelve vacío si ningún criterio tiene evidencia", () => {
    expect(nextFocus([criterion("fluency"), criterion("grammar")])).toEqual([]);
  });
});
