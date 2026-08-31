import { useEffect, useState } from "react";
import { ArrowLeft, MessageSquareText } from "lucide-react";
import { getSpeakingScenarios } from "../../api/academy";
import type { SpeakingScenario } from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { LevelBadge } from "../../components/LevelBadge";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { SpeakingRolePlay } from "./SpeakingRolePlay";

/** Clave i18n de cada métrica observada por un escenario. */
function metricLabelKey(metric: string): string {
  return `scenarios.metric.${metric}`;
}

interface SpeakingScenariosProps {
  userId: string | null;
}

/**
 * Catálogo de escenarios comunicativos (Speaking 3.0). Cada escenario declara
 * un objetivo comunicativo y las métricas que observa (task_completion,
 * interaction, fluency, repair, turn_taking). Al practicar se reutiliza
 * `SpeakingRolePlay`, que registra la telemetría de turnos del alumno
 * (`duration_ms`/`latency_ms`) para alimentar la señal objetiva de interacción.
 */
export function SpeakingScenarios({ userId }: SpeakingScenariosProps) {
  const { t } = useI18n();
  const [scenarios, setScenarios] = useState<SpeakingScenario[]>([]);
  const [active, setActive] = useState<SpeakingScenario | null>(null);
  const [finished, setFinished] = useState(false);

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

  if (active) {
    return (
      <Card className="gap-4 p-5">
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            className="min-h-9 gap-1 px-2 text-sm"
            onClick={() => {
              setActive(null);
              setFinished(false);
            }}
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            {t("scenarios.back")}
          </Button>
        </div>

        <header className="flex flex-wrap items-center gap-2">
          <h4 className="text-base font-semibold">{active.title}</h4>
          <LevelBadge level={active.cefr_target} />
        </header>

        <div className="flex flex-col gap-2 rounded-md border border-border bg-muted px-3 py-2.5">
          <span className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
            {t("scenarios.objective")}
          </span>
          <p className="text-sm leading-relaxed text-foreground">
            {active.communicative_objective}
          </p>
        </div>

        {!finished ? (
          <SpeakingRolePlay
            key={active.id}
            userId={userId}
            scenario={active.prompt}
            onFinish={() => setFinished(true)}
          />
        ) : (
          <div className="flex flex-col gap-3">
            <p className="flex items-center gap-2 text-sm font-semibold text-success">
              <MessageSquareText className="size-4" aria-hidden="true" />
              {t("scenarios.completed")}
            </p>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {t("scenarios.completedNote")}
            </p>
            <div className="flex flex-col gap-1.5">
              <span className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                {t("scenarios.metrics")}
              </span>
              <ul className="flex flex-wrap gap-2">
                {active.metrics.map((metric) => (
                  <li key={metric}>
                    <Badge variant="outline" className="gap-1.5">
                      {t(metricLabelKey(metric))}
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
            <Button
              variant="outline"
              className="min-h-10 self-start"
              onClick={() => setFinished(false)}
            >
              {t("scenarios.practice")}
            </Button>
          </div>
        )}
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">{t("scenarios.subtitle")}</p>
      {scenarios.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("scenarios.empty")}</p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {scenarios.map((scenario) => (
            <li key={scenario.id}>
              <Card className="h-full gap-3 p-4">
                <header className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold">{scenario.title}</span>
                  <LevelBadge level={scenario.cefr_target} />
                </header>
                <p className="text-xs text-muted-foreground">
                  {scenario.category}
                </p>
                <p className="text-sm leading-relaxed text-foreground">
                  {scenario.communicative_objective}
                </p>
                <ul className="flex flex-wrap gap-1.5">
                  {scenario.metrics.map((metric) => (
                    <li key={metric}>
                      <Badge variant="outline">{t(metricLabelKey(metric))}</Badge>
                    </li>
                  ))}
                </ul>
                <Button
                  className="min-h-10 self-start"
                  onClick={() => setActive(scenario)}
                >
                  {t("scenarios.practice")}
                </Button>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
