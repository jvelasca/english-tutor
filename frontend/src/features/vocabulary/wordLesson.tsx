/**
 * Lección de una palabra en Estudiar.
 *
 * Palabra nueva: significado, pronunciación, contexto y, si el diccionario los
 * trae, acepciones y una forma relacionada. Cada paso se puede saltar: queda
 * pendiente, no es un fallo. Palabra ya estudiada: evocación corta y la nota
 * FSRS, con un enlace para abrir los pasos que sigan pendientes.
 */
import { useEffect, useMemo, useState } from "react";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { cn } from "../../lib/utils";
import { ItemReplayButton } from "../../components/ItemReplayButton";
import { LoadingNotice } from "../../components/LoadingNotice";
import { lookupDictionaryWord } from "../../api/vocabulary";
import { useI18n } from "../../hooks/useI18n";
import type {
  DictionaryEntry,
  LessonFacet,
  LessonFacetStatus,
  StudyLessonItem,
} from "../../types/api";

const CORE_STEPS: LessonFacet[] = ["meaning", "pronunciation", "context"];
const ALL_FACETS: LessonFacet[] = [
  "meaning",
  "pronunciation",
  "context",
  "senses",
  "related",
];

const GRADE_KEY: Record<number, string> = {
  1: "fsrs.grade.again",
  2: "fsrs.grade.hard",
  3: "fsrs.grade.good",
  4: "fsrs.grade.easy",
};

const STEP_LABEL: Record<LessonFacet, string> = {
  meaning: "flashcards.lesson.meaning",
  pronunciation: "flashcards.lesson.pronunciation",
  context: "flashcards.lesson.context",
  senses: "flashcards.lesson.senses",
  related: "flashcards.lesson.related",
};

export interface LessonClose {
  item_id: string;
  grade: number;
  facets: Record<string, string>;
  translation: string;
}

/** Pasos extra solo cuando el diccionario tiene con qué enseñarlos. */
export function extraSteps(entry: DictionaryEntry | null, word: string): LessonFacet[] {
  const extras: LessonFacet[] = [];
  const meanings = (entry?.meanings ?? []).filter((meaning) => meaning.term && !meaning.proper_noun);
  if (meanings.length > 1) extras.push("senses");
  const related = (entry?.senses ?? []).find(
    (sense) => sense.lemma && sense.lemma.toLowerCase() !== word.toLowerCase(),
  );
  if (related) extras.push("related");
  return extras;
}

