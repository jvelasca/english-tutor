/**
 * Lección de una palabra en Estudiar.
 *
 * Se lee la palabra en inglés. El significado se revela cuando el alumno lo
 * pide, acierta entre las opciones o agota la pista. La nota FSRS sigue
 * saliendo solo por los cuatro botones, con el `item_id` de la cola.
 */
import { useEffect, useMemo, useState } from "react";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { ItemReplayButton } from "../../components/ItemReplayButton";
import { lookupDictionaryWord, requestStudyExample } from "../../api/vocabulary";
import { useI18n } from "../../hooks/useI18n";
import type { DictionaryEntry, LessonFacet, StudyLessonItem } from "../../types/api";

const GRADE_KEY: Record<number, string> = {
  1: "fsrs.grade.again",
  2: "fsrs.grade.hard",
  3: "fsrs.grade.good",
  4: "fsrs.grade.easy",
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

/** Cuántos caracteres de la traducción quedan a la vista tras una pista más. */
export function hintEnd(translation: string, shown: number): number {
  const text = translation.trim();
  if (!text || shown >= text.length) return text.length;
  const words = text.split(/\s+/);
  if (words.length > 1) {
    let cursor = 0;
    for (const word of words) {
      const at = text.indexOf(word, cursor);
      const end = at + word.length;
      if (end > shown) return end;
      cursor = end;
    }
    return text.length;
  }
  return Math.min(text.length, shown + 3);
}

/** Seis traducciones distintas, o null si la sesión no llega. */
export function quizChoices(items: StudyLessonItem[], current: StudyLessonItem): string[] | null {
  const correct = current.translation.trim();
  if (!correct) return null;
  const seen = new Set([correct.toLowerCase()]);
  const others: string[] = [];
  for (const item of items) {
    if (item.item_id === current.item_id) continue;
    const text = item.translation.trim();
    const key = text.toLowerCase();
    if (!text || seen.has(key)) continue;
    seen.add(key);
    others.push(text);
    if (others.length >= 5) break;
  }
  if (others.length < 5) return null;
  return shuffle([correct, ...others], current.item_id);
}

function shuffle(values: string[], seed: string): string[] {
  const out = [...values];
  let state = 0;
  for (const ch of seed) state = (Math.imul(state, 33) + ch.charCodeAt(0)) >>> 0;
  for (let index = out.length - 1; index > 0; index -= 1) {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    const swap = state % (index + 1);
    const left = out[index];
    out[index] = out[swap];
    out[swap] = left;
  }
  return out;
}

interface WordLessonProps {
  userId: string;
  items: StudyLessonItem[];
  deckName: string;
  onComplete: (close: LessonClose) => Promise<void>;
  onExit: () => void;
}

export function WordLesson({
  userId,
  items,
  deckName,
  onComplete,
  onExit,
}: WordLessonProps) {
  const { t } = useI18n();
  const [index, setIndex] = useState(0);
  const [entry, setEntry] = useState<DictionaryEntry | null>(null);
  const [lookupReady, setLookupReady] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [hintShown, setHintShown] = useState(0);
  const [reminderOpen, setReminderOpen] = useState(false);
  const [quizOpen, setQuizOpen] = useState(false);
  const [missed, setMissed] = useState<string[]>([]);
  const [heard, setHeard] = useState(false);
  const [sawExample, setSawExample] = useState(false);
  const [openedMore, setOpenedMore] = useState(false);
  const [example, setExample] = useState<ExampleLine | null>(null);
  const [generated, setGenerated] = useState(false);
  const [avoid, setAvoid] = useState<string[]>([]);
  const [exampleBusy, setExampleBusy] = useState(false);
  const [exampleError, setExampleError] = useState(false);
  const [saving, setSaving] = useState(false);
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
    setReminderOpen(false);
    setQuizOpen(false);
    setMissed([]);
    setHeard(false);
    setSawExample(false);
    setOpenedMore(false);
    setExample(null);
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
  }, [item, userId]);

  useEffect(() => {
    if (!lookupReady || generated) return;
    const phrase = entry?.example?.phrase?.trim() || "";
    if (!phrase) return;
    setExample({ phrase, translation: "" });
    setSawExample(true);
    setAvoid([phrase]);
  }, [lookupReady, entry, generated]);

  const choices = useMemo(
    () => (item ? quizChoices(items, item) : null),
    [items, item],
  );

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

  const translation = item.translation || entry?.translation || "";
  const hint = translation.trim().slice(0, hintShown);
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
      const next = index + 1;
      setReviewed((count) => count + 1);
      if (next >= items.length) setIndex(items.length);
      else setIndex(next);
    } catch {
      setError(true);
    } finally {
      setSaving(false);
    }
  }

  async function anotherSentence() {
    setExampleBusy(true);
    setExampleError(false);
    try {
      const next = await requestStudyExample(item.word, avoid);
      if (!next.phrase) {
        setExampleError(true);
        return;
      }
      setGenerated(true);
      setExample({ phrase: next.phrase, translation: next.translation });
      setSawExample(true);
      setAvoid((current) => [...current, next.phrase]);
    } catch {
      setExampleError(true);
    } finally {
      setExampleBusy(false);
    }
  }

  function pickChoice(choice: string) {
    if (choice.trim().toLowerCase() === translation.trim().toLowerCase()) {
      setRevealed(true);
      return;
    }
    setMissed((current) => (current.includes(choice) ? current : [...current, choice]));
  }

  return (
    <Card className="gap-5 p-5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          <span>{deckName}</span>
          {item.cefr ? <span>{` · ${item.cefr}`}</span> : null}
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
        <p className="text-4xl font-semibold tracking-tight" lang="en">
          {item.word}
        </p>
        <ItemReplayButton userId={userId} prompt={item.word} onPlay={() => setHeard(true)} />
      </div>

      {revealed ? (
        <p className="text-lg text-muted-foreground">{translation}</p>
      ) : (
        <div className="flex flex-col gap-3">
          {hint ? (
            <p className="text-lg tracking-wide text-muted-foreground" aria-live="polite">
              {hint}
              {hint.length < translation.trim().length ? "…" : ""}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={() => setRevealed(true)}>
              {t("flashcards.lesson.reveal")}
            </Button>
            {translation ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => setHintShown((shown) => hintEnd(translation, shown))}
              >
                {t("flashcards.lesson.hint")}
              </Button>
            ) : null}
            {item.mnemonic ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => setReminderOpen((open) => !open)}
              >
                {t("flashcards.lesson.mnemonic")}
              </Button>
            ) : null}
            {choices ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => setQuizOpen((open) => !open)}
              >
                {t("flashcards.lesson.quiz")}
              </Button>
            ) : null}
          </div>
          {reminderOpen && item.mnemonic ? (
            <p className="text-sm text-muted-foreground">{item.mnemonic}</p>
          ) : null}
          {quizOpen && choices ? (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {choices.map((choice) => {
                const wrong = missed.includes(choice);
                return (
                  <Button
                    key={choice}
                    type="button"
                    variant="outline"
                    disabled={wrong}
                    onClick={() => pickChoice(choice)}
                  >
                    {choice}
                  </Button>
                );
              })}
            </div>
          ) : null}
        </div>
      )}

      {revealed ? (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            {example ? (
              <div className="flex flex-col gap-1">
                <div className="flex items-start gap-2">
                  <p className="text-base leading-relaxed" lang="en">
                    {example.phrase}
                  </p>
                  <ItemReplayButton userId={userId} prompt={example.phrase} />
                </div>
                {example.translation ? (
                  <div className="flex items-start gap-2">
                    <p className="text-sm text-muted-foreground">{example.translation}</p>
                    <ItemReplayButton
                      userId={userId}
                      prompt={example.translation}
                      language="es"
                    />
                  </div>
                ) : null}
              </div>
            ) : null}
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="w-fit"
              disabled={exampleBusy || !lookupReady}
              onClick={() => void anotherSentence()}
            >
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

          <div className="flex flex-col gap-2">
            <p className="text-xs font-medium text-muted-foreground">
              {t("flashcards.lesson.gradePrompt")}
            </p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[1, 2, 3, 4].map((value) => (
                <Button
                  key={value}
                  type="button"
                  variant={value === 3 ? "default" : "outline"}
                  disabled={saving || !lookupReady}
                  onClick={() => void grade(value)}
                >
                  {t(GRADE_KEY[value])}
                </Button>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      {error ? (
        <p className="text-[11px] text-destructive">{t("flashcards.lesson.saveError")}</p>
      ) : null}
    </Card>
  );
}
