// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
}));

vi.mock("../../components/ItemReplayButton", () => ({
  ItemReplayButton: () => <button type="button">audio</button>,
}));

const item: StudyLessonItem = {
  item_id: "item-bank",
  word: "bank",
  cefr: "A2",
  card_type: "lexicon",
  card_id: "bank",
  deck_id: 0,
  is_new: true,
  translation: "banco",
  definition: "",
  facets: {},
  state: "new",
};

afterEach(() => cleanup());

describe("WordLesson", () => {
  it("un salto deja el paso pendiente y los que no aplican quedan en na", async () => {
    const onComplete = vi.fn().mockResolvedValue(undefined);
    render(
      <I18nProvider lang="en" setLang={() => {}}>
        <WordLesson
          userId="u1"
          items={[item]}
          deckName="All"
          onComplete={onComplete}
          onExit={() => {}}
        />
      </I18nProvider>,
    );

    expect(await screen.findByText("Meaning")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Pronunciation")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(await screen.findByText("Context")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Meanings in context")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    fireEvent.click(await screen.findByRole("button", { name: "Good" }));

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
    );
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
