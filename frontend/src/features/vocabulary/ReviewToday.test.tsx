// @vitest-environment jsdom
/**
 * Vitest de «Repasar hoy» (V3.85.0), heredero de `ReviewQueueSection` (V3.35).
 *
 * Lo que se protege aquí es el cambio de contrato: la cola de repaso deja de ser
 * una LISTA de filas con un botón por fila (cuya etiqueta era una palabra de
 * estado, «vencida») y pasa a ser un RESUMEN con UNA acción —«Repasar ahora
 * (N)»— que ENCADENA la cola del día: una palabra detrás de otra, cada una en el
 * peldaño que recomienda el planificador, con «Siguiente palabra»/«Terminar»
 * entre medias para que el alumno lea el feedback antes de avanzar.
 *
 * La traza declarada (motivo, `why` y señales de la decisión) NO se pierde: se
 * muestra una vez, para la palabra que se está trabajando.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { I18nProvider } from "../../hooks/useI18n";
import { ReviewSession, useReviewToday } from "./ReviewToday";
import type { ReviewQueue, ReviewQueueItem } from "../../types/api";

const mocks = vi.hoisted(() => ({
  getReviewQueue: vi.fn(),
  getDrillRecognitionQuestion: vi.fn(),
  getDrillRecallPrompt: vi.fn(),
  getDrillSentenceContext: vi.fn(),
  getDrillTransferContext: vi.fn(),
  // V3.85.1 (C1): los peldaños reconductivos puntúan sin micrófono y su
  // veredicto debe mover la sesión (antes la dejaban clavada).
  submitDrillRecognitionAttempt: vi.fn(),
  submitDrillRecallAttempt: vi.fn(),
  submitDrillWriteAttempt: vi.fn(),
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
  submitDrillRecognitionAttempt: mocks.submitDrillRecognitionAttempt,
  submitDrillRecallAttempt: mocks.submitDrillRecallAttempt,
  // V3.39: el paso Write es el que produce sin micrófono, así que es el que
  // permite encadenar en un test sin simular audio.
  submitDrillWriteAttempt: mocks.submitDrillWriteAttempt,
  // V3.68 (P1-02): el ciclo de vida del provenance que dispara el drill.
  markDrillStarted: mocks.markDrillStarted,
  markDrillAbandoned: mocks.markDrillAbandoned,
}));

function queue(payload: Partial<ReviewQueue>): ReviewQueue {
  return { due_count: 0, items: [], fsrs_version: "2.11.0-lite", ...payload };
}

function dueWord(word: string, extra: Partial<ReviewQueueItem> = {}): ReviewQueueItem {
  return {
    word,
    lexical_unit: word,
    cefr: "A1",
    kind: "word",
    due_at: "",
    state: "review",
    stability: 1,
    retrievability: 0.4,
    elapsed_days: 9,
    activity: "write",
    reason: "production_gap",
    competence: null,
    evidence: null,
    ...extra,
  };
}

/** Monta el resumen (hook) + la sesión encadenada tal y como los usa StudyTab. */
function Harness({ items }: { items: ReviewQueueItem[] }) {
  const { items: queueItems, dueCount, loadError, refresh } = useReviewToday("u1");
  void items;
  if (loadError) return <p>Could not load the review queue. </p>;
  if (queueItems.length === 0) {
    return <p>{dueCount > 0 ? "loading next batch" : "Nothing to review right now — come back later."}</p>;
  }
  return (
    <ReviewSession
      userId="u1"
      items={queueItems}
      onExit={() => void refresh()}
    />
  );
}

function renderHarness() {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <Harness items={[]} />
    </I18nProvider>,
  );
}