function offeredSteps(entry: DictionaryEntry | null, word: string, ready: boolean): LessonFacet[] {
  return ready ? [...CORE_STEPS, ...extraSteps(entry, word)] : [...CORE_STEPS];
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
  const [stepIndex, setStepIndex] = useState(0);
  const [outcomes, setOutcomes] = useState<Partial<Record<LessonFacet, LessonFacetStatus>>>({});
  const [entry, setEntry] = useState<DictionaryEntry | null>(null);
  const [lookupReady, setLookupReady] = useState(false);
  const [deepen, setDeepen] = useState(false);
  const [phase, setPhase] = useState<"steps" | "grade" | "done">("steps");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);
  const [reviewed, setReviewed] = useState(0);
  const [revealed, setRevealed] = useState(false);

  const item = items[index];
  const steps = useMemo(() => {
    if (!item) return CORE_STEPS;
    const offered = offeredSteps(entry, item.word, lookupReady);
    if (item.is_new || deepen) return offered;
    return offered;
  }, [item, entry, lookupReady, deepen]);

  const deepSteps = useMemo(() => {
    if (!item) return CORE_STEPS;
    const offered = offeredSteps(entry, item.word, lookupReady);
    const pending = offered.filter(
      (step) => item.facets[step] === "pending" || !item.facets[step],
    );
    return pending.length > 0 ? pending : offered;
  }, [item, entry, lookupReady]);

  const activeSteps = item && !item.is_new && deepen ? deepSteps : steps;

  useEffect(() => {
    if (!item) return;
    let alive = true;
    setEntry(null);
    setLookupReady(false);
    setStepIndex(0);
    setOutcomes({});
    setDeepen(false);
    setPhase(item.is_new ? "steps" : "grade");
    setRevealed(false);
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

  if (!item || phase === "done" && index >= items.length) {
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
  const example =
    entry?.example?.phrase ||
    entry?.situation ||
    entry?.senses?.find((sense) => sense.example)?.example ||
    "";
  const meanings = (entry?.meanings ?? []).filter((meaning) => meaning.term && !meaning.proper_noun);
  const related = (entry?.senses ?? []).find(
    (sense) => sense.lemma && sense.lemma.toLowerCase() !== item.word.toLowerCase(),
  );

  function mark(status: LessonFacetStatus) {
    const step = activeSteps[stepIndex];
    if (!step) return;
    const next = { ...outcomes, [step]: status };
    setOutcomes(next);
    const moreComing = !lookupReady && stepIndex >= activeSteps.length - 1;
    if (moreComing) return;
    if (stepIndex >= activeSteps.length - 1) {
      setPhase("grade");
      return;
    }
    setStepIndex((current) => current + 1);
  }

  function facetsForGrade(): Record<string, string> {
    if (!item.is_new && !deepen) {
      return { ...item.facets, meaning: "done" };
    }
    const offered = new Set(activeSteps);
    const out: Record<string, string> = {};
    for (const name of ALL_FACETS) {
      if (outcomes[name]) out[name] = outcomes[name] as string;
      else if (!offered.has(name)) out[name] = "na";
      else out[name] = "pending";
    }
    return out;
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
      if (next >= items.length) {
        setIndex(next);
        setPhase("done");
      } else {
        setIndex(next);
      }
    } catch {
      setError(true);
    } finally {
      setSaving(false);
    }
  }

  const showSteps = item.is_new || deepen;
  const step = activeSteps[stepIndex] ?? "meaning";
  const waiting = showSteps && !lookupReady && stepIndex >= activeSteps.length - 1 && phase === "steps";
  const pendingNames = ALL_FACETS.filter((name) => {
    if (outcomes[name] === "pending") return true;
    return !showSteps && item.facets[name] === "pending";
  }).map((name) => t(STEP_LABEL[name]));

  function GradeRow() {
    return (
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
              disabled={saving}
              onClick={() => void grade(value)}
            >
              {t(GRADE_KEY[value])}
            </Button>
          ))}
        </div>
      </div>
    );
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

      {showSteps ? (
        <ol className="flex items-center gap-2" aria-label={t(STEP_LABEL[step])}>
          {activeSteps.map((name, stepNumber) => {
            const current = phase === "steps" && stepNumber === stepIndex;
            const skipped = outcomes[name] === "pending";
            const passed = phase === "grade" || stepNumber < stepIndex;
            return (
              <li key={name} className="flex items-center gap-2">
                <span
                  className={cn(
                    "flex size-8 items-center justify-center rounded-full text-xs font-semibold",
                    current && "bg-primary text-primary-foreground",
                    !current && skipped && "border border-dashed border-primary text-primary",
                    !current && !skipped && passed && "bg-primary/15 text-primary",
                    !current && !skipped && !passed && "border border-border text-muted-foreground",
                  )}
                >
                  {stepNumber + 1}
                </span>
              </li>
            );
          })}
        </ol>
      ) : null}

      {showSteps && phase === "grade" ? (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <p className="text-3xl font-semibold tracking-tight" lang="en">{item.word}</p>
            {translation ? (
              <p className="text-sm text-muted-foreground">{translation}</p>
            ) : null}
          </div>
          {pendingNames.length > 0 ? (
            <p className="text-xs text-muted-foreground">
              {t("flashcards.lesson.pendingLine").replace("{steps}", pendingNames.join(", "))}
            </p>
          ) : null}
          <GradeRow />
        </div>
      ) : showSteps && phase === "steps" ? (
        <div className="flex min-h-40 flex-col gap-4">
          <p className="text-sm font-semibold text-primary">{t(STEP_LABEL[step])}</p>
          {step === "meaning" ? (
            <div className="flex flex-col gap-2">
              <p className="text-4xl font-semibold tracking-tight" lang="en">{item.word}</p>
              {translation ? (
                <p className="text-lg text-muted-foreground">{translation}</p>
              ) : (
                <p className="text-sm text-muted-foreground">{t("flashcards.lesson.noMeaning")}</p>
              )}
            </div>
          ) : null}
          {step === "pronunciation" ? (
            <div className="flex items-center gap-3">
              <p className="text-4xl font-semibold tracking-tight" lang="en">{item.word}</p>
              <ItemReplayButton userId={userId} prompt={item.word} />
            </div>
          ) : null}
          {step === "context" ? (
            <p className="text-lg leading-relaxed">
              {example || t("flashcards.lesson.noContext")}
            </p>
          ) : null}
          {step === "senses" ? (
            <ul className="flex flex-col gap-2 text-base">
              {meanings.map((meaning) => (
                <li key={`${meaning.term}-${meaning.pos}`}>
                  <span className="font-medium">{meaning.term}</span>
                  {meaning.gloss ? ` — ${meaning.gloss}` : ""}
                </li>
              ))}
            </ul>
          ) : null}
          {step === "related" ? (
            <p className="text-lg">
              {t("flashcards.lesson.relatedTo").replace("{lemma}", related?.lemma || item.word)}
            </p>
          ) : null}
          {waiting ? <LoadingNotice className="text-[11px]" /> : null}
          <div className="mt-auto flex flex-wrap gap-2">
            <Button type="button" disabled={waiting} onClick={() => mark("done")}>
              {t("flashcards.lesson.continue")}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={waiting}
              onClick={() => mark("pending")}
            >
              {t("flashcards.lesson.skip")}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex min-h-40 flex-col gap-4">
          <p className="text-sm font-semibold text-primary">{t("flashcards.lesson.recall")}</p>
          <p className="text-xs text-muted-foreground">{t("flashcards.lesson.recallPrompt")}</p>
          <p className="text-2xl font-semibold">{translation || item.definition}</p>
          <div className="flex items-center gap-3">
            <ItemReplayButton userId={userId} prompt={item.word} />
            {revealed ? (
              <p className="text-4xl font-semibold tracking-tight" lang="en">{item.word}</p>
            ) : (
              <Button type="button" variant="outline" onClick={() => setRevealed(true)}>
                {t("flashcards.lesson.reveal")}
              </Button>
            )}
          </div>
          {!deepen ? (
            <button
              type="button"
              className="w-fit text-sm font-medium text-primary underline-offset-2 hover:underline"
              onClick={() => {
                setDeepen(true);
                setPhase("steps");
                setStepIndex(0);
                setOutcomes({});
              }}
            >
              {t("flashcards.lesson.deeper")}
            </button>
          ) : null}
          {pendingNames.length > 0 ? (
            <p className="text-xs text-muted-foreground">
              {t("flashcards.lesson.pendingLine").replace("{steps}", pendingNames.join(", "))}
            </p>
          ) : null}
          {revealed ? <GradeRow /> : null}
        </div>
      )}

      {error ? (
        <p className="text-[11px] text-destructive">{t("flashcards.lesson.saveError")}</p>
      ) : null}
    </Card>
  );
}
