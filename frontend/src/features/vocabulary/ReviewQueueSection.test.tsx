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
}));

vi.mock("../../api/learning", () => ({
  getReviewQueue: mocks.getReviewQueue,
}));
vi.mock("../../api/vocabulary", () => ({
  getDrillRecognitionQuestion: mocks.getDrillRecognitionQuestion,
  getDrillRecallPrompt: mocks.getDrillRecallPrompt,
  getDrillSentenceContext: mocks.getDrillSentenceContext,
  getDrillTransferContext: mocks.getDrillTransferContext,
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
    expect(mocks.getDrillRecallPrompt).toHaveBeenCalledWith("u1", "river");
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

  it("la actividad Transfer revela la palabra y abre el paso de transferencia (V3.40)", async () => {
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
            limiting_skill: "spontaneous_use",
            task: {
              skill: "spontaneous_use",
              activity: "transfer",
              reason: "transfer_gap",
              support_level: "spontaneous",
            },
            unit_surfaces: ["river"],
            transfer: false,
            success_contexts: ["lexicon:writing"],
            competence: null,
            evidence: null,
          },
        ],
      }),
    );
    mocks.getDrillTransferContext.mockResolvedValue({
      word: "river",
      context_id: "transfer:story",
      topic: "story",
      prompt: 'Tell a short story about your day using "river".',
      available: true,
    });
    renderSection();

    expect(await screen.findByText("river")).toBeTruthy();
    expect(screen.getByText("Use it in a new situation")).toBeTruthy();
    expect(
      screen.getByText("Ready to use it in a new situation"),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Review river" }));

    expect(mocks.getDrillTransferContext).toHaveBeenCalledWith("u1", "river");
    expect(
      await screen.findByText(/Tell a short story about your day/),
    ).toBeTruthy();
    expect(mocks.getDrillRecognitionQuestion).not.toHaveBeenCalled();
    expect(mocks.getDrillRecallPrompt).not.toHaveBeenCalled();
  });
});
