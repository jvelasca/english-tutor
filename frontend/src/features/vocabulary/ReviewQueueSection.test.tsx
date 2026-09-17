// @vitest-environment jsdom
/**
 * Vitest de `ReviewQueueSection` (V3.35, P1-2): la cola de repaso propia
 * (FSRS) muestra los ítems vencidos con la actividad recomendada por hueco y
 * abre el drill directamente en ese peldaño (`initialStep`).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { I18nProvider } from "../../hooks/useI18n";
import { ReviewQueueSection } from "./ReviewQueueSection";
import type { ReviewQueue } from "../../types/api";

const mocks = vi.hoisted(() => ({
  getReviewQueue: vi.fn(),
  getDrillRecognitionQuestion: vi.fn(),
  getDrillRecallPrompt: vi.fn(),
  getDrillSentenceContext: vi.fn(),
  getDrillTransferContext: vi.fn(),
  markDrillStarted: vi.fn(),
  markDrillAbandoned: vi.fn(),
}));

vi.mock("../../api/learning", () => ({
  getReviewQueue: mocks.getReviewQueue,
}));
vi.mock("../../api/vocabulary", () => ({
  getDrillRecognitionQuestion: mocks.getDrillRecognitionQuestion,
  getDrillRecallPrompt: mocks.getDrillRecallPrompt,
  getDrillSentenceContext: mocks.getDrillSentenceContext,
  getDrillTransferContext: mocks.getDrillTransferContext,
  // V3.68 (P1-02): el ciclo de vida del provenance que dispara el drill.
  markDrillStarted: mocks.markDrillStarted,
  markDrillAbandoned: mocks.markDrillAbandoned,
  submitDrillRecognitionAttempt: vi.fn(),
  submitDrillRecallAttempt: vi.fn(),
  submitDrillSentenceAttempt: vi.fn(),
  submitDrillWriteAttempt: vi.fn(),
  submitDrillTransferAttempt: vi.fn(),
}));

function queue(payload: Partial<ReviewQueue>): ReviewQueue {
  return { due_count: 0, items: [], fsrs_version: "2.11.0-lite", ...payload };
}

function renderSection() {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <ReviewQueueSection userId="u1" />
    </I18nProvider>,
  );
}

describe("ReviewQueueSection (V3.35)", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("muestra los ítems vencidos con su actividad recomendada", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 2,
        items: [
          {
            word: "river",
            lexical_unit: "river",
            cefr: "A1",
            kind: "word",
            due_at: "",
            state: "review",
            stability: 1,
            retrievability: 0.4,
            elapsed_days: 9,
            activity: "recall",
            reason: "no_recall_evidence",
            competence: null,
            evidence: null,
          },
          {
            word: "apple",
            lexical_unit: "apple",
            cefr: "A1",
            kind: "word",
            due_at: "",
            state: "review",
            stability: 1,
            retrievability: 0.5,
            elapsed_days: 7,
            activity: "sentence",
            reason: "production_gap",
            competence: null,
            evidence: null,
          },
        ],
      }),
    );
    renderSection();

    // V3.35.1 (P1-03): Recall/Sentence NO revelan la forma esperada.
    expect(
      await screen.findByText("Word hidden — recall from meaning"),
    ).toBeTruthy();
    expect(
      screen.getByText("Word hidden — produce it in a sentence"),
    ).toBeTruthy();
    expect(screen.queryByText("river")).toBeNull();
    expect(screen.queryByText("apple")).toBeNull();
    expect(screen.getByText("2 due")).toBeTruthy();
    expect(screen.getByText("Recall")).toBeTruthy();
    expect(screen.getByText("No recall from meaning yet")).toBeTruthy();
    expect(screen.getByText("Say in a sentence")).toBeTruthy();
    expect(screen.getByText("Understood but not produced yet")).toBeTruthy();
  });

  it("declara el `why` del planner en la fila (V3.72: por qué esta tarjeta)", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 1,
        items: [
          {
            word: "river",
            lexical_unit: "river",
            cefr: "A1",
            kind: "word",
            due_at: "",
            state: "review",
            stability: 1,
            retrievability: 0.4,
            elapsed_days: 9,
            activity: "recall",
            reason: "no_recall_evidence",
            why: "recognition without recall evidence; due for review (memory decayed)",
            competence: null,
            evidence: null,
          },
        ],
      }),
    );
    renderSection();

    const line = await screen.findByText(/recognition without recall evidence/);
    // El texto es del servidor: la UI solo añade la etiqueta traducida.
    expect(line.textContent).toBe(
      "Why? recognition without recall evidence; due for review (memory decayed)",
    );
  });

  it("sin `why` declarado la fila no inventa un porqué (V3.72)", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 1,
        items: [
          {
            word: "river",
            lexical_unit: "river",
            cefr: "A1",
            kind: "word",
            due_at: "",
            state: "review",
            stability: 1,
            retrievability: 0.4,
            elapsed_days: 9,
            activity: "recognition",
            reason: "weak_recognition",
            competence: null,
            evidence: null,
          },
        ],
      }),
    );
    renderSection();

    await screen.findByText("river");
    expect(screen.queryByText("Why?")).toBeNull();
  });

  it("solo revela la palabra cuando la actividad es Recognition", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 1,
        items: [
          {
            word: "river",
            lexical_unit: "river",
            cefr: "A1",
            kind: "word",
            due_at: "",
            state: "review",
            stability: 1,
            retrievability: 0.3,
            elapsed_days: 12,
            activity: "recognition",
            reason: "weak_recognition",
            competence: null,
            evidence: null,
          },
        ],
      }),
    );
    renderSection();

    expect(await screen.findByText("river")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Review river" }),
    ).toBeTruthy();
  });

  it("sin ítems vencidos muestra el estado vacío", async () => {
    mocks.getReviewQueue.mockResolvedValue(queue({}));
    renderSection();
    expect(
      await screen.findByText("Nothing to review right now — come back later."),
    ).toBeTruthy();
  });

  it("abre el WordDrill en el peldaño recomendado", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 1,
        items: [
          {
            word: "river",
            lexical_unit: "river",
            cefr: "A1",
            kind: "word",
            due_at: "",
            state: "review",
            stability: 1,
            retrievability: 0.4,
            elapsed_days: 9,
            activity: "recall",
            reason: "no_recall_evidence",
            // V3.68 (P1-02): el id determinista de la decisión servida viaja al
            // drill y termina en los GET/POST del peldaño.
            decision_id: "d-recall",
            competence: null,
            evidence: null,
          },
        ],
      }),
    );
    mocks.getDrillRecallPrompt.mockResolvedValue({
      word: "river",
      available: true,
      cue: "río",
      cue_kind: "translation",
    });
    renderSection();

    // V3.35.1 (P1-03): con Recall, el botón no filtra la palabra en su nombre.
    fireEvent.click(
      await screen.findByRole("button", { name: "Review word" }),
    );
    expect(mocks.getDrillRecallPrompt).toHaveBeenCalledWith(
      "u1",
      "river",
      undefined,
      "d-recall",
    );
    expect(mocks.getDrillRecognitionQuestion).not.toHaveBeenCalled();
    expect(await screen.findByText("río")).toBeTruthy();
  });

  it("la actividad Write revela la palabra y abre el paso de escritura (V3.39)", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 1,
        items: [
          {
            word: "river",
            lexical_unit: "river",
            cefr: "A1",
            kind: "word",
            due_at: "",
            state: "review",
            stability: 1,
            retrievability: 0.4,
            elapsed_days: 9,
            activity: "write",
            reason: "skill_gap",
            limiting_skill: "written_production",
            task: {
              skill: "written_production",
              activity: "write",
              reason: "skill_gap",
              support_level: "independent",
            },
            competence: null,
            evidence: null,
          },
        ],
      }),
    );
    renderSection();

    // La palabra es el RECURSO de la tarea: se muestra (a diferencia de recall).
    expect(await screen.findByText("river")).toBeTruthy();
    expect(screen.getByText("Write a sentence")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Review river" }));

    // El paso Write no pide contenido al servidor: la consigna es la palabra.
    expect(await screen.findByText(/using “river”/)).toBeTruthy();
    expect(mocks.getDrillRecognitionQuestion).not.toHaveBeenCalled();
    expect(mocks.getDrillRecallPrompt).not.toHaveBeenCalled();
    expect(mocks.getDrillSentenceContext).not.toHaveBeenCalled();
  });

  it("la actividad Transfer NO revela la palabra y abre el paso de transferencia (V3.43)", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 1,
        items: [
          {
            word: "river",
            lexical_unit: "river",
            cefr: "A1",
            kind: "word",
            due_at: "",
            state: "review",
            stability: 1,
            retrievability: 0.4,
            elapsed_days: 9,
            activity: "transfer",
            reason: "transfer_gap",
            decision_id: "d-transfer",
            limiting_skill: "spontaneous_use",
            task: {
              skill: "spontaneous_use",
              activity: "transfer",
              reason: "transfer_gap",
              support_level: "spontaneous",
            },
            unit_surfaces: ["river"],
            transfer: false,
            transfer_state: "emerging",
            success_contexts: ["lexicon:writing"],
            context_diversity: null,
            competence: null,
            evidence: null,
          },
        ],
      }),
    );
    mocks.getDrillTransferContext.mockResolvedValue({
      word: "river",
      context_id: "transfer:story",
      topic: "personal_experience",
      prompt: "Tell a short story about something that happened to you recently.",
      available: true,
      communicative_goal: "narrate",
      discourse_type: "narrative",
    });
    renderSection();

    // V3.43 (P1-01): la cola muestra la etiqueta de oculta, no la palabra.
    expect(
      await screen.findByText(
        "Word hidden — use it on your own in a new situation",
      ),
    ).toBeTruthy();
    expect(screen.queryByText("river")).toBeNull();
    expect(screen.getByText("Use it in a new situation")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Review word" }));

    expect(mocks.getDrillTransferContext).toHaveBeenCalledWith(
      "u1",
      "river",
      "d-transfer",
    );
    expect(
      await screen.findByText(/Tell a short story about something/),
    ).toBeTruthy();
    // La cabecera del drill tampoco revela el target antes del intento.
    expect(screen.queryByText("river")).toBeNull();
    expect(mocks.getDrillRecognitionQuestion).not.toHaveBeenCalled();
    expect(mocks.getDrillRecallPrompt).not.toHaveBeenCalled();
  });

  it("muestra la confianza de transferencia cuando hay evidencia (V3.49)", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 1,
        items: [
          {
            word: "river",
            lexical_unit: "river",
            cefr: "A1",
            kind: "word",
            due_at: "",
            state: "review",
            stability: 1,
            retrievability: 0.4,
            elapsed_days: 9,
            activity: "transfer",
            reason: "transfer_gap",
            transfer_state: "transfer_stable",
            transfer_confidence: {
              score: 0.91,
              level: "high",
              sample: 3,
              drivers: { contexts: 1, independence: 1 },
              recency_days: null,
            },
            competence: null,
            evidence: null,
          },
        ],
      }),
    );
    renderSection();

    const badge = await screen.findByText("Transfer evidence: solid");
    expect(badge).toBeTruthy();
    expect(badge.getAttribute("title")).toContain("internal protocol");
  });

  it("no muestra la confianza de transferencia sin evidencia (V3.49)", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 1,
        items: [
          {
            word: "river",
            lexical_unit: "river",
            cefr: "A1",
            kind: "word",
            due_at: "",
            state: "review",
            stability: 1,
            retrievability: 0.4,
            elapsed_days: 9,
            activity: "recall",
            reason: "no_recall_evidence",
            transfer_confidence: {
              score: 0,
              level: "none",
              sample: 0,
              drivers: {},
              recency_days: null,
            },
            competence: null,
            evidence: null,
          },
        ],
      }),
    );
    renderSection();

    await screen.findByText("Word hidden — recall from meaning");
    expect(screen.queryByText("No transfer evidence yet")).toBeNull();
  });

  it("muestra los motivos DECLARADOS de la decisión cuando hay proyección (V3.64)", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 1,
        items: [
          {
            word: "river",
            lexical_unit: "river",
            cefr: "A1",
            kind: "word",
            due_at: "",
            state: "review",
            stability: 1,
            retrievability: 0.4,
            elapsed_days: 9,
            activity: "write",
            reason: "skill_gap",
            decision: {
              skill: "written_production",
              activity: "write",
              expected_learning_value: 0.62,
              p_success: 0.5,
              margin: 0,
              value: 0.8,
              capacity_skill: "written_production",
              comparable: true,
              source: "argmax",
              projected: true,
              difficulty_fit: "in_zone",
              drivers: {
                measured: true,
                gap: "high",
                transfer_gap: "medium",
                retention_due: true,
                effort: "some",
                assessment_confidence: "medium",
              },
              why: ["Large gap in this skill"],
              alternatives: [],
            },
            competence: null,
            evidence: null,
          },
        ],
      }),
    );
    renderSection();

    const line = await screen.findByText(/In your growth zone/);
    // Bandas declaradas, en el idioma de la interfaz y en una sola línea.
    expect(line.textContent).toContain("Large gap");
    expect(line.textContent).toContain("Transfer: building");
    expect(line.textContent).toContain("Due for review");
    expect(line.textContent).toContain("Costly recall");
    expect(line.textContent).toContain("Assessment confidence: medium");
    // El alcance declarado viaja en el `title` (no es una promesa de dominio).
    expect(line.getAttribute("title")).toContain("not a claim of mastery");
  });

  it("no inventa motivos cuando el estado no declara medida (V3.64)", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 1,
        items: [
          {
            word: "river",
            lexical_unit: "river",
            cefr: "A1",
            kind: "word",
            due_at: "",
            state: "review",
            stability: 1,
            retrievability: 0.4,
            elapsed_days: 9,
            activity: "recall",
            reason: "no_recall_evidence",
            decision: {
              skill: "",
              activity: "recall",
              expected_learning_value: 0.1,
              p_success: null,
              margin: null,
              value: 0.1,
              capacity_skill: "",
              comparable: false,
              source: "cascade",
              projected: true,
              difficulty_fit: "unknown",
              drivers: { measured: false, gap: "high", transfer_gap: "high" },
              why: [],
              alternatives: [],
            },
            competence: null,
            evidence: null,
          },
        ],
      }),
    );
    renderSection();

    await screen.findByText("Word hidden — recall from meaning");
    // Ni encaje ni bandas: sin medida declarada no hay nada que explicar.
    expect(screen.queryByText(/growth zone/)).toBeNull();
    expect(screen.queryByText(/Large gap/)).toBeNull();
  });
});
