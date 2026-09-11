// @vitest-environment jsdom
/**
 * Vitest de `WordDrill` con `initialStep` (V3.35): la cola de repaso abre el
 * drill directamente en la actividad recomendada, sin pasar por Recognition.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { I18nProvider } from "../../hooks/useI18n";
import { WordDrill } from "./wordDrill";

const mocks = vi.hoisted(() => ({
  getDrillRecognitionQuestion: vi.fn(),
  getDrillRecallPrompt: vi.fn(),
  getDrillSentenceContext: vi.fn(),
  getDrillTransferContext: vi.fn(),
  submitDrillRecallAttempt: vi.fn(),
  submitDrillWriteAttempt: vi.fn(),
  submitDrillTransferAttempt: vi.fn(),
}));

vi.mock("../../api/vocabulary", () => ({
  getDrillRecognitionQuestion: mocks.getDrillRecognitionQuestion,
  getDrillRecallPrompt: mocks.getDrillRecallPrompt,
  getDrillSentenceContext: mocks.getDrillSentenceContext,
  getDrillTransferContext: mocks.getDrillTransferContext,
  submitDrillRecognitionAttempt: vi.fn(),
  submitDrillRecallAttempt: mocks.submitDrillRecallAttempt,
  submitDrillSentenceAttempt: vi.fn(),
  submitDrillWriteAttempt: mocks.submitDrillWriteAttempt,
  submitDrillTransferAttempt: mocks.submitDrillTransferAttempt,
}));

function renderDrill(
  initialStep?: "recognition" | "recall" | "sentence" | "write" | "transfer",
  onProduced: () => void = () => {},
) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <WordDrill
        userId="u1"
        word="river"
        initialStep={initialStep}
        onProduced={onProduced}
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

  it("peldaño cloze (V3.37): frase con hueco, palabra oculta y cue enviado", async () => {
    mocks.getDrillRecallPrompt.mockResolvedValue({
      word: "river",
      available: true,
      cue: "The _____ flows to the sea.",
      cue_kind: "cloze",
      support_level: "guided",
    });
    mocks.submitDrillRecallAttempt.mockResolvedValue({
      word: "river",
      correct: true,
      expected: "river",
      delayed: false,
      recall_days: 1,
      error_type: "correct",
    });
    renderDrill("recall");

    // El rótulo del peldaño y el cue con hueco se muestran; la diana se oculta.
    expect(
      await screen.findByText("The _____ flows to the sea."),
    ).toBeTruthy();
    expect(
      screen.getByText(/Complete the sentence with the missing word/),
    ).toBeTruthy();
    expect(screen.queryByText("river")).toBeNull();

    fireEvent.change(screen.getByLabelText("Type the word"), {
      target: { value: "river" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check" }));

    // El cliente declara QUÉ peldaño le sirvieron (premisa 21).
    await waitFor(() =>
      expect(mocks.submitDrillRecallAttempt).toHaveBeenCalledWith(
        "u1",
        "river",
        "river",
        expect.any(Number),
        "cloze",
      ),
    );
  });
});

describe("WordDrill paso Write (V3.39)", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("initialStep='write' abre la escritura sin pedir contenido al servidor", async () => {
    renderDrill("write");

    // La consigna muestra la palabra (es el recurso de la tarea, no la diana).
    expect(await screen.findByText(/using “river”/)).toBeTruthy();
    expect(screen.getByLabelText("Your sentence")).toBeTruthy();
    expect(mocks.getDrillRecognitionQuestion).not.toHaveBeenCalled();
    expect(mocks.getDrillRecallPrompt).not.toHaveBeenCalled();
    expect(mocks.getDrillSentenceContext).not.toHaveBeenCalled();
  });

  it("un acierto acredita la modalidad escrita y avisa al padre", async () => {
    const onProduced = vi.fn();
    mocks.submitDrillWriteAttempt.mockResolvedValue({
      word: "river",
      text: "I swim in the river every summer.",
      used_word: true,
      word_count: 6,
      passed: true,
      error_type: "correct",
    });
    renderDrill("write", onProduced);

    fireEvent.change(await screen.findByLabelText("Your sentence"), {
      target: { value: "I swim in the river every summer." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check sentence" }));

    await waitFor(() =>
      expect(mocks.submitDrillWriteAttempt).toHaveBeenCalledWith(
        "u1",
        "river",
        "I swim in the river every summer.",
        expect.any(Number),
      ),
    );
    expect(
      await screen.findByText(/You produced the word in writing/),
    ).toBeTruthy();
    expect(onProduced).toHaveBeenCalledTimes(1);
  });

  it("un fallo explica qué faltó y nunca dispara onProduced", async () => {
    const onProduced = vi.fn();
    mocks.submitDrillWriteAttempt.mockResolvedValue({
      word: "river",
      text: "river",
      used_word: true,
      word_count: 1,
      passed: false,
      error_type: "too_short",
    });
    renderDrill("write", onProduced);

    fireEvent.change(await screen.findByLabelText("Your sentence"), {
      target: { value: "river" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check sentence" }));

    expect(await screen.findByText(/write a longer sentence/)).toBeTruthy();
    expect(onProduced).not.toHaveBeenCalled();
  });
});

describe("WordDrill paso Transfer (V3.40)", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("initialStep='transfer' carga la consigna sin revelar el target (V3.43)", async () => {
    mocks.getDrillTransferContext.mockResolvedValue({
      word: "river",
      context_id: "transfer:story",
      topic: "personal_experience",
      prompt: "Tell a short story about something that happened to you recently.",
      available: true,
      communicative_goal: "narrate",
      discourse_type: "narrative",
    });
    renderDrill("transfer");

    expect(mocks.getDrillTransferContext).toHaveBeenCalledWith("u1", "river");
    expect(mocks.getDrillRecognitionQuestion).not.toHaveBeenCalled();
    expect(mocks.getDrillRecallPrompt).not.toHaveBeenCalled();
    expect(mocks.getDrillSentenceContext).not.toHaveBeenCalled();
    expect(
      await screen.findByText(/Tell a short story about something/),
    ).toBeTruthy();
    // V3.43 (P1-01): la cabecera NO revela la palabra y la consigna no la lleva.
    expect(
      screen.getAllByText("Word hidden — use it on your own").length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText("river")).toBeNull();
  });

  it("un acierto envía el context_id y avisa al padre", async () => {
    const onProduced = vi.fn();
    mocks.getDrillTransferContext.mockResolvedValue({
      word: "river",
      context_id: "transfer:story",
      topic: "personal_experience",
      prompt: "Tell a short story about something that happened to you recently.",
      available: true,
      communicative_goal: "narrate",
      discourse_type: "narrative",
    });
    mocks.submitDrillTransferAttempt.mockResolvedValue({
      word: "river",
      text: "Yesterday I walked by the river with my sister.",
      context_id: "transfer:story",
      used_word: true,
      word_count: 8,
      passed: true,
      error_type: "correct",
      lexical_transfer: true,
      semantic_fit: true,
      adequacy: "fit",
    });
    renderDrill("transfer", onProduced);

    fireEvent.change(await screen.findByLabelText("Your answer"), {
      target: { value: "Yesterday I walked by the river with my sister." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check answer" }));

    await waitFor(() =>
      expect(mocks.submitDrillTransferAttempt).toHaveBeenCalledWith(
        "u1",
        "river",
        "Yesterday I walked by the river with my sister.",
        "transfer:story",
        expect.any(Number),
      ),
    );
    expect(
      await screen.findByText(/used the word on your own in a new situation/),
    ).toBeTruthy();
    expect(onProduced).toHaveBeenCalledTimes(1);
  });

  it("un uso léxico con adecuación sospechosa avisa y no declara transferencia limpia", async () => {
    const onProduced = vi.fn();
    mocks.getDrillTransferContext.mockResolvedValue({
      word: "river",
      context_id: "transfer:story",
      topic: "personal_experience",
      prompt: "Tell a short story about something that happened to you recently.",
      available: true,
      communicative_goal: "narrate",
      discourse_type: "narrative",
    });
    mocks.submitDrillTransferAttempt.mockResolvedValue({
      word: "river",
      text: "I river the water every morning before work.",
      context_id: "transfer:story",
      used_word: true,
      word_count: 8,
      passed: true,
      error_type: "semantic_doubt",
      lexical_transfer: true,
      semantic_fit: false,
      adequacy: "suspect",
    });
    renderDrill("transfer", onProduced);

    fireEvent.change(await screen.findByLabelText("Your answer"), {
      target: { value: "I river the water every morning before work." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check answer" }));

    // V3.43 (P1-02): hubo producción léxica (onProduced) pero se avisa de que
    // el uso no encaja y no cuenta como transferencia confirmada.
    expect(
      await screen.findByText(/won't count as confirmed transfer/),
    ).toBeTruthy();
    expect(onProduced).toHaveBeenCalledTimes(1);
    // El target se revela en la cabecera tras el intento.
    expect(await screen.findByText("river")).toBeTruthy();
  });

  it("un uso semánticamente incorrecto avisa con firmeza y no cuenta como transferencia", async () => {
    const onProduced = vi.fn();
    mocks.getDrillTransferContext.mockResolvedValue({
      word: "river",
      context_id: "transfer:story",
      topic: "personal_experience",
      prompt: "Tell a short story about something that happened to you recently.",
      available: true,
      communicative_goal: "narrate",
      discourse_type: "narrative",
    });
    mocks.submitDrillTransferAttempt.mockResolvedValue({
      word: "river",
      text: "I river the water every morning before work.",
      context_id: "transfer:story",
      used_word: true,
      word_count: 8,
      passed: true,
      // V3.44: contradicción FUERTE con los sentidos de la unidad.
      error_type: "semantic_mismatch",
      lexical_transfer: true,
      semantic_fit: false,
      adequacy: "incorrect",
    });
    renderDrill("transfer", onProduced);

    fireEvent.change(await screen.findByLabelText("Your answer"), {
      target: { value: "I river the water every morning before work." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check answer" }));

    expect(
      await screen.findByText(/wrong meaning here/),
    ).toBeTruthy();
    // La evidencia léxica sigue existiendo (hubo producción).
    expect(onProduced).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("river")).toBeTruthy();
  });

  it("sin consigna disponible avisa y no deja enviar", async () => {
    const onProduced = vi.fn();
    mocks.getDrillTransferContext.mockResolvedValue({
      word: "river",
      context_id: "",
      topic: "",
      prompt: "",
      available: false,
    });
    renderDrill("transfer", onProduced);

    expect(
      await screen.findByText(/No new situation available/),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Check answer" }),
    ).toHaveProperty("disabled", true);
    expect(onProduced).not.toHaveBeenCalled();
  });

  it("muestra la condición de recuperación servida (V3.46)", async () => {
    mocks.getDrillTransferContext.mockResolvedValue({
      word: "river",
      context_id: "transfer:story",
      topic: "personal_experience",
      prompt:
        "Tell a short story about something that happened to you recently. Use any vocabulary you need.",
      available: true,
      communicative_goal: "narrate",
      discourse_type: "narrative",
      condition: "open_context",
      required_target: false,
      unscaffolded: true,
    });
    renderDrill("transfer");

    // La condición explica cuánta ayuda da la tarea (V3.46, P1-03).
    expect(
      await screen.findByText(/Open use: you choose your words/),
    ).toBeTruthy();
  });

  it("no usar la palabra en condición abierta se explica como no-error (V3.46)", async () => {
    const onProduced = vi.fn();
    mocks.getDrillTransferContext.mockResolvedValue({
      word: "river",
      context_id: "transfer:story",
      topic: "personal_experience",
      prompt:
        "Tell a short story about something that happened to you recently. Use any vocabulary you need.",
      available: true,
      communicative_goal: "narrate",
      discourse_type: "narrative",
      condition: "open_context",
      required_target: false,
      unscaffolded: true,
    });
    mocks.submitDrillTransferAttempt.mockResolvedValue({
      word: "river",
      text: "I walked to the beach yesterday with my sister.",
      context_id: "transfer:story",
      used_word: false,
      word_count: 8,
      passed: false,
      error_type: "missing_target",
      lexical_transfer: false,
      semantic_fit: null,
      adequacy: "unknown",
      condition: "open_context",
      required_target: false,
    });
    renderDrill("transfer", onProduced);

    fireEvent.change(await screen.findByLabelText("Your answer"), {
      target: { value: "I walked to the beach yesterday with my sister." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check answer" }));

    // En `open_context` la palabra NO era obligatoria: ni error ni evidencia.
    expect(await screen.findByText(/wasn't required here/)).toBeTruthy();
    expect(screen.queryByText(/must use the word/)).toBeNull();
    expect(onProduced).not.toHaveBeenCalled();
  });
});
