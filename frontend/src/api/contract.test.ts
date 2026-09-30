import { afterEach, describe, expect, it, vi } from "vitest";
import { getListeningQuestion } from "./listening";
import { addVocabularyItem } from "./vocabulary";

function mockFetch(data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok: true, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

// Payload con los MISMOS nombres que sirve el backend (snake_case). Es el espejo
// del lado servidor en `backend/tests/test_contract_v392.py`: si el backend
// renombra una clave, allí cae; si el cliente deja de traducirla, aquí. Ese
// desacuerdo es el fallo real que V3.92 arregló y que llevaba versiones oculto.
const RAW_LISTENING_QUESTION = {
  id: "l1",
  level: "A1",
  skill: "numbers",
  difficulty: 1,
  script: "It's a quarter past eight.",
  question: "What time is it?",
  options: ["8:15", "8:45"],
  flow: [
    {
      stage: "while1",
      task: "mcq",
      transcript_state_inicial: "hidden",
      allow_skip: false,
    },
  ],
  transcript_policy: {
    revelation: "on_first_fail",
    max_attempts_per_stage: 2,
    allow_manual_reveal: true,
    shadowing_optional: true,
  },
  sentence_timings: [
    {
      index: 0,
      start: 0,
      end: 2.5,
      text: "It's a quarter past eight.",
      sync: "coarse_heuristic",
    },
  ],
  word_timings: [{ index: 0, text: "It's", start: 0, end: 0.4, sentence: 0 }],
};

const SENSE = {
  term: "bank",
  pos: "noun",
  gloss: "A place where money is kept.",
  lemma: "bank",
  source: "lexicon",
  domain: "finance",
};

describe("contract E2E: borde backend -> frontend (V3.92)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getListeningQuestion traduce el snake_case EXACTO del backend", async () => {
    mockFetch(RAW_LISTENING_QUESTION);
    const q = await getListeningQuestion("u1", "A1");
    expect(q.transcriptPolicy?.max_attempts_per_stage).toBe(2);
    expect(q.sentenceTimings).toHaveLength(1);
    expect(q.wordTimings).toHaveLength(1);
    const raw = q as unknown as Record<string, unknown>;
    expect("transcript_policy" in raw).toBe(false);
    expect("sentence_timings" in raw).toBe(false);
    expect("word_timings" in raw).toBe(false);
  });

  it("addVocabularyItem manda el sense tal cual, sin renombrar campos", async () => {
    const fn = mockFetch({});
    await addVocabularyItem("u1", "bank", { translation: "banco", sense: SENSE });
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/items");
    const body = JSON.parse(init.body as string);
    expect(body.sense).toEqual(SENSE);
  });

  it("addVocabularyItem no manda sense cuando no consta", async () => {
    const fn = mockFetch({});
    await addVocabularyItem("u1", "anchor");
    const [, init] = fn.mock.calls[0];
    const body = JSON.parse(init.body as string);
    expect("sense" in body).toBe(false);
  });
});