/** Rellena la frase del paso Write y la envía. */
async function writeAndSend(text: string) {
  const box = await screen.findByLabelText("Your sentence");
  fireEvent.change(box, { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Check sentence" }));
}

describe("ReviewToday · resumen y sesión encadenada (V3.85.0)", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("con ítems vencidos no pinta una lista: monta la sesión en el peldaño servido", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 2,
        items: [
          dueWord("river", { decision_id: "d-river" }),
          dueWord("apple", { decision_id: "d-apple" }),
        ],
      }),
    );
    mocks.submitDrillWriteAttempt.mockResolvedValue({
      word: "river",
      passed: true,
      used_word: true,
      too_short: false,
      score: 100,
    });

    renderHarness();

    // El drill abre directamente en el peldaño que sirvió la cola (`write`).
    expect(
      await screen.findByText(/Write your own sentence using “river”/),
    ).toBeTruthy();
    // Progreso de la sesión, no una lista de 20 filas.
    expect(screen.getByText("1 of 2")).toBeTruthy();
    // La actividad recomendada se declara como etiqueta, no como acción.
    expect(screen.getByText("Write a sentence")).toBeTruthy();
    // El motivo declarado de ESTA palabra.
    expect(screen.getByText("Understood but not produced yet")).toBeTruthy();
  });

  it("encadena: al superar el peldaño ofrece «Siguiente palabra» y avanza a la última", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 2,
        items: [dueWord("river"), dueWord("apple")],
      }),
    );
    mocks.submitDrillWriteAttempt.mockResolvedValue({
      word: "river",
      passed: true,
      used_word: true,
      too_short: false,
      score: 100,
    });

    renderHarness();
    await writeAndSend("I sat by the river last summer.");

    // El drill NO se desmonta: el alumno lee el feedback y decide cuándo seguir.
    expect(await screen.findByRole("button", { name: "Next word" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Next word" }));

    await waitFor(() => expect(screen.getByText("2 of 2")).toBeTruthy());
    expect(
      await screen.findByText(/Write your own sentence using “apple”/),
    ).toBeTruthy();
  });

  it("la última palabra ofrece «Terminar» y al terminar vuelve al resumen refrescado", async () => {
    mocks.getReviewQueue
      .mockResolvedValueOnce(
        queue({ due_count: 1, items: [dueWord("river")] }),
      )
      // Tras terminar, la cola del día ya está vacía.
      .mockResolvedValue(queue({}));
    mocks.submitDrillWriteAttempt.mockResolvedValue({
      word: "river",
      passed: true,
      used_word: true,
      too_short: false,
      score: 100,
    });

    renderHarness();
    await writeAndSend("I sat by the river last summer.");

    const finish = await screen.findByRole("button", { name: "Finish" });
    expect(screen.queryByRole("button", { name: "Next word" })).toBeNull();
    fireEvent.click(finish);

    expect(
      await screen.findByText("Nothing to review right now — come back later."),
    ).toBeTruthy();
  });

  it("cerrar a mitad de sesión también vuelve al resumen", async () => {
    mocks.getReviewQueue
      .mockResolvedValueOnce(queue({ due_count: 2, items: [dueWord("river"), dueWord("apple")] }))
      .mockResolvedValue(queue({}));

    renderHarness();
    fireEvent.click(await screen.findByRole("button", { name: "Close" }));

    expect(
      await screen.findByText("Nothing to review right now — come back later."),
    ).toBeTruthy();
  });

  it("declara el `why` del planner para la palabra que se está trabajando", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 1,
        items: [
          dueWord("river", {
            why: "production gap; due for review (memory decayed)",
          }),
        ],
      }),
    );
    renderHarness();

    expect(
      await screen.findByText(/production gap; due for review \(memory decayed\)/),
    ).toBeTruthy();

    const line = screen.getByText(/production gap; due for review/);
    expect(line.textContent).toBe(
      "Why? production gap; due for review (memory decayed)",
    );
  });

  it("muestra la confianza de transferencia cuando hay evidencia (V3.49)", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 1,
        items: [
          dueWord("river", {
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
          }),
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

    renderHarness();

    const badge = await screen.findByText("Transfer evidence: solid");
    expect(badge.getAttribute("title")).toContain("internal protocol");
    // La transferencia NO revela la palabra esperada.
    expect(screen.queryByText("river")).toBeNull();
  });

  it("muestra los motivos DECLARADOS de la decisión cuando hay proyección (V3.64)", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 1,
        items: [
          dueWord("river", {
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
          }),
        ],
      }),
    );

    renderHarness();

    const line = await screen.findByText(/In your growth zone/);
    expect(line.textContent).toContain("Large gap");
    expect(line.textContent).toContain("Transfer: building");
    expect(line.textContent).toContain("Due for review");
    expect(line.textContent).toContain("Costly recall");
    expect(line.textContent).toContain("Assessment confidence: medium");
    expect(line.getAttribute("title")).toContain("not a claim of mastery");
  });

  it("no inventa motivos cuando el estado no declara medida (V3.64)", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 1,
        items: [
          dueWord("river", {
            decision: {
              skill: "",
              activity: "write",
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
          }),
        ],
      }),
    );

    renderHarness();

    await screen.findByText(/Write your own sentence/);
    expect(screen.queryByText(/growth zone/)).toBeNull();
    expect(screen.queryByText(/Large gap/)).toBeNull();
  });
});

