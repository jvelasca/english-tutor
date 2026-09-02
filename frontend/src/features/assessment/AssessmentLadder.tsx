import { useCallback, useEffect, useState } from "react";
import {
  getAssessmentV2Ladder,
  startAssessmentV2,
  submitAssessmentV2,
} from "../../api/academy";
import type {
  AssessmentV2Ladder,
  AssessmentV2State,
} from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { cn } from "../../lib/utils";

interface AssessmentLadderProps {
  userId: string | null;
  levelId?: string;
}

function pct(score: number | null | undefined): string {
  return score == null ? "—" : `${Math.round(score * 100)}%`;
}

const KIND_ORDER = [
  "formative",
  "unit",
  "progress",
  "level",
  "retention",
] as const;

/**
 * Escalera Assessment 2.0: formative → unit → progress → level → retention.
 */
export function AssessmentLadder({ userId, levelId }: AssessmentLadderProps) {
  const { t } = useI18n();
  const [ladder, setLadder] = useState<AssessmentV2Ladder | null>(null);
  const [session, setSession] = useState<AssessmentV2State | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!userId) return;
    try {
      const data = await getAssessmentV2Ladder(userId, levelId);
      setLadder(data);
    } catch {
      /* backend no disponible */
    }
  }, [userId, levelId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!userId) return null;

  async function begin(kind: string) {
    if (!ladder) return;
    setBusy(true);
    setError(null);
    try {
      const next = await startAssessmentV2(userId!, kind, ladder.level_id);
      setSession(next);
      setAnswers({});
    } catch {
      setError(t("assessmentV2.errorStart"));
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const next = await submitAssessmentV2(
        userId!,
        session.session_id,
        answers,
      );
      setSession(next);
      await refresh();
    } catch {
      setError(t("assessmentV2.errorSubmit"));
    } finally {
      setBusy(false);
    }
  }

  function kindLabel(kind: string): string {
    return t(`assessmentV2.kind.${kind}` as "assessmentV2.kind.formative");
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-base font-semibold">{t("assessmentV2.title")}</h3>
        <p className="text-sm text-muted-foreground">
          {t("assessmentV2.subtitle")}
        </p>
      </div>

      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}

      {ladder && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {KIND_ORDER.map((kind) => {
              const step = ladder.steps.find((s) => s.kind === kind);
              if (!step) return null;
              const active = session?.kind === kind && session.status === "open";
              return (
                <Button
                  key={kind}
                  type="button"
                  size="sm"
                  variant={
                    step.completed ? "secondary" : active ? "default" : "outline"
                  }
                  disabled={busy || (!step.available && !step.completed)}
                  onClick={() => void begin(kind)}
                  className={cn(
                    step.completed && "border-emerald-500/40",
                    !step.available && !step.completed && "opacity-50",
                  )}
                >
                  {kindLabel(kind)}
                  {step.completed ? " ✓" : ""}
                </Button>
              );
            })}
          </div>

          <Card className="space-y-2 p-3 text-sm">
            <p>
              <span className="text-muted-foreground">
                {t("assessmentV2.next")}:{" "}
              </span>
              {ladder.readiness.next_kind
                ? kindLabel(ladder.readiness.next_kind)
                : t("assessmentV2.nextNone")}
            </p>
            <p>
              <span className="text-muted-foreground">
                {t("assessmentV2.mastery")}:{" "}
              </span>
              {ladder.mastery_gate.met
                ? t("assessmentV2.masteryOk")
                : `${t("assessmentV2.masteryMissing")}: ${ladder.mastery_gate.missing.join(", ")}`}
            </p>
            {ladder.readiness.retention_due && (
              <p className="text-amber-700 dark:text-amber-400">
                {t("assessmentV2.retentionDue")}
              </p>
            )}
          </Card>
        </div>
      )}

      {session && (
        <Card className="space-y-4 p-4">
          <div>
            <h4 className="font-medium">{session.instrument.title}</h4>
            <p className="text-xs text-muted-foreground">
              {kindLabel(session.kind)} · {t("assessmentV2.threshold")}{" "}
              {pct(session.instrument.threshold)}
            </p>
          </div>

          {session.status === "open" && (
            <div className="space-y-4">
              {session.instrument.items.map((item, idx) => (
                <fieldset key={item.id} className="space-y-2">
                  <legend className="text-sm font-medium">
                    {idx + 1}. {item.prompt}
                  </legend>
                  <div className="flex flex-col gap-1.5">
                    {item.options.map((opt, oi) => (
                      <label
                        key={`${item.id}-${oi}`}
                        className={cn(
                          "flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm",
                          answers[item.id] === oi
                            ? "border-primary bg-primary/5"
                            : "border-border",
                        )}
                      >
                        <input
                          type="radio"
                          name={item.id}
                          checked={answers[item.id] === oi}
                          onChange={() =>
                            setAnswers((prev) => ({ ...prev, [item.id]: oi }))
                          }
                        />
                        {opt}
                      </label>
                    ))}
                  </div>
                </fieldset>
              ))}
              <Button
                type="button"
                disabled={
                  busy ||
                  Object.keys(answers).length < session.instrument.items.length
                }
                onClick={() => void submit()}
              >
                {t("assessmentV2.submit")}
              </Button>
            </div>
          )}

          {session.result && (
            <div className="space-y-2 text-sm">
              <p
                className={cn(
                  "font-medium",
                  session.result.passed
                    ? "text-emerald-700 dark:text-emerald-400"
                    : "text-amber-700 dark:text-amber-400",
                )}
              >
                {session.result.passed
                  ? t("assessmentV2.passed")
                  : t("assessmentV2.failed")}{" "}
                · {pct(session.result.overall)} (
                {session.result.correct}/{session.result.total})
              </p>
              {session.result.failed_skills.length > 0 && (
                <p className="text-muted-foreground">
                  {t("assessmentV2.failedSkills")}:{" "}
                  {session.result.failed_skills.join(", ")}
                </p>
              )}
            </div>
          )}

          {session.retention && (
            <div className="space-y-1 rounded-md border border-border p-3 text-sm">
              <p className="font-medium">{t("assessmentV2.retentionTitle")}</p>
              <p>
                {pct(session.retention.initial_overall)} →{" "}
                {pct(session.retention.delayed_overall)}
                {session.retention.retention_rate != null &&
                  ` · ${pct(session.retention.retention_rate)}`}
                {session.retention.stable
                  ? ` · ${t("assessmentV2.retentionStable")}`
                  : ""}
              </p>
            </div>
          )}

          {session.status === "done" && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setSession(null)}
            >
              {t("assessmentV2.back")}
            </Button>
          )}
        </Card>
      )}
    </div>
  );
}
