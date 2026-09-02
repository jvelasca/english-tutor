import { useCallback, useEffect, useState } from "react";
import { getFsrsDue, reviewFsrsCard } from "../../api/academy";
import type { FsrsCard, FsrsDue } from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { cn } from "../../lib/utils";

interface FsrsReviewProps {
  userId: string | null;
}

const GRADES = [
  { grade: 1, key: "fsrs.grade.again" },
  { grade: 2, key: "fsrs.grade.hard" },
  { grade: 3, key: "fsrs.grade.good" },
  { grade: 4, key: "fsrs.grade.easy" },
] as const;

function pct(n: number | null | undefined): string {
  return n == null ? "—" : `${Math.round(n * 100)}%`;
}

/**
 * Cola FSRS-lite (V2.11): What / Why / When / How strong / Last / Next.
 */
export function FsrsReviewPanel({ userId }: FsrsReviewProps) {
  const { t } = useI18n();
  const [queue, setQueue] = useState<FsrsDue | null>(null);
  const [current, setCurrent] = useState<FsrsCard | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastExplain, setLastExplain] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!userId) return;
    try {
      const data = await getFsrsDue(userId, 15);
      setQueue(data);
      setCurrent(data.cards[0] ?? null);
    } catch {
      /* backend no disponible */
    }
  }, [userId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!userId) return null;

  async function gradeCard(grade: number) {
    if (!current) return;
    setBusy(true);
    setError(null);
    try {
      const out = await reviewFsrsCard(
        userId!,
        current.target_type,
        current.target_id,
        grade,
      );
      const nextDays = out.explain.when.next_in_days;
      setLastExplain(
        `${out.explain.what.label}: ${pct(out.explain.how_strong.retrievability)} · +${nextDays.toFixed(1)}d`,
      );
      await refresh();
    } catch {
      setError(t("fsrs.errorReview"));
    } finally {
      setBusy(false);
    }
  }

  const explain = current?.explain;

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-base font-semibold">{t("fsrs.title")}</h3>
        <p className="text-sm text-muted-foreground">{t("fsrs.subtitle")}</p>
      </div>

      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}

      {queue && (
        <p className="text-sm text-muted-foreground">
          {t("fsrs.dueCount")}: {queue.due_count}
        </p>
      )}

      {lastExplain && (
        <p className="text-xs text-muted-foreground">{lastExplain}</p>
      )}

      {!current && (
        <p className="text-sm text-muted-foreground">{t("fsrs.empty")}</p>
      )}

      {current && explain && (
        <Card className="space-y-3 p-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {t("fsrs.what")}
            </p>
            <p className="font-medium">
              {explain.what.label}{" "}
              <span className="text-xs text-muted-foreground">
                ({explain.what.target_type})
              </span>
            </p>
          </div>

          <div className="grid gap-2 text-sm sm:grid-cols-2">
            <p>
              <span className="text-muted-foreground">{t("fsrs.why")}: </span>
              {t(`fsrs.whyReason.${explain.why}`)}
            </p>
            <p>
              <span className="text-muted-foreground">{t("fsrs.when")}: </span>
              {explain.when.due
                ? t("fsrs.dueNow")
                : `+${explain.when.next_in_days.toFixed(1)}d`}
            </p>
            <p>
              <span className="text-muted-foreground">
                {t("fsrs.howStrong")}:{" "}
              </span>
              S {explain.how_strong.stability.toFixed(1)} · R{" "}
              {pct(explain.how_strong.retrievability)}
            </p>
            <p>
              <span className="text-muted-foreground">
                {t("fsrs.lastEvidence")}:{" "}
              </span>
              {explain.last_evidence.grade_label || t("fsrs.never")}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {GRADES.map(({ grade, key }) => (
              <Button
                key={grade}
                type="button"
                size="sm"
                variant={grade <= 2 ? "outline" : "default"}
                disabled={busy}
                className={cn(grade === 1 && "text-destructive")}
                onClick={() => void gradeCard(grade)}
              >
                {t(key)}
              </Button>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
