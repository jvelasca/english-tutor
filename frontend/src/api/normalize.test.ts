/**
 * Vitest de la normalización runtime de contratos (V3.77.2).
 *
 * Fija la lección de V3.77.0/V3.77.1: un JSON HTTP con la forma incompleta no
 * puede llegar al estado de React. Cada caso alimenta el normalizador con la
 * basura que un servidor podría servir (ausente, null, tipo equivocado,
 * elemento no-objeto) y comprueba que sale un objeto de dominio utilizable.
 */
import { describe, expect, it } from "vitest";
import {
  asArray,
  asBoolean,
  asNumber,
  asString,
  asStringArray,
  normalizeDictionaryEntry,
  normalizeDrillCandidates,
  normalizeLexicon,
  normalizeRetentionDue,
  normalizeReviewQueue,
  normalizeVocabBulkAdd,
  normalizeVocabCollections,
  normalizeVocabItemAdd,
} from "./normalize";

describe("helpers de coerción", () => {
  it("asArray solo acepta arrays", () => {
    expect(asArray([1, 2])).toEqual([1, 2]);
    expect(asArray(null)).toEqual([]);
    expect(asArray(undefined)).toEqual([]);
    expect(asArray("abc")).toEqual([]);
    expect(asArray({ length: 2 })).toEqual([]);
  });

  it("los escalares caen a su valor neutro ante un tipo equivocado", () => {
    expect(asNumber("3")).toBe(0);
    expect(asNumber(NaN)).toBe(0);
    expect(asNumber(4)).toBe(4);
    expect(asString(7)).toBe("");
    expect(asString("x")).toBe("x");
    expect(asBoolean("true")).toBe(false);
    expect(asBoolean(true)).toBe(true);
    expect(asStringArray(["a", 2, null, "b"])).toEqual(["a", "b"]);
  });
});

describe("normalizeVocabCollections (el fallo de V3.77.0)", () => {
  it("una respuesta sin `collections` sale como array vacío", () => {
    expect(normalizeVocabCollections({})).toEqual({ collections: [] });
    expect(normalizeVocabCollections(null)).toEqual({ collections: [] });
    expect(normalizeVocabCollections("abc")).toEqual({ collections: [] });
  });

  it("un `collections` no-array pero truthy no se cuela", () => {
    expect(normalizeVocabCollections({ collections: {} })).toEqual({
      collections: [],
    });
    expect(normalizeVocabCollections({ collections: "x" })).toEqual({
      collections: [],
    });
  });

  it("descarta elementos que no son registros y completa los campos", () => {
    const out = normalizeVocabCollections({
      collections: ["basura", null, { id: 7, title: "Travel" }],
    });
    expect(out.collections).toHaveLength(1);
    expect(out.collections[0]).toMatchObject({
      id: 7,
      title: "Travel",
      item_count: 0,
      enrolled: false,
      is_global: false,
    });
  });

  it("no convierte una cadena en número: el id inválido cae a 0", () => {
    // El backend sirve números; una cadena es un contrato roto, no un id.
    const out = normalizeVocabCollections({ collections: [{ id: "7" }] });
    expect(out.collections[0].id).toBe(0);
  });
});

describe("normalizeLexicon", () => {
  it("`summary` e `items` existen aunque falten en la respuesta", () => {
    const out = normalizeLexicon({});
    expect(out.items).toEqual([]);
    expect(out.summary.by_cefr).toEqual([]);
    expect(out.summary.total).toBe(0);
    // Los contadores de la matriz de competencia también salen a 0.
    expect(out.summary.production_gap).toBe(0);
    expect(out.summary.transfer_gap).toBe(0);
  });

  it("no se puede reventar con un `items` no-array ni con summary basura", () => {
    const out = normalizeLexicon({ summary: "abc", items: { a: 1 } });
    expect(out.items).toEqual([]);
    expect(out.summary.by_cefr).toEqual([]);
  });

  it("coerciona el estado de cada ítem y conserva los campos aditivos", () => {
    const out = normalizeLexicon({
      summary: { total: 1, by_cefr: [{ cefr: "A1", count: 1 }, "x"] },
      items: [
        { word: "go", status: "raro", recall: "0.5", next_review_days: null },
      ],
    });
    expect(out.summary.by_cefr).toEqual([{ cefr: "A1", count: 1 }]);
    expect(out.items[0]).toMatchObject({
      word: "go",
      status: "learning",
      recall: 0,
      next_review_days: 0,
      production_count: 0,
    });
  });
});

