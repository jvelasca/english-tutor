import { useEffect, useState } from "react";
import {
  getSpeakingScenarios,
  startSpeakingMission,
  submitSpeakingMissionAttempt,
  submitSpeakingMissionRetry,
} from "../../api/academy";
import type {
  SpeakingMissionState,
  SpeakingScenario,
} from "../../types/api";
import { criterionLabel } from "../../utils/speaking";
import { useI18n } from "../../hooks/useI18n";
import { LevelBadge } from "../../components/LevelBadge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { cn } from "../../lib/utils";

interface SpeakingMissionProps {
  userId: string | null;
}

function pct(score: number | null | undefined): string {
  return score == null ? "—" : `${Math.round(score * 100)}%`;
}

/**
 * Loop V2.9: Mission → Attempt → Evaluation → Targeted drill → Retry → Improvement.
 * Reutiliza escenarios del catálogo y el scorer determinista vía backend.
 */
export function SpeakingMission({ userId }: SpeakingMissionProps) {
  const { t } = useI18n();
  const [scenarios, setScenarios] = useState<SpeakingScenario[]>([]);
  const [state, setState] = useState<SpeakingMissionState | null>(null);
  const [heard, setHeard] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!userId) return;
      try {
        const data = await getSpeakingScenarios(userId);
        if (!cancelled) setScenarios(data.scenarios);
      } catch {
        /* backend no disponible */
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  if (!userId) return null;

  async function begin(scenarioId: string) {
    setBusy(true);
    setError(null);
    try {
      const next = await startSpeakingMission(userId!, scenarioId);
      setState(next);
      setHeard("");
    } catch {
      setError(t("mission.errorStart"));
    } finally {
      setBusy(false);
    }
  }

  async function sendAttempt() {
    if (!state || !heard.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const next = await submitSpeakingMissionAttempt(
        userId!,
        state.session_id,
        heard.trim(),
      );
      setState(next);
      setHeard("");
    } catch {
      setError(t("mission.errorAttempt"));
    } finally {
      setBusy(false);
    }
  }

  async function sendRetry() {
    if (!state || !heard.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const next = await submitSpeakingMissionRetry(
        userId!,
        state.session_id,
        heard.trim(),
      );
      setState(next);
      setHeard("");
    } catch {
      setError(t("mission.errorRetry"));
    } finally {
      setBusy(false);
    }
  }

  if (!state) {
    return (
      <Card className="gap-4 p-5">
        <header>
          <h3 className="text-sm font-semibold text-foreground">
            {t("mission.title")}
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("mission.subtitle")}
          </p>
        </header>
        {scenarios.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("mission.empty")}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {scenarios.slice(0, 6).map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void begin(s.id)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md border border-border px-3 py-2 text-left text-sm",
                    "hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                  )}
                >
                  <LevelBadge level={s.cefr_target} />
                  <span className="font-medium text-foreground">{s.title}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </Card>
    );
  }

  const canAttempt = state.status === "mission" || state.status === "attempt";
  const canRetry =
    state.status === "drill" ||
    state.status === "evaluation" ||
    state.status === "retry";
  const done = state.status === "improvement";

  return (
    <Card className="gap-4 p-5">
      <header className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <LevelBadge level={state.mission.cefr_target} />
            <h3 className="truncate text-sm font-semibold text-foreground">
              {state.mission.title}
            </h3>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {state.mission.communicative_objective}
          </p>
        </div>
        <Button
          variant="ghost"
          className="shrink-0 px-2 text-xs"
          onClick={() => {
            setState(null);
            setHeard("");
            setError(null);
          }}
        >
          {t("mission.reset")}
        </Button>
      </header>

      <p className="rounded-md bg-secondary/60 px-3 py-2 text-sm text-foreground">
        {state.mission.prompt}
      </p>

      {state.evaluation && (
        <section className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("mission.evaluation")}
          </h4>
          <p className="text-sm text-foreground">
            {t("mission.overall")}:{" "}
            <span className="font-semibold tabular-nums">
              {pct(state.evaluation.overall)}
            </span>
          </p>
          <p className="text-sm text-muted-foreground">
            {state.evaluation.recommendation}
          </p>
          {state.evaluation.weak.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {t("mission.weak")}:{" "}
              {state.evaluation.weak.map(criterionLabel).join(", ")}
            </p>
          )}
        </section>
      )}

      {state.drills.length > 0 && !done && (
        <section className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("mission.drills")}
          </h4>
          <ul className="flex flex-col gap-2">
            {state.drills.map((d) => (
              <li
                key={d.criterion}
                className="rounded-md border border-border px-3 py-2"
              >
                <p className="text-sm font-medium text-foreground">{d.title}</p>
                <p className="text-xs text-muted-foreground">{d.instruction}</p>
                <p className="mt-1 text-sm text-foreground">{d.prompt}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {state.improvement && (
        <section className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("mission.improvement")}
          </h4>
          <p
            className={cn(
              "text-sm font-semibold tabular-nums",
              state.improvement.improved ? "text-primary" : "text-foreground",
            )}
          >
            {pct(state.improvement.before_overall)} →{" "}
            {pct(state.improvement.after_overall)}
            {state.improvement.delta != null && (
              <span className="ml-2 text-muted-foreground">
                ({state.improvement.delta > 0 ? "+" : ""}
                {Math.round(state.improvement.delta * 100)}%)
              </span>
            )}
          </p>
          {state.improvement.improved ? (
            <p className="text-sm text-primary">{t("mission.improved")}</p>
          ) : (
            <p className="text-sm text-muted-foreground">
              {t("mission.notImproved")}
            </p>
          )}
        </section>
      )}

      {(canAttempt || canRetry) && (
        <div className="space-y-2">
          <textarea
            value={heard}
            onChange={(e) => setHeard(e.target.value)}
            rows={3}
            placeholder={
              canRetry ? t("mission.retryPlaceholder") : t("mission.attemptPlaceholder")
            }
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          />
          <Button
            disabled={busy || !heard.trim()}
            onClick={() => void (canRetry ? sendRetry() : sendAttempt())}
          >
            {canRetry ? t("mission.retry") : t("mission.attempt")}
          </Button>
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}
    </Card>
  );
}
