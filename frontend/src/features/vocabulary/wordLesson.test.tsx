// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../hooks/useI18n";
import type { StudyLessonItem } from "../../types/api";
import { extraSteps, helpPhrase, sameSpelling, syllableEnd, WordLesson } from "./wordLesson";

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
  requestStudyQuiz: vi.fn().mockResolvedValue({
    choices: ["banco", "casa", "río", "tren", "libro", "mesa"],
  }),
  requestStudyHint: vi.fn().mockResolvedValue({
    word: "bank",
    hint: "lugar donde se guarda el dinero",
  }),
  setVocabularyTranslation: vi.fn().mockResolvedValue({}),
}));

vi.mock("../../api/translate", () => ({
  translateText: vi.fn().mockResolvedValue("Fui al banco."),
}));

vi.mock("../../components/ItemReplayButton", () => ({
  ItemReplayButton: ({
    onPlay,
    language,
  }: {
    onPlay?: () => void;
    language?: string;
  }) => (
    <button type="button" data-lang={language} onClick={() => onPlay?.()}>
      audio
    </button>
  ),
}));

import {
  lookupDictionaryWord,
  requestStudyExample,
  requestStudyHint,
  requestStudyQuiz,
  setVocabularyTranslation,
} from "../../api/vocabulary";

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

function renderLesson(
  items: StudyLessonItem[],
  onComplete = vi.fn().mockResolvedValue(undefined),
  onEditCard?: (cardId: number) => void,
  direction: "en-es" | "es-en" = "en-es",
) {
  render(
    <I18nProvider lang="en" setLang={() => {}}>
      <WordLesson
        userId="u1"
        items={items}
        deckName="All"
        onComplete={onComplete}
        onExit={() => {}}
        onEditCard={onEditCard}
        direction={direction}
      />
    </I18nProvider>,
  );
  return onComplete;
}

async function whenEnabled(name: string) {
  await waitFor(() => {
    expect((screen.getByRole("button", { name }) as HTMLButtonElement).disabled).toBe(false);
  });
}

afterEach(() => cleanup());

