/**
 * Lección de una palabra en Estudiar.
 *
 * EN→ES se lee el inglés y se descubre el español. ES→EN es el espejo: se lee
 * el español y se descubre el inglés. Sin traducción, esa ficha se queda en
 * EN→ES. Una sílaba descubre el siguiente grupo vocálico de lo que está oculto.
 * La frase del diccionario se puede abrir en el anverso, en el idioma que se
 * pregunta. «¿Cuál es?» pide opciones al diccionario, no al mazo. Pista muestra
 * el recordatorio o pide uno. El primer fallo de «¿Cuál es?» guarda Otra vez;
 * el resto de la nota sigue saliendo por los cuatro botones, con el `item_id`.
 */
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Baseline,
  Eye,
  Flame,
  Lightbulb,
  ListChecks,
  Pencil,
  Quote,
  RotateCcw,
  Sparkles,
  SquarePen,
  ThumbsUp,
} from "lucide-react";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { ItemReplayButton } from "../../components/ItemReplayButton";
import {
  PhraseTranslateButton,
  usePhraseTranslation,
} from "../../components/PhraseTranslate";
import {
  lookupDictionaryWord,
  requestStudyExample,
  requestStudyHint,
  requestStudyQuiz,
  setVocabularyTranslation,
} from "../../api/vocabulary";
import { useI18n } from "../../hooks/useI18n";
import { cn } from "../../lib/utils";
import { directionClass, directionLabelKey } from "../../utils/dictionaryDirection";
import type {
  DictionaryEntry,
  LessonFacet,
  StudyDirection,
  StudyLessonItem,
} from "../../types/api";

const GRADE_KEY: Record<number, string> = {
  1: "fsrs.grade.again",
  2: "fsrs.grade.hard",
  3: "fsrs.grade.good",
  4: "fsrs.grade.easy",
};

const GRADE_ICON: Record<number, typeof RotateCcw> = {
  1: RotateCcw,
  2: Flame,
  3: ThumbsUp,
  4: Sparkles,
};

export interface LessonClose {
  item_id: string;
  grade: number;
  facets: Record<string, string>;
  translation: string;
}

interface ExampleLine {
  phrase: string;
  translation: string;
}

const MAX_EXAMPLES = 4;
const VOWELS = new Set(["a", "e", "i", "o", "u", "y"]);

