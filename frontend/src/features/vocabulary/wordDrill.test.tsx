// @vitest-environment jsdom
/**
 * Vitest de `WordDrill` con `initialStep` (V3.35): la cola de repaso abre el
 * drill directamente en la actividad recomendada, sin pasar por Recognition.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { I18nProvider } from "../../hooks/useI18n";
import { WordDrill } from "./wordDrill";

const mocks = vi.hoisted(() => ({
  getDrillRecognitionQuestion: vi.fn(),
  getDrillRecallPrompt: vi.fn(),
  getDrillSentenceContext: vi.fn(),
}));

vi.mock("../../api/vocabulary", () => ({
  getDrillRecognitionQuestion: mocks.getDrillRecognitionQuestion,
  getDrillRecallPrompt: mocks.getDrillRecallPrompt,
  getDrillSentenceContext: mocks.getDrillSentenceContext,
  submitDrillRecognitionAttempt: vi.fn(),
  submitDrillRecallAttempt: vi.fn(),
  submitDrillSentenceAttempt: vi.fn(),
}));

function renderDrill(initialStep?: "recognition" | "recall" | "sentence") {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <WordDrill
        userId="u1"
        word="river"
        initialStep={initialStep}
        onProduced={() => {}}
        onClose={() => {}}
      />
    </I18nProvider>,
  );
}

describe("WordDrill initialStep (V3.35)", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("por defecto abre en Recognition", async () => {
    mocks.getDrillRecognitionQuestion.mockResolvedValue({
      word: "river",
      available: true,
      question_id: "q1",
      options: ["río", "mar"],
    });
    renderDrill();
    expect(mocks.getDrillRecognitionQuestion).toHaveBeenCalledWith("u1", "river");
    expect(await screen.findByText("río")).toBeTruthy();
    expect(mocks.getDrillRecallPrompt).not.toHaveBeenCalled();
    expect(mocks.getDrillSentenceContext).not.toHaveBeenCalled();
  });

  it("initialStep='recall' abre directamente en Recall", async () => {
    mocks.getDrillRecallPrompt.mockResolvedValue({
      word: "river",
      available: true,
      cue: "río",
      cue_kind: "translation",
    });
    renderDrill("recall");

    expect(mocks.getDrillRecallPrompt).toHaveBeenCalledWith("u1", "river");
    expect(mocks.getDrillRecognitionQuestion).not.toHaveBeenCalled();
    expect(await screen.findByText("río")).toBeTruthy();
  });

  it("initialStep='sentence' abre directamente en Sentence", async () => {
    mocks.getDrillSentenceContext.mockResolvedValue({
      phrase: "I swim in the river.",
      source: "template",
    });
    renderDrill("sentence");

    expect(mocks.getDrillSentenceContext).toHaveBeenCalledWith("u1", "river");
    expect(mocks.getDrillRecognitionQuestion).not.toHaveBeenCalled();
    expect(await screen.findByText("I swim in the river.")).toBeTruthy();
  });
});
