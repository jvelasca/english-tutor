import { useEffect, useState } from "react";
import { motion, type Variants } from "motion/react";
import { BookOpen, Mic } from "lucide-react";
import { getLexicon } from "../../api/vocabulary";
import type { LexicalItem, LexicalStatus, Lexicon } from "../../types/api";
import {
  cefrBarValue,
  recognizedNotProduced,
  sortLexicalItems,
} from "./dictionary";
import { useI18n } from "../../hooks/useI18n";
import { LevelBadge } from "../../components/LevelBadge";
import { SkillBar } from "../../components/SkillBar";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { Progress } from "../../components/ui/progress";
import { cn } from "../../lib/utils";

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
  },
};

const STATUS_TONE: Record<LexicalStatus, string> = {
  mastered: "border-transparent bg-success/15 text-success",
  known: "border-transparent bg-primary/15 text-primary",
  learning: "border-transparent bg-warning/15 text-warning",
  weak: "border-transparent bg-destructive/10 text-destructive",
};

interface PersonalDictionaryProps {
  userId: string | null;
}

/** Diccionario personal (V2.3): evidencia por ítem léxico con estado y recall. */
export function PersonalDictionary({ userId }: PersonalDictionaryProps) {
  const { t } = useI18n();
  const [lexicon, setLexicon] = useState<Lexicon | null>(null);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    void (async () => {
      try {
        const data = await getLexicon(userId);
        if (!cancelled) setLexicon(data);
      } catch {
        /* backend no disponible */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  if (!lexicon) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
        <DictionaryHeader />
        <p className="mt-4 text-sm text-muted-foreground">{t("common.loading")}</p>
      </div>
    );
  }

  const { summary, items } = lexicon;
  const sorted = sortLexicalItems(items);

  const drillCandidates = recognizedNotProduced(items);

  const maxCefr = Math.max(1, ...summary.by_cefr.map((b) => b.count));

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-5"
      >
        <DictionaryHeader total={summary.total} />

        <motion.section variants={item} aria-label={t("dictionary.title")}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile
              label={t("dictionary.known")}
              value={summary.known}
              tone="text-primary"
            />
            <StatTile
              label={t("dictionary.learning")}
              value={summary.learning}
              tone="text-warning"
            />
            <StatTile
              label={t("dictionary.weak")}
              value={summary.weak}
              tone="text-destructive"
            />
            <StatTile
              label={t("dictionary.mastered")}
              value={summary.mastered}
              tone="text-success"
            />
          </div>
        </motion.section>

        {summary.by_cefr.length > 0 && (
          <motion.section variants={item} aria-label={t("dictionary.byCefr")}>
            <Card className="gap-3 p-5">
              <h2 className="text-sm font-semibold">{t("dictionary.byCefr")}</h2>
              <ul className="flex flex-col gap-2.5">
                {summary.by_cefr.map((bucket) => (
                  <li key={bucket.cefr} className="flex items-center gap-3">
                    <LevelBadge level={bucket.cefr} className="w-12 justify-center" />
                    <SkillBar
                      value={cefrBarValue(bucket.count, maxCefr)}
                      hint={String(bucket.count)}
                      className="flex-1"
                    />
                  </li>
                ))}
              </ul>
            </Card>
          </motion.section>
        )}

        {drillCandidates.length > 0 && (
          <motion.section
            variants={item}
            aria-label={t("dictionary.recognizedNotProduced")}
          >
            <Card className="gap-3 p-5">
              <div className="flex items-center gap-2">
                <Mic className="size-4 text-primary" aria-hidden="true" />
                <h2 className="text-sm font-semibold">
                  {t("dictionary.recognizedNotProduced")}
                </h2>
              </div>
              <p className="text-xs text-muted-foreground">
                {t("dictionary.recognizedNotProducedHint")}
              </p>
              <ul className="flex flex-wrap gap-1.5">
                {drillCandidates.map((word) => (
                  <li
                    key={word}
                    className="rounded-md border border-border bg-secondary px-2 py-1 text-xs font-medium"
                  >
                    {word}
                  </li>
                ))}
              </ul>
            </Card>
          </motion.section>
        )}

        <motion.section variants={item} aria-label={t("dictionary.items")}>
          <Card className="gap-0 overflow-hidden p-0">
            {sorted.length === 0 ? (
              <p className="p-5 text-sm text-muted-foreground">
                {t("dictionary.empty")}
              </p>
            ) : (
              <ul className="divide-y divide-border/60">
                {sorted.map((lex) => (
                  <LexicalRow key={lex.word} lexical={lex} />
                ))}
              </ul>
            )}
          </Card>
        </motion.section>
      </motion.div>
    </div>
  );
}

function DictionaryHeader({ total }: { total?: number }) {
  const { t } = useI18n();
  return (
    <motion.header variants={item} className="flex items-center justify-between gap-3">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight sm:text-3xl">
          <BookOpen className="size-6 text-primary" aria-hidden="true" />
          {t("dictionary.title")}
        </h1>
        <p className="mt-1 text-muted-foreground">{t("dictionary.subtitle")}</p>
      </div>
      {total != null && (
        <Badge variant="secondary" className="shrink-0">
          {total} {t("dictionary.total")}
        </Badge>
      )}
    </motion.header>
  );
}

function StatTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 text-left shadow-sm">
      <span className={cn("text-2xl font-bold tabular-nums", tone)}>{value}</span>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

function LexicalRow({ lexical }: { lexical: LexicalItem }) {
  const { t } = useI18n();
  const kindLabel =
    lexical.kind === "structure"
      ? t("dictionary.kind.structure")
      : t("dictionary.kind.word");
  const statusLabel = t(`dictionary.status.${lexical.status}`);

  return (
    <li className="flex items-center gap-3 p-3 sm:p-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-semibold text-foreground">
            {lexical.word}
          </span>
          {lexical.cefr && <LevelBadge level={lexical.cefr} className="shrink-0" />}
          <span className="shrink-0 text-xs text-muted-foreground">{kindLabel}</span>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <Progress
            value={Math.round(lexical.recall * 100)}
            className="h-1.5 flex-1"
            aria-label={`${t("dictionary.recall")} ${Math.round(lexical.recall * 100)}%`}
          />
          <span className="w-9 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
            {Math.round(lexical.recall * 100)}%
          </span>
        </div>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        <Badge className={cn(STATUS_TONE[lexical.status])}>{statusLabel}</Badge>
        {lexical.status !== "mastered" && (
          <span className="text-[11px] text-muted-foreground">
            {lexical.status === "weak"
              ? t("mastery.reviewNow")
              : t("dictionary.nextReviewIn").replace(
                  "{days}",
                  String(lexical.next_review_days),
                )}
          </span>
        )}
      </div>
    </li>
  );
}