function foldSpelling(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

/** Misma palabra, sin distinguir mayúsculas ni espacios de más. */
export function sameSpelling(typed: string, expected: string): boolean {
  const wanted = foldSpelling(expected);
  return wanted.length > 0 && foldSpelling(typed) === wanted;
}

/** Pasos extra solo cuando el diccionario tiene con qué enseñarlos. */
export function extraSteps(entry: DictionaryEntry | null, word: string): LessonFacet[] {
  const extras: LessonFacet[] = [];
  const meanings = (entry?.meanings ?? []).filter(
    (meaning) => meaning.term && !meaning.proper_noun,
  );
  if (meanings.length > 1) extras.push("senses");
  const related = (entry?.senses ?? []).find(
    (sense) => sense.lemma && sense.lemma.toLowerCase() !== word.toLowerCase(),
  );
  if (related) extras.push("related");
  return extras;
}

/** Frase de ayuda: el ejemplo del diccionario, o el de la primera acepción. */
export function helpPhrase(entry: DictionaryEntry | null): string {
  const direct = entry?.example?.phrase?.trim() || "";
  if (direct) return direct;
  for (const sense of entry?.senses ?? []) {
    const phrase = sense.example?.trim() || "";
    if (phrase) return phrase;
  }
  return "";
}

/** Índice tras la siguiente sílaba aproximada: onset y un grupo vocálico. */
export function syllableEnd(text: string, shown: number): number {
  const raw = text.trim();
  if (!raw || shown >= raw.length) return raw.length;
  let index = Math.max(0, shown);
  const start = index;
  while (index < raw.length && /\s/.test(raw[index])) index += 1;
  while (
    index < raw.length &&
    !VOWELS.has(raw[index].toLowerCase()) &&
    !/\s/.test(raw[index])
  ) {
    index += 1;
  }
  const vowelAt = index;
  while (index < raw.length && VOWELS.has(raw[index].toLowerCase())) index += 1;
  if (index === vowelAt) {
    while (index < raw.length && !/\s/.test(raw[index])) index += 1;
  }
  if (index === start) return Math.min(raw.length, start + 1);
  return index;
}

function ExampleRow({
  userId,
  phrase,
  knownTranslation = "",
  showSpanishFirst = false,
}: {
  userId: string;
  phrase: string;
  knownTranslation?: string;
  showSpanishFirst?: boolean;
}) {
  const spoken = usePhraseTranslation(phrase, phrase, {
    startInSpanish: showSpanishFirst,
    knownSpanish: knownTranslation,
  });
  const language = spoken.isSpanish ? "es" : "en";
  return (
    <div className="flex items-start gap-2">
      {spoken.display ? (
        <>
          <p className="text-base leading-relaxed" lang={language}>
            {spoken.display}
          </p>
          <ItemReplayButton userId={userId} prompt={spoken.display} language={language} />
        </>
      ) : null}
      <PhraseTranslateButton state={spoken} />
    </div>
  );
}

interface WordLessonProps {
  userId: string;
  items: StudyLessonItem[];
  deckName: string;
  onComplete: (close: LessonClose) => Promise<void>;
  onExit: () => void;
  /** Ficha manual: abre Tarjetas en el editor de ese id. */
  onEditCard?: (cardId: number) => void;
  /** Se fija al abrir la lección. ES→EN pregunta el español. */
  direction?: StudyDirection;
}

export function WordLesson({
  userId,
  items,
  deckName,
  onComplete,
  onExit,
  onEditCard,
  direction = "en-es",
}: WordLessonProps) {
  const { t } = useI18n();
  const [index, setIndex] = useState(0);
  const [entry, setEntry] = useState<DictionaryEntry | null>(null);
  const [lookupReady, setLookupReady] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [hintShown, setHintShown] = useState(0);
  const [writing, setWriting] = useState(false);
  const [typed, setTyped] = useState("");
  const [writeMiss, setWriteMiss] = useState(false);
  const [clue, setClue] = useState("");
  const [hintOpen, setHintOpen] = useState(false);
  const [hintBusy, setHintBusy] = useState(false);
  const [hintError, setHintError] = useState(false);
  const [quizChoices, setQuizChoices] = useState<string[] | null>(null);
  const [quizBusy, setQuizBusy] = useState(false);
  const [quizError, setQuizError] = useState(false);
  const [phraseOpen, setPhraseOpen] = useState(false);
  const [quizOpen, setQuizOpen] = useState(false);
  const [quizFailed, setQuizFailed] = useState(false);
  const [missSaved, setMissSaved] = useState(false);
  const [missed, setMissed] = useState<string[]>([]);
  const [editingBack, setEditingBack] = useState(false);
  const [draft, setDraft] = useState("");
  const [ownTranslation, setOwnTranslation] = useState<string | null>(null);
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState(false);
  const [heard, setHeard] = useState(false);
  const [sawExample, setSawExample] = useState(false);
  const [openedMore, setOpenedMore] = useState(false);
  const [examples, setExamples] = useState<ExampleLine[]>([]);
  const [generated, setGenerated] = useState(false);
  const [avoid, setAvoid] = useState<string[]>([]);
  const [exampleBusy, setExampleBusy] = useState(false);
  const [exampleError, setExampleError] = useState(false);
  const [saving, setSaving] = useState(false);
  const missLock = useRef(false);
  const [error, setError] = useState(false);
  const [reviewed, setReviewed] = useState(0);

  const item = items[index];

  useEffect(() => {
    if (!item) return;
    let alive = true;
    setEntry(null);
    setLookupReady(false);
    setRevealed(false);
    setHintShown(0);
    setWriting(false);
    setTyped("");
    setWriteMiss(false);
    setClue(item.mnemonic || "");
    setHintOpen(false);
    setHintBusy(false);
    setHintError(false);
    setQuizChoices(null);
    setQuizBusy(false);
    setQuizError(false);
    setPhraseOpen(false);
    setQuizOpen(false);
    setQuizFailed(false);
    setMissSaved(false);
    missLock.current = false;
    setMissed([]);
    setEditingBack(false);
    setDraft("");
    setOwnTranslation(null);
    setEditSaving(false);
    setEditError(false);
    setHeard(false);
    setSawExample(false);
    setOpenedMore(false);
    setExamples([]);
    setGenerated(false);
    setAvoid([]);
    setExampleBusy(false);
    setExampleError(false);
    setError(false);
    void lookupDictionaryWord(userId, item.word)
      .then((found) => {
        if (alive) setEntry(found);
      })
      .catch(() => {
        if (alive) setEntry(null);
      })
      .finally(() => {
        if (alive) setLookupReady(true);
      });
    return () => {
      alive = false;
    };
  }, [item, userId, direction]);

  useEffect(() => {
    if (!lookupReady || generated) return;
    const phrase = helpPhrase(entry);
    if (!phrase) return;
    setExamples([{ phrase, translation: "" }]);
    setSawExample(true);
    setAvoid([phrase]);
  }, [lookupReady, entry, generated]);

  if (!item) {
    return (
      <Card className="gap-3 p-5">
        <p className="text-sm font-medium">
          {t("flashcards.study.finished").replace("{n}", String(reviewed))}
        </p>
        <Button type="button" size="sm" variant="outline" onClick={onExit}>
          {t("flashcards.study.back")}
        </Button>
      </Card>
    );
  }

  const translation = ownTranslation ?? (item.translation || entry?.translation || "");
  const manualCardId =
    item.card_type === "flashcard" ? Number(item.card_id) : Number.NaN;
  const editsInCards = Number.isInteger(manualCardId) && manualCardId > 0;
  const reverse = direction === "es-en" && translation.trim().length > 0;
  const faceDirection = reverse ? "es-en" : "en-es";
  const prompt = reverse ? translation : item.word;
  const answer = reverse ? item.word : translation;
  const promptLang = reverse ? "es" : "en";
  const answerLang = reverse ? "en" : "es";
  // La sílaba descubre la cara oculta. Al escribir se pela la palabra inglesa,
  // que es lo que hay que teclear en los dos sentidos: en ES → EN no puede
  // cambiar al español que ya está a la vista.
  const hintSource = writing && !revealed ? item.word : answer;
  const hintText = hintSource.trim();
  const hint = hintText.slice(0, hintShown);
  const extras = extraSteps(entry, item.word);
  const meanings = (entry?.meanings ?? []).filter(
    (meaning) => meaning.term && !meaning.proper_noun,
  );
  const related = (entry?.senses ?? []).find(
    (sense) => sense.lemma && sense.lemma.toLowerCase() !== item.word.toLowerCase(),
  );

  function facetsForGrade(): Record<string, string> {
    return {
      meaning: "done",
      pronunciation: heard ? "done" : "pending",
      context: sawExample ? "done" : "pending",
      senses: extras.includes("senses") ? (openedMore ? "done" : "pending") : "na",
      related: extras.includes("related") ? (openedMore ? "done" : "pending") : "na",
    };
  }

  function advance() {
    const next = index + 1;
    setReviewed((count) => count + 1);
    if (next >= items.length) setIndex(items.length);
    else setIndex(next);
  }

  async function grade(value: number) {
    setSaving(true);
    setError(false);
    try {
      await onComplete({
        item_id: item.item_id,
        grade: value,
        facets: facetsForGrade(),
        translation,
      });
      advance();
    } catch {
      setError(true);
    } finally {
      setSaving(false);
    }
  }

  /** Otra vez, sin pasar de carta: Siguiente avanza cuando ya quedó guardada. */
  async function recordMiss(): Promise<boolean> {
    if (!lookupReady || missSaved || saving || missLock.current) return missSaved;
    missLock.current = true;
    setSaving(true);
    setError(false);
    try {
      await onComplete({
        item_id: item.item_id,
        grade: 1,
        facets: facetsForGrade(),
        translation,
      });
      setMissSaved(true);
      return true;
    } catch {
      missLock.current = false;
      setError(true);
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function goNext() {
    if (saving) return;
    if (!missSaved) {
      const saved = await recordMiss();
      if (!saved) return;
    }
    advance();
  }

  async function toggleHint() {
    if (hintOpen) {
      setHintOpen(false);
      return;
    }
    if (clue.trim()) {
      setHintOpen(true);
      return;
    }
    setHintBusy(true);
    setHintError(false);
    try {
      const result = await requestStudyHint({
        word: item.word,
        translation,
        cardType: item.card_type,
        cardId: item.card_id,
        direction: reverse ? "es-en" : "en-es",
      });
      if (!result.hint.trim()) {
        setHintError(true);
        return;
      }
      setClue(result.hint);
      setHintOpen(true);
    } catch {
      setHintError(true);
    } finally {
      setHintBusy(false);
    }
  }

  async function openQuiz() {
    if (quizOpen) {
      setQuizOpen(false);
      return;
    }
    if (quizChoices && quizChoices.length > 1) {
      setQuizOpen(true);
      return;
    }
    setQuizBusy(true);
    setQuizError(false);
    try {
      const exclude = items
        .filter((other) => other.item_id !== item.item_id)
        .map((other) => (reverse ? other.word : other.translation).trim())
        .filter(Boolean);
      const result = await requestStudyQuiz(
        item.word,
        translation,
        exclude,
        reverse ? "es-en" : "en-es",
      );
      if (result.choices.length < 2) {
        setQuizError(true);
        return;
      }
      setQuizChoices(result.choices);
      setQuizOpen(true);
    } catch {
      setQuizError(true);
    } finally {
      setQuizBusy(false);
    }
  }

  function beginEdit() {
    if (editsInCards) {
      onEditCard?.(manualCardId);
      return;
    }
    setDraft(translation);
    setEditError(false);
    setEditingBack(true);
  }

  async function saveBack() {
    if (editSaving) return;
    setEditSaving(true);
    setEditError(false);
    try {
      await setVocabularyTranslation(userId, item.word, draft.trim());
      setOwnTranslation(draft.trim());
      setEditingBack(false);
    } catch {
      setEditError(true);
    } finally {
      setEditSaving(false);
    }
  }

  function checkSpelling() {
    if (sameSpelling(typed, item.word)) {
      setWriteMiss(false);
      setWriting(false);
      setRevealed(true);
      return;
    }
    setWriteMiss(true);
  }

  async function anotherSentence() {
    if (examples.length >= MAX_EXAMPLES) return;
    setExampleBusy(true);
    setExampleError(false);
    try {
      const next = await requestStudyExample(item.word, avoid);
      if (!next.phrase) {
        setExampleError(true);
        return;
      }
      setGenerated(true);
      setExamples((current) => {
        if (current.length >= MAX_EXAMPLES) return current;
        if (current.some((line) => line.phrase === next.phrase)) return current;
        return [...current, { phrase: next.phrase, translation: next.translation }];
      });
      setSawExample(true);
      setAvoid((current) => [...current, next.phrase]);
    } catch {
      setExampleError(true);
    } finally {
      setExampleBusy(false);
    }
  }

  function pickChoice(choice: string) {
    if (quizFailed || saving || !lookupReady) return;
    if (choice.trim().toLowerCase() === answer.trim().toLowerCase()) {
      setRevealed(true);
      return;
    }
    setMissed((current) => (current.includes(choice) ? current : [...current, choice]));
    setQuizFailed(true);
    setRevealed(true);
    void recordMiss();
  }

  return (
    <Card className="relative gap-5 overflow-hidden p-5">
      <span
        aria-hidden="true"
        className={cn("absolute inset-x-0 top-0 h-1", directionClass(faceDirection), "dir-bar")}
      />
      <div className="flex items-center justify-between gap-2">
        <p className="flex min-w-0 flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>{deckName}</span>
          {item.cefr ? <span>{item.cefr}</span> : null}
          <span
            className={cn(
              "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
              directionClass(faceDirection),
              "dir-chip",
            )}
          >
            {t(directionLabelKey(faceDirection))}
          </span>
        </p>
        <div className="flex items-center gap-3">
          <p className="text-xs tabular-nums text-muted-foreground">
            {t("flashcards.lesson.progress")
              .replace("{n}", String(index + 1))
              .replace("{total}", String(items.length))}
          </p>
          <button
            type="button"
            className="text-xs font-medium text-muted-foreground hover:text-foreground"
            onClick={onExit}
          >
            {t("flashcards.study.exit")}
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {writing && !revealed ? (
          <form
            className="flex flex-1 flex-col gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              checkSpelling();
            }}
          >
            <label className="flex flex-col gap-1 text-sm" htmlFor="lesson-write">
              {t("flashcards.lesson.writeLabel")}
              <input
                id="lesson-write"
                value={typed}
                autoComplete="off"
                className="rounded-md border border-border bg-background px-3 py-2 text-lg"
                onChange={(event) => {
                  setTyped(event.target.value);
                  setWriteMiss(false);
                }}
              />
            </label>
            <Button type="submit" size="sm" variant="outline" className="w-fit">
              {t("flashcards.lesson.writeCheck")}
            </Button>
            {writeMiss ? (
              <p className="text-[11px] text-destructive">{t("flashcards.lesson.writeWrong")}</p>
            ) : null}
          </form>
        ) : (
          <p className="text-4xl font-semibold tracking-tight" lang={promptLang}>
            {prompt}
          </p>
        )}
        <ItemReplayButton
          userId={userId}
          prompt={prompt}
          language={promptLang}
          onPlay={promptLang === "en" ? () => setHeard(true) : undefined}
        />
        <Button
          type="button"
          size="icon"
          variant="ghost"
          aria-label={t("flashcards.lesson.edit")}
          title={t("flashcards.lesson.edit")}
          onClick={beginEdit}
        >
          <SquarePen aria-hidden="true" />
        </Button>
      </div>

      {editingBack ? (
        <form
          className="flex flex-col gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            void saveBack();
          }}
        >
          <input
            value={draft}
            autoFocus
            maxLength={500}
            aria-label={t("flashcards.study.backPlaceholder")}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            onChange={(event) => setDraft(event.target.value)}
          />
          <div className="flex items-center gap-2">
            <Button type="submit" size="sm" disabled={editSaving}>
              {editSaving ? t("common.saving") : t("common.save")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              disabled={editSaving}
              onClick={() => setEditingBack(false)}
            >
              {t("common.cancel")}
            </Button>
          </div>
          {editError ? (
            <p className="text-[11px] text-destructive">{t("flashcards.study.editError")}</p>
          ) : null}
        </form>
      ) : null}

      {revealed ? (
        <div className="flex items-center gap-3">
          <p className="text-lg text-muted-foreground" lang={answerLang}>
            {answer}
          </p>
          {answer.trim() ? (
            <ItemReplayButton
              userId={userId}
              prompt={answer}
              language={answerLang}
              onPlay={answerLang === "en" ? () => setHeard(true) : undefined}
            />
          ) : null}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {hint ? (
            <p
              className="text-lg tracking-wide text-muted-foreground"
              lang={writing ? "en" : answerLang}
              aria-live="polite"
            >
              {hint}
              {hint.length < hintText.length ? "…" : ""}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={() => setRevealed(true)}>
              <Eye aria-hidden="true" />
              {t(reverse ? "flashcards.lesson.revealWord" : "flashcards.lesson.reveal")}
            </Button>
            {hintText ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => setHintShown((shown) => syllableEnd(hintText, shown))}
              >
                <Baseline aria-hidden="true" />
                {t("flashcards.lesson.hint")}
              </Button>
            ) : null}
            <Button
              type="button"
              variant="outline"
              aria-pressed={writing}
              onClick={() => {
                setWriting((open) => !open);
                setTyped("");
                setWriteMiss(false);
                setHintShown(0);
              }}
            >
              <Pencil aria-hidden="true" />
              {t("flashcards.lesson.write")}
            </Button>
            {examples.length > 0 ? (
              <Button
                type="button"
                variant="outline"
                aria-pressed={phraseOpen}
                onClick={() => setPhraseOpen((open) => !open)}
              >
                <Quote aria-hidden="true" />
                {t("flashcards.lesson.phrase")}
              </Button>
            ) : null}
            <Button
              type="button"
              variant="outline"
              aria-pressed={hintOpen}
              disabled={hintBusy}
              onClick={() => void toggleHint()}
            >
              <Lightbulb aria-hidden="true" />
              {t("flashcards.lesson.mnemonic")}
            </Button>
            <Button
              type="button"
              variant="outline"
              aria-pressed={quizOpen}
              disabled={quizBusy || !translation.trim()}
              onClick={() => void openQuiz()}
            >
              <ListChecks aria-hidden="true" />
              {t("flashcards.lesson.quiz")}
            </Button>
          </div>
          {phraseOpen && examples[0] ? (
            <ExampleRow
              userId={userId}
              phrase={examples[0].phrase}
              knownTranslation={examples[0].translation}
              showSpanishFirst={reverse}
            />
          ) : null}
          {hintError ? (
            <p className="text-[11px] text-destructive">{t("flashcards.lesson.hintError")}</p>
          ) : null}
          {hintOpen && clue ? (
            <p className="text-sm text-muted-foreground">{clue}</p>
          ) : null}
          {quizError ? (
            <p className="text-[11px] text-destructive">{t("flashcards.lesson.quizError")}</p>
          ) : null}
        </div>
      )}

      {quizOpen && quizChoices && (!revealed || quizFailed) ? (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {quizChoices.map((choice) => {
            const wrong = missed.includes(choice);
            return (
              <Button
                key={choice}
                type="button"
                variant="outline"
                disabled={!lookupReady || wrong || quizFailed}
                className={
                  wrong
                    ? "border-destructive bg-destructive/10 text-destructive hover:bg-destructive/10 hover:text-destructive disabled:opacity-100"
                    : undefined
                }
                onClick={() => pickChoice(choice)}
              >
                {choice}
              </Button>
            );
          })}
        </div>
      ) : null}

      {revealed ? (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            {examples.map((line) => (
              <ExampleRow
                key={line.phrase}
                userId={userId}
                phrase={line.phrase}
                knownTranslation={line.translation}
                showSpanishFirst={reverse}
              />
            ))}
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="w-fit"
              disabled={exampleBusy || !lookupReady || examples.length >= MAX_EXAMPLES}
              onClick={() => void anotherSentence()}
            >
              <Quote aria-hidden="true" />
              {t("flashcards.lesson.another")}
            </Button>
            {exampleError ? (
              <p className="text-[11px] text-destructive">
                {t("flashcards.lesson.exampleError")}
              </p>
            ) : null}
          </div>

          {extras.length > 0 ? (
            <details
              onToggle={(event) => {
                if ((event.currentTarget as HTMLDetailsElement).open) setOpenedMore(true);
              }}
            >
              <summary className="cursor-pointer text-sm font-medium text-primary">
                {t("flashcards.lesson.more")}
              </summary>
              {extras.includes("senses") ? (
                <ul className="mt-2 flex flex-col gap-1 text-sm">
                  {meanings.map((meaning) => (
                    <li key={`${meaning.term}-${meaning.pos}`}>
                      <span className="font-medium">{meaning.term}</span>
                      {meaning.gloss ? ` — ${meaning.gloss}` : ""}
                    </li>
                  ))}
                </ul>
              ) : null}
              {extras.includes("related") && related?.lemma ? (
                <p className="mt-2 text-sm">
                  {t("flashcards.lesson.relatedTo").replace("{lemma}", related.lemma)}
                </p>
              ) : null}
            </details>
          ) : null}

          {quizFailed ? (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-medium text-destructive">
                {t("flashcards.lesson.missed")}
              </p>
              <Button
                type="button"
                className="w-fit"
                disabled={saving}
                onClick={() => void goNext()}
              >
                {t("flashcards.lesson.next")}
                <ArrowRight aria-hidden="true" />
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-medium text-muted-foreground">
                {t("flashcards.lesson.gradePrompt")}
              </p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {[1, 2, 3, 4].map((value) => {
                  const Icon = GRADE_ICON[value];
                  return (
                    <Button
                      key={value}
                      type="button"
                      variant={value === 3 ? "default" : "outline"}
                      disabled={saving || !lookupReady}
                      onClick={() => void grade(value)}
                    >
                      <Icon aria-hidden="true" />
                      {t(GRADE_KEY[value])}
                    </Button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      ) : null}

      {error ? (
        <p className="text-[11px] text-destructive">{t("flashcards.lesson.saveError")}</p>
      ) : null}
    </Card>
  );
}
