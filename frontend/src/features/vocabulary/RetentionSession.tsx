/**
 * Sesión de retención léxica (estilo Anki): voltear tarjeta + grade FSRS.
 *
 * Camino etiquetado (D5/E3): solo reprograma `fsrs_cards` lexicon y escribe
 * eventos informativos. No abre el drill ni escribe mastery.
 */
import { useCallback, useEffect, useState } from "react";
import { Layers, RefreshCw } from "lucide-react";
import { getRetentionDue, reviewRetentionCard } from "../../api/vocabulary";
import type { RetentionCard } from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { ItemReplayButton } from "../../components/ItemReplayButton";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { cn } from "../../lib/utils";

const GRADES = [
  { grade: 1, key: "fsrs.grade.again", tone: "text-destructive" },
  { grade: 2, key: "fsrs.grade.hard", tone: "text-warning" },
  { grade: 3, key: "fsrs.grade.good", tone: "text-primary" },
  { grade: 4, key: "fsrs.grade.easy", tone: "text-success" },
] as const;

interface RetentionSessionProps {
  userId: string;
  onFinished?: () => void;
}

export function RetentionSession({ userId, onFinished }: RetentionSessionProps) {
  const { t } = useI18n();
  const [queue, setQueue] = useState<RetentionCard[]>([]);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [done, setDone] = useState(0);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const data = await getRetentionDue(userId, { limit: 15 });
      setQueue(Array.isArray(data?.items) ? data.items : []);
      setIndex(0);
      setFlipped(false);
      setDone(0);
    } catch {
      setError(true);
      setQueue([]);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void load();
  }, [load]);

  const current = queue[index] ?? null;
  const remaining = Math.max(0, queue.length - index);

  async function grade(g: number) {
    if (!current || busy) return;
    setBusy(true);
    try {
      await reviewRetentionCard(userId, current.word, g);
      setDone((n) => n + 1);
      setFlipped(false);
      const next = index + 1;
      if (next >= queue.length) {
        setActive(false);
        onFinished?.();
        await load();
      } else {
        setIndex(next);
      }
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  if (!active) {
    return (
      <Card className="gap-3 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <Layers className="size-4 text-primary" aria-hidden="true" />
              {t("dictionary.retention.title")}
            </h2>
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              {t("dictionary.retention.hint")}
            </p>
          </div>
          <Badge variant="secondary" className="shrink-0">
            {loading ? "…" : remaining}
          </Badge>
        </div>
        {error ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            {t("dictionary.loadError")}
            <button
              type="button"
              onClick={() => void load()}
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium hover:border-primary/50"
            >
              <RefreshCw className="size-3.5" aria-hidden="true" />
              {t("common.retry")}
            </button>
          </p>
        ) : remaining === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t("dictionary.retention.empty")}
          </p>
        ) : (
          <Button
            type="button"
            size="sm"
            className="w-fit"
            onClick={() => setActive(true)}
            disabled={loading}
          >
            {t("dictionary.retention.start").replace(
              "{n}",
              String(remaining),
            )}
          </Button>
        )}
      </Card>
    );
  }

  if (!current) {
    return (
      <Card className="gap-3 p-5">
        <p className="text-sm text-muted-foreground">
          {t("dictionary.retention.finished").replace("{n}", String(done))}
        </p>
        <Button type="button" size="sm" variant="outline" onClick={() => setActive(false)}>
          {t("dictionary.retention.back")}
        </Button>
      </Card>
    );
  }

  return (
    <Card className="gap-4 p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">{t("dictionary.retention.title")}</h2>
        <Badge variant="secondary">
          {index + 1}/{queue.length}
        </Badge>
      </div>

      <button
        type="button"
        onClick={() => setFlipped((f) => !f)}
        className={cn(
          "flex min-h-36 w-full flex-col items-center justify-center gap-3 rounded-xl border border-border bg-secondary/40 px-4 py-6 text-center transition-colors hover:border-primary/40",
        )}
        aria-label={t("dictionary.retention.flip")}
      >
        <span className="text-2xl font-bold tracking-tight" lang="en">
          {current.word}
        </span>
        {flipped ? (
          <div className="flex flex-col gap-1">
            {current.translation ? (
              <span className="text-lg font-semibold" lang="es">
                {current.translation}
              </span>
            ) : null}
            {current.definition ? (
              <span className="text-sm text-muted-foreground" lang="en">
                {current.definition}
              </span>
            ) : null}
            {!current.translation && !current.definition ? (
              <span className="text-sm text-muted-foreground">
                {t("dictionary.retention.noFace")}
              </span>
            ) : null}
          </div>
        ) : (
          <span className="text-xs text-muted-foreground">
            {t("dictionary.retention.tapReveal")}
          </span>
        )}
      </button>

      <div className="flex items-center justify-center gap-2">
        <ItemReplayButton prompt={current.word} userId={userId} />
      </div>

      {flipped ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {GRADES.map((g) => (
            <Button
              key={g.grade}
              type="button"
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => void grade(g.grade)}
              className={cn("font-semibold", g.tone)}
            >
              {t(g.key)}
            </Button>
          ))}
        </div>
      ) : (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="w-fit self-center"
          onClick={() => setFlipped(true)}
        >
          {t("dictionary.retention.reveal")}
        </Button>
      )}

      <button
        type="button"
        className="text-xs text-muted-foreground underline-offset-2 hover:underline"
        onClick={() => {
          setActive(false);
          void load();
        }}
      >
        {t("dictionary.retention.exit")}
      </button>
    </Card>
  );
}
