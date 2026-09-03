import { useEffect, useState } from "react";
import { getListeningDiagnostic, getListeningStats } from "../../api/listening";
import type {
  ListeningDiagnostic,
  ListeningStats,
} from "../../types/api";
import { SUBSKILL_LABELS } from "../../utils/learningLabels";
import { useI18n } from "../../hooks/useI18n";
import { LevelBadge } from "../../components/LevelBadge";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { SkillBar } from "../../components/SkillBar";
import { ProgressRing } from "../../components/ProgressRing";
import { cn } from "../../lib/utils";
import { TabLoading } from "../progress/tabBits";

interface ListeningRecorridoPanelProps {
  userId: string;
}

// Etiqueta i18n de una dimensión de resiliencia auditiva ("clear_speech" →
// "listening.resilience.clear_speech").
function resilienceLabel(dimension: string): string {
  return `listening.resilience.${dimension}`;
}

function trendLabel(direction: string): string {
  switch (direction) {
    case "up":
      return "diag.improving";
    case "down":
      return "diag.gettingWorse";
    case "flat":
      return "diag.stable";
    default:
      return "diag.stable";
  }
}

function topicLabel(topic: string): string {
  return topic.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function retentionBucketLabel(bucket: string): string {
  switch (bucket) {
    case "0-2":
      return "0–2 days";
    case "2-7":
      return "2–7 days";
    case "7-30":
      return "7–30 days";
    case "30+":
      return "over 30 days";
    default:
      return bucket;
  }
}

function subskillLabel(skill: string): string {
  return SUBSKILL_LABELS[skill] ?? skill.replace(/_/g, " ");
}

/**
 * Recorrido Listening (MI PROGRESO · Recorridos): vista read-only con los datos
 * reales de `getListeningStats` + `getListeningDiagnostic` (nivel, precisión,
 * sub-destrezas, resiliencia, retención...). Imita el bloque de análisis de
 * ListeningPractice pero sin estados de práctica ni micrófono.
 */
export function ListeningRecorridoPanel({
  userId,
}: ListeningRecorridoPanelProps) {
  const { t } = useI18n();
  const [stats, setStats] = useState<ListeningStats | null>(null);
  const [diagnostic, setDiagnostic] = useState<ListeningDiagnostic | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [s, d] = await Promise.all([
          getListeningStats(userId),
          getListeningDiagnostic(userId),
        ]);
        if (!cancelled) {
          setStats(s);
          setDiagnostic(d);
        }
      } catch {
        if (!cancelled) {
          setStats(null);
          setDiagnostic(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  if (loading) return <TabLoading />;

  if (!stats && !diagnostic) {
    return (
      <Card className="p-6 text-center">
        <p className="text-sm text-muted-foreground">{t("empty.noProgress")}</p>
      </Card>
    );
  }

  const trend = diagnostic?.trend;
  const currentLevelStat = stats?.levels.find((lv) => lv.level === stats?.level);

  return (
    <div className="flex flex-col gap-4">
      {stats && (
        <Card className="gap-4 p-5">
          <div className="flex flex-wrap items-center justify-around gap-6">
            <div className="flex flex-col items-center gap-1.5">
              <ProgressRing
                value={stats.accuracy ?? 0}
                size={72}
                strokeWidth={7}
                className={cn(
                  stats.accuracy === null
                    ? "text-muted-foreground"
                    : stats.accuracy >= 80
                      ? "text-success"
                      : stats.accuracy >= 60
                        ? "text-warning"
                        : "text-destructive",
                )}
                ariaLabel={`${t("listening.accuracy")}: ${
                  stats.accuracy !== null ? `${stats.accuracy}%` : "—"
                }`}
              >
                <span className="text-lg font-bold tabular-nums text-foreground">
                  {stats.accuracy !== null ? `${stats.accuracy}%` : "—"}
                </span>
              </ProgressRing>
              <span className="text-xs font-medium text-foreground">
                {t("listening.accuracy")}
              </span>
              <span className="text-[11px] tabular-nums text-muted-foreground">
                {stats.correct} {t("assessment.of")} {stats.attempts}
              </span>
            </div>

            <div className="flex flex-col items-center gap-1.5">
              <LevelBadge level={stats.level} showLabel={false} />
              <span className="text-xs font-medium text-foreground">
                {t("listening.currentLevel")}
              </span>
              <span className="text-[11px] tabular-nums text-muted-foreground">
                {currentLevelStat
                  ? `${currentLevelStat.mastered}/${currentLevelStat.total}`
                  : "—"}
              </span>
              {currentLevelStat?.completed && (
                <span className="text-[11px] font-semibold text-success">
                  {t("listening.routeCompleted").replace(
                    "{level}",
                    stats.level,
                  )}
                </span>
              )}
              {currentLevelStat &&
                !currentLevelStat.completed &&
                currentLevelStat.mastered === currentLevelStat.total && (
                  <span className="text-[11px] font-semibold text-warning">
                    {t("listening.routePendingCert")}
                  </span>
                )}
            </div>
          </div>
          {stats.completed && (
            <p className="text-sm font-semibold text-success">
              {t("listening.completed")}
            </p>
          )}
          <p className="border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground">
            {t("listening.routeNote").replace("{level}", stats.level)}
          </p>
        </Card>
      )}

      {diagnostic && (
        <Card className="gap-4 p-5">
          <p className="text-sm font-semibold text-foreground">
            {t("listening.diagnostic")}
          </p>
          <p className="text-sm text-foreground">{diagnostic.recommendation}</p>

          {diagnostic.resilience.dimensions.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t("listening.resilience")}
              </p>
              <ul className="flex flex-wrap gap-2">
                {diagnostic.resilience.dimensions.map((r) => (
                  <li key={r.dimension}>
                    <Badge
                      variant={
                        r.dimension === diagnostic.resilience.main_weakness
                          ? "default"
                          : "outline"
                      }
                      className="gap-1.5"
                    >
                      {t(resilienceLabel(r.dimension))} ·{" "}
                      {r.accuracy !== null ? `${r.accuracy}%` : "—"}
                    </Badge>
                  </li>
                ))}
              </ul>
              {diagnostic.resilience.recommendation && (
                <p className="text-sm text-muted-foreground">
                  {diagnostic.resilience.recommendation}
                </p>
              )}
            </div>
          )}

          {diagnostic.subskills.length > 0 && (
            <ul className="flex flex-col gap-2.5">
              {diagnostic.subskills.map((s) => (
                <li
                  key={s.skill}
                  className={cn(s.realization_gap && "opacity-80")}
                >
                  <SkillBar
                    label={subskillLabel(s.skill)}
                    value={(s.accuracy ?? 0) / 100}
                    hint={`${s.attempts} · ${
                      s.accuracy !== null ? `${s.accuracy}%` : "—"
                    }${s.review_due ? ` · ${t("diag.review")}` : ""}`}
                  />
                </li>
              ))}
            </ul>
          )}

          {trend && trend.direction !== "n/a" && (
            <p className="text-sm text-muted-foreground">
              {t("diag.trend")}:{" "}
              <strong
                className={cn(
                  trend.direction === "up" && "text-success",
                  trend.direction === "down" && "text-destructive",
                  trend.direction === "flat" && "text-muted-foreground",
                )}
              >
                {t(trendLabel(trend.direction))}
              </strong>
              {trend.delta !== null
                ? ` (${trend.delta > 0 ? "+" : ""}${trend.delta})`
                : ""}
            </p>
          )}

          {diagnostic.by_topic.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t("listening.accuracyByTopic")}
              </p>
              <ul className="flex flex-wrap gap-2">
                {diagnostic.by_topic.map((tp) => (
                  <li key={tp.topic}>
                    <Badge variant="outline" className="gap-1.5">
                      {topicLabel(tp.topic)} ·{" "}
                      {tp.accuracy !== null ? `${tp.accuracy}%` : "—"}
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {diagnostic.by_difficulty.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t("listening.accuracyByDifficulty")}
              </p>
              <ul className="flex flex-wrap gap-2">
                {diagnostic.by_difficulty.map((d) => (
                  <li key={d.difficulty}>
                    <Badge variant="outline" className="gap-1.5">
                      {t("pron.level")} {d.difficulty} ·{" "}
                      {d.accuracy !== null ? `${d.accuracy}%` : "—"}
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {diagnostic.recurrence.questions_seen > 0 && (
            <p className="text-sm text-muted-foreground">
              {t("listening.retries")}: {diagnostic.recurrence.retried}{" "}
              {t("assessment.of")} {diagnostic.recurrence.questions_seen} ·{" "}
              {t("listening.recovered")} {diagnostic.recurrence.recovered}
            </p>
          )}

          <div className="flex flex-col gap-2">
            <p className="text-sm text-muted-foreground">
              {t("listening.retention")}:{" "}
              {diagnostic.retention.immediate_accuracy !== null
                ? `${diagnostic.retention.immediate_accuracy}%`
                : "—"}{" "}
              {t("listening.immediate")} →{" "}
              {diagnostic.retention.delayed_accuracy !== null
                ? `${diagnostic.retention.delayed_accuracy}%`
                : "—"}{" "}
              {t("listening.delayed")}
              {diagnostic.retention.retention_rate !== null && (
                <span
                  className={cn(
                    "ml-1 font-medium",
                    diagnostic.retention.retention_rate >= 0.9
                      ? "text-success"
                      : diagnostic.retention.retention_rate >= 0.7
                        ? "text-warning"
                        : "text-destructive",
                  )}
                >
                  · {t("listening.retention")}{" "}
                  {Math.round(diagnostic.retention.retention_rate * 100)}%
                </span>
              )}
            </p>
            {diagnostic.retention.by_bucket.length > 0 && (
              <ul className="flex flex-wrap gap-2">
                {diagnostic.retention.by_bucket.map((b) => (
                  <li key={b.bucket}>
                    <Badge variant="outline" className="gap-1.5">
                      {retentionBucketLabel(b.bucket)} ·{" "}
                      {b.accuracy !== null ? `${b.accuracy}%` : "—"}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
