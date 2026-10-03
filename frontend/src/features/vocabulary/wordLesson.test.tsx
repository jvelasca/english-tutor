// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../hooks/useI18n";
import type { StudyLessonItem } from "../../types/api";
import { extraSteps, WordLesson } from "./wordLesson";

vi.mock("../../api/vocabulary", () => ({
  lookupDictionaryWord: vi.fn().mockResolvedValue({
    word: "bank",
    translation: "banco",
    meanings: [
      { term: "banco", pos: "noun", gloss: "finanzas", domain: "", proper_noun: false },
      { term: "orilla", pos: "noun", gloss: "río", domain: "", proper_noun: false },
    ],
    senses: [{ lemma: "bank", pos: "noun", gloss: "" }],
    example: { phrase: "I went to the bank.", source: "corpus", level: "A2" },
  }),
  requestStudyExample: vi.fn(),
}));

vi.mock("../../components/ItemReplayButton", () => ({
  ItemReplayButton: ({ onPlay }: { onPlay?: () => void }) => (
    <button type="button" onClick={() => onPlay?.()}>
      audio
    </button>
  ),
}));

import { requestStudyExample } from "../../api/vocabulary";

function lessonItem(overrides: Partial<StudyLessonItem> = {}): StudyLessonItem {
  return {
    item_id: "item-bank",
    word: "bank",
    cefr: "A2",
    card_type: "lexicon",
    card_id: "bank",
    deck_id: 0,
    is_new: true,
    translation: "banco",
    definition: "",
    mnemonic: "dinero junto al río",
    facets: {},
    state: "new",
    ...overrides,
  };
}

function renderLesson(items: StudyLessonItem[], onComplete = vi.fn().mockResolvedValue(undefined)) {
  render(
    <I18nProvider lang="en" setLang={() => {}}>
      <WordLesson userId="u1" items={items} deckName="All" onComplete={onComplete} onExit={() => {}} />
    </I18nProvider>,
  );
  return onComplete;
}

afterEach(() => cleanup());

describe("WordLesson", () => {
  it("revelar y calificar cierra la carta y deja pendientes lo que no se usó", async () => {
    const onComplete = renderLesson([lessonItem()]);

    expect(screen.queryByRole("button", { name: "Good" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Show the meaning" }));
    expect(await screen.findByText("I went to the bank.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Good" }));

    await waitFor(() =>
      expect(onComplete).toHaveBeenCalledWith(
        expect.objectContaining({
          item_id: "item-bank",
          grade: 3,
          facets: expect.objectContaining({
            meaning: "done",
            pronunciation: "pending",
            context: "done",
            senses: "pending",
            related: "na",
          }),
        }),
      ),
    );
  });

  it("la pista descubre un trozo y el recordatorio no cierra la carta", () => {
    const onComplete = renderLesson([lessonItem()]);
    fireEvent.click(screen.getByRole("button", { name: "Hint" }));
    expect(screen.getByText("ban…")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Reminder" }));
    expect(screen.getByText("dinero junto al río")).toBeTruthy();
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("una opción falsa no cierra; la correcta revela y la nota sí cierra", async () => {
    const words = ["banco", "casa", "río", "tren", "libro", "mesa"];
    const items = words.map((translation, index) =>
      lessonItem({
        item_id: `item-${index}`,
        word: `word${index}`,
        translation,
        mnemonic: "",
      }),
    );
    const onComplete = renderLesson(items);
    fireEvent.click(screen.getByRole("button", { name: "Which meaning?" }));
    fireEvent.click(screen.getByRole("button", { name: "casa" }));
    expect(onComplete).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Good" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "banco" }));
    await waitFor(() => {
      const good = screen.getByRole("button", { name: "Good" }) as HTMLButtonElement;
      expect(good.disabled).toBe(false);
    });
    fireEvent.click(screen.getByRole("button", { name: "Good" }));
    await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
  });

  it("oír la palabra marca la pronunciación hecha", async () => {
    const onComplete = renderLesson([lessonItem({ mnemonic: "" })]);
    fireEvent.click(screen.getAllByRole("button", { name: "audio" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "Show the meaning" }));
    await waitFor(() => {
      const good = screen.getByRole("button", { name: "Good" }) as HTMLButtonElement;
      expect(good.disabled).toBe(false);
    });
    fireEvent.click(screen.getByRole("button", { name: "Good" }));
    await waitFor(() =>
      expect(onComplete).toHaveBeenCalledWith(
        expect.objectContaining({
          facets: expect.objectContaining({ pronunciation: "done" }),
        }),
      ),
    );
  });

  it("otra frase sustituye el ejemplo y un fallo conserva la anterior", async () => {
    vi.mocked(requestStudyExample).mockResolvedValueOnce({
      word: "bank",
      phrase: "The bank opens at nine.",
      translation: "El banco abre a las nueve.",
    });
    renderLesson([lessonItem({ mnemonic: "" })]);
    fireEvent.click(screen.getByRole("button", { name: "Show the meaning" }));
    expect(await screen.findByText("I went to the bank.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Another sentence" }));
    expect(await screen.findByText("The bank opens at nine.")).toBeTruthy();
    expect(screen.getByText("El banco abre a las nueve.")).toBeTruthy();

    vi.mocked(requestStudyExample).mockRejectedValueOnce(new Error("down"));
    fireEvent.click(screen.getByRole("button", { name: "Another sentence" }));
    expect(await screen.findByText("Could not make another sentence.")).toBeTruthy();
    expect(screen.getByText("The bank opens at nine.")).toBeTruthy();
  });

  it("no ofrece acepciones ni relación cuando el diccionario no las trae", () => {
    expect(
      extraSteps(
        {
          word: "cup",
          meanings: [{ term: "taza", pos: "noun", gloss: "", domain: "", proper_noun: false }],
          senses: [{ lemma: "cup", pos: "noun", gloss: "" }],
        } as never,
        "cup",
      ),
    ).toEqual([]);
  });
});