describe("WordLesson", () => {
  it("revelar y calificar cierra la carta y deja pendientes lo que no se usó", async () => {
    const onComplete = renderLesson([lessonItem()]);

    expect(screen.queryByRole("button", { name: "Good" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Show the meaning" }));
    expect(await screen.findByText("I went to the bank.")).toBeTruthy();
    expect(
      screen.getAllByRole("button", { name: "audio" }).map((button) => button.getAttribute("data-lang")),
    ).toContain("es");
    fireEvent.click(screen.getByRole("button", { name: "Good" }));

    await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
    const close = onComplete.mock.calls[0][0];
    expect(Object.keys(close).sort()).toEqual(["facets", "grade", "item_id", "translation"]);
    expect(close).toEqual(
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

  it("la sílaba descubre el siguiente grupo vocálico y el recordatorio no cierra", () => {
    const onComplete = renderLesson([lessonItem()]);
    fireEvent.click(screen.getByRole("button", { name: "Syllable" }));
    expect(screen.getByText("ba…")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Hint" }));
    expect(screen.getByText("dinero junto al río")).toBeTruthy();
    expect(requestStudyHint).not.toHaveBeenCalled();
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("sin recordatorio, Pista pide una y la muestra sin cerrar", async () => {
    vi.mocked(requestStudyHint).mockClear();
    const onComplete = renderLesson([lessonItem({ mnemonic: "" })]);
    fireEvent.click(screen.getByRole("button", { name: "Hint" }));
    expect(await screen.findByText("lugar donde se guarda el dinero")).toBeTruthy();
    expect(requestStudyHint).toHaveBeenCalledWith({
      word: "bank",
      translation: "banco",
      cardType: "lexicon",
      cardId: "bank",
      direction: "en-es",
    });
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("la opción correcta revela y la nota sí cierra", async () => {
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
    await whenEnabled("banco");
    fireEvent.click(screen.getByRole("button", { name: "banco" }));
    await waitFor(() => {
      const good = screen.getByRole("button", { name: "Good" }) as HTMLButtonElement;
      expect(good.disabled).toBe(false);
    });
    fireEvent.click(screen.getByRole("button", { name: "Good" }));
    await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
    expect(onComplete.mock.calls[0][0].grade).toBe(3);
  });

  it("una opción falsa queda en rojo y se anota una sola vez como Otra vez", async () => {
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
    await whenEnabled("casa");
    fireEvent.click(screen.getByRole("button", { name: "casa" }));
    expect(screen.getByRole("button", { name: "casa" }).className).toMatch(/text-destructive/);
    expect(screen.getAllByText("banco").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Good" })).toBeNull();
    await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
    expect(onComplete.mock.calls[0][0]).toEqual(
      expect.objectContaining({ item_id: "item-0", grade: 1 }),
    );
    await whenEnabled("Next");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("word1")).toBeTruthy();
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("la frase del diccionario se abre en el anverso y no cierra", async () => {
    const onComplete = renderLesson([lessonItem({ mnemonic: "" })]);
    fireEvent.click(await screen.findByRole("button", { name: /^Sentence$/ }));
    expect(await screen.findByText("I went to the bank.")).toBeTruthy();
    expect(screen.queryByText("banco")).toBeNull();
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("el lápiz de una ficha manual abre su edición", () => {
    const onEditCard = vi.fn();
    const onComplete = renderLesson(
      [lessonItem({ card_type: "flashcard", card_id: "12", deck_id: 2 })],
      vi.fn().mockResolvedValue(undefined),
      onEditCard,
    );
    fireEvent.click(screen.getByRole("button", { name: "Edit this card" }));
    expect(onEditCard).toHaveBeenCalledWith(12);
    expect(setVocabularyTranslation).not.toHaveBeenCalled();
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("el lápiz de una palabra del léxico guarda la traducción y no cierra", async () => {
    const onComplete = renderLesson([lessonItem()]);
    fireEvent.click(screen.getByRole("button", { name: "Edit this card" }));
    fireEvent.change(screen.getByLabelText("Reverse side (Spanish)"), {
      target: { value: "ancla" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(setVocabularyTranslation).toHaveBeenCalledWith("u1", "bank", "ancla"),
    );
    expect(onComplete).not.toHaveBeenCalled();
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

  it("otra frase se suma a la lista y un fallo conserva las anteriores", async () => {
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
    expect(screen.getByText("I went to the bank.")).toBeTruthy();

    vi.mocked(requestStudyExample).mockRejectedValueOnce(new Error("down"));
    fireEvent.click(screen.getByRole("button", { name: "Another sentence" }));
    expect(await screen.findByText("Could not make another sentence.")).toBeTruthy();
    expect(screen.getByText("I went to the bank.")).toBeTruthy();
    expect(screen.getByText("The bank opens at nine.")).toBeTruthy();
  });

  it("otra frase se detiene al llegar a cuatro", async () => {
    vi.mocked(requestStudyExample).mockClear();
    for (const phrase of ["One bank.", "Two banks.", "Three banks."]) {
      vi.mocked(requestStudyExample).mockResolvedValueOnce({
        word: "bank",
        phrase,
        translation: phrase,
      });
    }
    renderLesson([lessonItem({ mnemonic: "" })]);
    fireEvent.click(screen.getByRole("button", { name: "Show the meaning" }));
    expect(await screen.findByText("I went to the bank.")).toBeTruthy();
    for (const phrase of ["One bank.", "Two banks.", "Three banks."]) {
      fireEvent.click(screen.getByRole("button", { name: "Another sentence" }));
      expect(await screen.findByText(phrase)).toBeTruthy();
    }
    expect(screen.getByText("I went to the bank.")).toBeTruthy();
    expect(
      (screen.getByRole("button", { name: "Another sentence" }) as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(requestStudyExample).toHaveBeenCalledTimes(3);
  });

  it("escribir la palabra bien revela y un fallo no cierra", () => {
    const onComplete = renderLesson([lessonItem({ mnemonic: "" })]);
    fireEvent.click(screen.getByRole("button", { name: "Write" }));
    expect(screen.queryByText("bank")).toBeNull();
    fireEvent.change(screen.getByLabelText("Type the word"), { target: { value: "bench" } });
    fireEvent.click(screen.getByRole("button", { name: "Check" }));
    expect(screen.getByText("That's not the word. Try again.")).toBeTruthy();
    expect(onComplete).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Good" })).toBeNull();

    fireEvent.change(screen.getByLabelText("Type the word"), { target: { value: "  Bank " } });
    fireEvent.click(screen.getByRole("button", { name: "Check" }));
    expect(screen.getByText("bank")).toBeTruthy();
    expect(screen.getByText("banco")).toBeTruthy();
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("ES → EN muestra el español y escribir comprueba el inglés", async () => {
    vi.mocked(requestStudyQuiz).mockResolvedValueOnce({
      choices: ["wrench", "hammer", "knife", "river", "truck", "house"],
    });
    const onComplete = renderLesson(
      [
        lessonItem({
          item_id: "item-wrench",
          word: "wrench",
          translation: "llave",
          mnemonic: "",
        }),
        lessonItem({
          item_id: "item-hammer",
          word: "hammer",
          translation: "martillo",
          mnemonic: "",
        }),
      ],
      undefined,
      undefined,
      "es-en",
    );
    expect(screen.getByText("llave")).toBeTruthy();
    expect(screen.queryByText("wrench")).toBeNull();
    expect(screen.getByRole("button", { name: "audio" }).getAttribute("data-lang")).toBe("es");

    fireEvent.click(screen.getByRole("button", { name: "Syllable" }));
    expect(screen.getByText("wre…")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Write" }));
    fireEvent.click(screen.getByRole("button", { name: "Syllable" }));
    expect(screen.getByText("wre…")).toBeTruthy();
    expect(screen.queryByText("lla…")).toBeNull();

    fireEvent.change(screen.getByLabelText("Type the word"), { target: { value: "llave" } });
    fireEvent.click(screen.getByRole("button", { name: "Check" }));
    expect(screen.getByText("That's not the word. Try again.")).toBeTruthy();
    expect(screen.queryByText("wrench")).toBeNull();

    fireEvent.change(screen.getByLabelText("Type the word"), { target: { value: "wrench" } });
    fireEvent.click(screen.getByRole("button", { name: "Check" }));
    expect(screen.getByText("wrench")).toBeTruthy();
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("en los dos sentidos, escribir y la sílaba de después buscan la palabra inglesa", () => {
    const card = lessonItem({
      word: "allen wrench",
      translation: "llave allen",
      mnemonic: "",
    });

    renderLesson([card]);
    fireEvent.click(screen.getByRole("button", { name: "Syllable" }));
    expect(screen.getByText("lla…")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Write" }));
    fireEvent.click(screen.getByRole("button", { name: "Syllable" }));
    expect(screen.getByText("a…")).toBeTruthy();
    expect(screen.queryByText("lla…")).toBeNull();
    fireEvent.change(screen.getByLabelText("Type the word"), {
      target: { value: "llave allen" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check" }));
    expect(screen.getByText("That's not the word. Try again.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Type the word"), {
      target: { value: "  Allen   wrench " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check" }));
    expect(screen.getByText("allen wrench")).toBeTruthy();
    expect(screen.getByText("llave allen")).toBeTruthy();

    cleanup();
    renderLesson([card], undefined, undefined, "es-en");
    expect(screen.getByText("llave allen")).toBeTruthy();
    expect(screen.queryByText("allen wrench")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Syllable" }));
    expect(screen.getByText("a…")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Write" }));
    fireEvent.click(screen.getByRole("button", { name: "Syllable" }));
    expect(screen.getByText("a…")).toBeTruthy();
    expect(screen.queryByText("lla…")).toBeNull();
    const hint = screen.getByText("a…");
    expect(hint.getAttribute("lang")).toBe("en");
    fireEvent.change(screen.getByLabelText("Type the word"), {
      target: { value: "llave allen" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check" }));
    expect(screen.getByText("That's not the word. Try again.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Good" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Type the word"), {
      target: { value: "allen wrench" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check" }));
    expect(screen.getByText("allen wrench")).toBeTruthy();
    expect(screen.getByText("llave allen")).toBeTruthy();
  });

  it("ES → EN el quiz acierta con la palabra inglesa y no cierra", async () => {
    vi.mocked(requestStudyQuiz).mockResolvedValueOnce({
      choices: ["wrench", "hammer", "knife", "river", "truck", "house"],
    });
    const onComplete = renderLesson(
      [
        lessonItem({
          item_id: "item-wrench",
          word: "wrench",
          translation: "llave",
          mnemonic: "",
        }),
        lessonItem({
          item_id: "item-hammer",
          word: "hammer",
          translation: "martillo",
          mnemonic: "",
        }),
      ],
      undefined,
      undefined,
      "es-en",
    );
    fireEvent.click(screen.getByRole("button", { name: "Which meaning?" }));
    await whenEnabled("wrench");
    expect(requestStudyQuiz).toHaveBeenCalledWith("wrench", "llave", ["hammer"], "es-en");
    fireEvent.click(screen.getByRole("button", { name: "wrench" }));
    expect(screen.getByRole("button", { name: "Good" })).toBeTruthy();
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("ES → EN la frase se ve en español y el inglés queda detrás", async () => {
    renderLesson([lessonItem({ mnemonic: "" })], undefined, undefined, "es-en");
    fireEvent.click(await screen.findByRole("button", { name: "Sentence" }));
    expect(await screen.findByText("Fui al banco.")).toBeTruthy();
    expect(screen.queryByText("I went to the bank.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Back to English" }));
    expect(screen.getByText("I went to the bank.")).toBeTruthy();
  });

  it("sin español, ES → EN estudia esa ficha en inglés", async () => {
    vi.mocked(lookupDictionaryWord).mockResolvedValueOnce({
      word: "bank",
      translation: "",
      meanings: [],
      senses: [],
    } as never);
    renderLesson(
      [lessonItem({ translation: "", mnemonic: "" })],
      undefined,
      undefined,
      "es-en",
    );
    expect(await screen.findByRole("button", { name: "Show the meaning" })).toBeTruthy();
    expect(screen.getByText("bank")).toBeTruthy();
  });

  it("al escribir, la sílaba es de la palabra inglesa", () => {
    renderLesson([lessonItem({ translation: "el banco de la esquina", mnemonic: "" })]);
    fireEvent.click(screen.getByRole("button", { name: "Write" }));
    fireEvent.click(screen.getByRole("button", { name: "Syllable" }));
    expect(screen.getByText("ba…")).toBeTruthy();
    expect(screen.queryByText(/^el/)).toBeNull();
  });

  it("la sílaba y la grafía coinciden con el proxy de grupos vocálicos", () => {
    expect(syllableEnd("banco", 0)).toBe(2);
    expect(syllableEnd("banco", 2)).toBe(5);
    expect(sameSpelling("  Bank ", "bank")).toBe(true);
    expect(sameSpelling("bench", "bank")).toBe(false);
    expect(helpPhrase({ example: { phrase: "I went to the bank." } } as never)).toBe(
      "I went to the bank.",
    );
    expect(
      helpPhrase({
        example: null,
        senses: [{ example: "The law will make a difference." }],
      } as never),
    ).toBe("The law will make a difference.");
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