describe("normalizeDrillCandidates", () => {
  it("`words` siempre es un array de cadenas", () => {
    expect(normalizeDrillCandidates({})).toEqual({ words: [] });
    expect(normalizeDrillCandidates(null)).toEqual({ words: [] });
    expect(normalizeDrillCandidates({ words: "go" })).toEqual({ words: [] });
    expect(normalizeDrillCandidates({ words: ["go", 3] })).toEqual({
      words: ["go"],
    });
  });
});

describe("normalizeRetentionDue", () => {
  it("`items` siempre array y los escalares con defecto", () => {
    const out = normalizeRetentionDue({});
    expect(out.items).toEqual([]);
    expect(out.due_count).toBe(0);
    expect(out.fsrs_version).toBe("");

    const bad = normalizeRetentionDue({ items: { 0: "x" }, due_count: "2" });
    expect(bad.items).toEqual([]);
    expect(bad.due_count).toBe(0);
  });

  it("normaliza cada carta y descarta las no-objeto", () => {
    const out = normalizeRetentionDue({
      items: [{ word: "airport", reps: "3" }, 42, null],
    });
    expect(out.items).toHaveLength(1);
    expect(out.items[0]).toMatchObject({
      word: "airport",
      reps: 0,
      translation: "",
      stability: 0,
    });
  });
});

describe("normalizeVocabItemAdd / normalizeVocabBulkAdd", () => {
  it("`added` y `count` salen con forma aunque falten", () => {
    expect(normalizeVocabItemAdd({})).toMatchObject({
      added: [],
      item: { word: "", translation: "", definition: "" },
    });
    expect(normalizeVocabBulkAdd({})).toMatchObject({ added: [], count: 0 });
    expect(normalizeVocabBulkAdd({ added: null, count: "3" })).toMatchObject({
      added: [],
      count: 0,
    });
  });
});

describe("normalizeDictionaryEntry", () => {
  it("`usage` es siempre objeto y `alternatives` siempre array", () => {
    const out = normalizeDictionaryEntry({ word: "coffee" });
    expect(out.alternatives).toEqual([]);
    expect(out.usage).toEqual({ tracked: false, surface: null, unit: null });
    expect(out.direction).toBe("en-es");
    expect(out.definition_source).toBe("none");
    expect(out.example).toBeNull();
  });

  it("una entrada sin `usage` no rompe la tarjeta de resultado", () => {
    const out = normalizeDictionaryEntry({
      word: "coffee",
      usage: null,
      definition_source: "llm",
      direction: "es-en",
    });
    expect(out.usage.tracked).toBe(false);
    expect(out.direction).toBe("es-en");
    expect(out.definition_source).toBe("llm");
  });

  it("normaliza el bloque de uso de la superficie", () => {
    const out = normalizeDictionaryEntry({
      usage: {
        tracked: true,
        surface: { status: "mozart", recall: "0.4", production_channels: ["x", 1] },
      },
    });
    expect(out.usage.tracked).toBe(true);
    expect(out.usage.surface).toMatchObject({
      status: "learning",
      recall: 0,
      production_channels: ["x"],
      next_review_days: 0,
    });
  });
});

describe("normalizeReviewQueue", () => {
  it("un `items` no-array pero truthy ya no llega al render", () => {
    const out = normalizeReviewQueue({ items: { a: 1 }, due_count: "5" });
    expect(out.items).toEqual([]);
    expect(out.due_count).toBe(0);
  });

  it("normaliza cada ítem y su actividad declarada", () => {
    const out = normalizeReviewQueue({
      items: [{ word: "go", activity: "telepatía", reason: "due" }, "x"],
    });
    expect(out.items).toHaveLength(1);
    expect(out.items[0]).toMatchObject({
      word: "go",
      activity: "recognition",
      reason: "due",
      stability: 0,
    });
  });

  it("conserva el bloque de decisión solo si es objeto", () => {
    const withDecision = normalizeReviewQueue({
      items: [{ word: "go", decision: { skill: "vocabulary" } }],
    });
    expect(withDecision.items[0].decision).toEqual({ skill: "vocabulary" });

    const badDecision = normalizeReviewQueue({
      items: [{ word: "go", decision: "nope" }],
    });
    expect(badDecision.items[0].decision).toBeNull();
  });
});