describe("ReviewToday · contratos incompletos (V3.77.2)", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("un `items` no-array pero truthy no llega al render", async () => {
    // El `queue?.items ?? []` de antes solo cubría null/undefined: un objeto o
    // una cadena *truthy* pasaba la guardia y reventaba en `items.map`.
    mocks.getReviewQueue.mockResolvedValue({
      due_count: 3,
      items: { 0: "river" },
      fsrs_version: "2.11.0-lite",
    } as never);

    renderHarness();

    // Cae al estado vacío honesto en vez de tumbar la pantalla.
    expect(await screen.findByText(/Nothing to review/)).toBeTruthy();
  });

  it("elementos no-objeto dentro del array se descartan", async () => {
    mocks.getReviewQueue.mockResolvedValue({
      due_count: 2,
      items: ["basura", 7, null],
      fsrs_version: "2.11.0-lite",
    } as never);

    renderHarness();

    expect(await screen.findByText(/Nothing to review/)).toBeTruthy();
  });

  it("un fallo de carga no finge una cola vacía", async () => {
    mocks.getReviewQueue.mockRejectedValue(new Error("down"));

    renderHarness();

    expect(
      await screen.findByText(/Could not load the review queue/),
    ).toBeTruthy();
  });
});

describe("ReviewToday · peldaños reconductivos y accesibilidad (V3.85.1)", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  // C1 (P0 de la auditoría AY): antes la sesión avanzaba SOLO con `onProduced`,
  // que Recognition/Recall nunca disparan; un ítem servido en uno de esos
  // peldaños quedaba clavado sin ofrecer «Siguiente palabra».
  it("un ítem servido como recognition avanza al dar veredicto y encadena (C1)", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 2,
        items: [
          dueWord("river", { activity: "recognition", decision_id: "d-river" }),
          dueWord("apple", { activity: "recognition", decision_id: "d-apple" }),
        ],
      }),
    );
    mocks.getDrillRecognitionQuestion.mockResolvedValue({
      word: "river",
      available: true,
      question_id: "q1",
      options: ["río", "mar"],
    });
    mocks.submitDrillRecognitionAttempt.mockResolvedValue({
      word: "river",
      correct: true,
      correct_index: 0,
      selected_index: 0,
    });

    renderHarness();

    await screen.findByText("1 of 2");
    // Sin veredicto todavía no hay avance.
    expect(screen.queryByRole("button", { name: "Next word" })).toBeNull();

    fireEvent.click(await screen.findByRole("button", { name: "río" }));
    fireEvent.click(screen.getByRole("button", { name: "Check answer" }));

    // El veredicto (sin producción) ofrece avanzar y la cola encadena.
    expect(
      await screen.findByRole("button", { name: "Next word" }),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Next word" }));
    await waitFor(() => expect(screen.getByText("2 of 2")).toBeTruthy());
  });

  it("un ítem servido como recall avanza al dar veredicto (C1)", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({
        due_count: 1,
        items: [
          dueWord("river", {
            activity: "recall",
            reason: "no_recall_evidence",
          }),
        ],
      }),
    );
    mocks.getDrillRecallPrompt.mockResolvedValue({
      word: "river",
      available: true,
      cue: "río",
      cue_kind: "translation",
    });
    mocks.submitDrillRecallAttempt.mockResolvedValue({
      word: "river",
      correct: true,
      expected: "river",
      delayed: false,
      recall_days: 1,
      error_type: "correct",
    });

    renderHarness();

    fireEvent.change(await screen.findByLabelText("Type the word"), {
      target: { value: "river" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check" }));

    // Última palabra de la cola: el CTA es «Terminar».
    expect(await screen.findByRole("button", { name: "Finish" })).toBeTruthy();
  });

  it("el contador es región viva y el foco viaja al CTA (a11y)", async () => {
    mocks.getReviewQueue.mockResolvedValue(
      queue({ due_count: 2, items: [dueWord("river"), dueWord("apple")] }),
    );
    mocks.submitDrillWriteAttempt.mockResolvedValue({
      word: "river",
      passed: true,
      used_word: true,
      word_count: 6,
      min_words: 4,
    });

    renderHarness();

    const progress = await screen.findByText("1 of 2");
    expect(progress.getAttribute("role")).toBe("status");
    expect(progress.getAttribute("aria-live")).toBe("polite");
    expect(progress.getAttribute("aria-atomic")).toBe("true");

    await writeAndSend("I sat by the river last summer.");

    const next = await screen.findByRole("button", { name: "Next word" });
    // El foco se mueve al CTA: el usuario de teclado no tabula por todo el drill.
    await waitFor(() => expect(document.activeElement).toBe(next));
  });
});
