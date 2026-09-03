import { useEffect, useState } from "react";
import type {
  Bucket,
  LearningEvent,
  ProgressHistory,
  StudentModel,
} from "../../types/api";
import { getProgressHistory } from "../../api/progress";
import { getEvents } from "../../api/learning";
import { getStudentModel } from "../../api/academy";
import { useI18n } from "../../hooks/useI18n";
import { TriadCard } from "../../components/TriadCard";
import {
  BucketToggle,
  ProgressDashboard,
} from "../../components/ProgressDashboard";
import { EstimatedLevelBadge } from "../../components/LevelBadge";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { SkillBar } from "../../components/SkillBar";
import { TabLoading, SectionHeading } from "./tabBits";

interface ResumenTabProps {
  userId: string;
  refreshKey: number;
}

/**
 * Resumen — cabecera compacta de posición (nivel + readiness + overall),
 * tríada Progress/Mastery/Readiness y el histórico real de actividad con
 * selector de agrupación day/week/month.
 */
export function ResumenTab({ userId, refreshKey }: ResumenTabProps) {
  const { t } = useI18n();
  const [model, setModel] = useState<StudentModel | null>(null);
  const [modelReady, setModelReady] = useState(false);
  const [bucket, setBucket] = useState<Bucket>("week");
  const [history, setHistory] = useState<ProgressHistory | null>(null);
  const [events, setEvents] = useState<LearningEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    void (async () => {
      try {
        const m = await getStudentModel(userId);
        if (!cancelled) setModel(m);
      } catch {
        if (!cancelled) setModel(null);
      } finally {
        if (!cancelled) setModelReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, refreshKey]);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setHistoryLoading(true);
    void (async () => {
      try {
        const h = await getProgressHistory(userId, bucket);
        if (!cancelled) {
          setHistory(h);
          setHistoryLoading(false);
        }
      } catch {
        if (!cancelled) {
          setHistory(null);
          setHistoryLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, bucket, refreshKey]);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    void (async () => {
      try {
        const e = await getEvents(userId);
        if (!cancelled) setEvents(e);
      } catch {
        if (!cancelled) setEvents([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, refreshKey]);

  const level = model?.estimated_level ?? null;
  const overall = Math.round(model?.readiness.overall ?? 0);
  const band = model?.readiness.band ?? "developing";

  return (
    <div className="flex flex-col gap-5">
      {/* Cabecera compacta de posición */}
      {modelReady && model ? (
        <Card className="gap-3 p-5">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <p className="text-sm font-semibold text-foreground">
              {t("progress.overall")}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {level && <EstimatedLevelBadge level={level} />}
              <Badge variant="secondary">
                {model.target_level} · {t(`readiness.${band}`)}
              </Badge>
            </div>
          </div>
          <SkillBar
            label={t("progress.overall")}
            value={overall / 100}
            hint={`${overall}%`}
          />
        </Card>
      ) : modelReady ? null : (
        <TabLoading />
      )}

      <section aria-label={t("progress.title")}>
        <SectionHeading>{t("triad.progress")} · {t("triad.mastery")} · {t("triad.readiness")}</SectionHeading>
        <TriadCard userId={userId} refreshKey={refreshKey} />
      </section>

      <section aria-label={t("progress.activityTitle")}>
        <SectionHeading>{t("progress.activityTitle")}</SectionHeading>
        <Card className="gap-0 overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
            <p className="text-sm font-semibold">{t("progress.activityTitle")}</p>
            <BucketToggle value={bucket} onChange={setBucket} />
          </div>
          <div className="p-4">
            {historyLoading && history === null ? (
              <TabLoading />
            ) : (
              <ProgressDashboard history={history} events={events} />
            )}
          </div>
        </Card>
      </section>
    </div>
  );
}
