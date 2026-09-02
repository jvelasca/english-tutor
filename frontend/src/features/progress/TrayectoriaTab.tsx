import { useEffect, useState } from "react";
import { Flag, MapPin } from "lucide-react";
import {
  getCefrLadder,
  getCourseMap,
  getStudentModel,
} from "../../api/academy";
import type { CefrLadder, CourseMap, StudentModel } from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { JourneyNode } from "../../components/JourneyNode";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { cn } from "../../lib/utils";
import { SectionHeading, TabLoading } from "./tabBits";

interface TrayectoriaTabProps {
  userId: string;
  refreshKey: number;
}

/**
 * Trayectoria — la escalera CEFR como concepto "journey" (dominado/actual/
 * pendiente) en versión compacta, sin cabecera de página duplicada. Reutiliza
 * la lógica de JourneyScreen (cefr-ladder + student-model + course-map).
 */
export function TrayectoriaTab({ userId, refreshKey }: TrayectoriaTabProps) {
  const { t } = useI18n();
  const [ladder, setLadder] = useState<CefrLadder | null>(null);
  const [model, setModel] = useState<StudentModel | null>(null);
  const [course, setCourse] = useState<CourseMap | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setDone(false);
    void (async () => {
      try {
        const [l, m] = await Promise.all([
          getCefrLadder(userId),
          getStudentModel(userId),
        ]);
        if (cancelled) return;
        setLadder(l);
        setModel(m);
        const c = await getCourseMap(userId, m.level_id);
        if (cancelled) return;
        setCourse(c);
        setDone(true);
      } catch {
        if (!cancelled) setDone(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, refreshKey]);

  if (!done) return <TabLoading />;

  if (!ladder && !model) {
    return (
      <Card className="p-6 text-center">
        <p className="text-sm text-muted-foreground">{t("empty.noProgress")}</p>
      </Card>
    );
  }

  const bands = (ladder?.bands ?? []).filter((b) => !b.id.endsWith("+"));
  const you = ladder?.estimated_band ?? model?.current_level.toLowerCase() ?? null;
  const youNumeric = ladder?.estimated_numeric ?? null;

  const unitsMastered =
    course?.units.filter((u) => u.status === "done").length ?? 0;
  const unitsTotal = course?.units.length ?? 0;

  const readySkills = model?.readiness.skills ?? [];
  const skillsReady = readySkills.filter((s) => s.ready).length;

  const evidence = (model?.mastery ?? []).filter((m) => m.evidence_count > 0);
  const retention =
    evidence.length > 0
      ? evidence.reduce((acc, m) => acc + m.retention, 0) / evidence.length
      : 0;

  const nextMilestone =
    bands.find((b) => youNumeric != null && b.numeric > youNumeric) ?? null;

  const hasData = (model?.mastery ?? []).length > 0;

  return (
    <div className="flex flex-col gap-5">
      <section aria-label={t("progress.journeyTab")}>
        <SectionHeading>{t("journey.subtitle")}</SectionHeading>
        <Card className="gap-5 p-5">
          <div className="flex items-start overflow-x-auto pb-3">
            {bands.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {t("journey.empty")}
              </p>
            ) : (
              bands.map((b, i) => {
                const isYou = b.id === you;
                const state =
                  youNumeric == null
                    ? "locked"
                    : b.numeric < youNumeric
                      ? "done"
                      : isYou
                        ? "current"
                        : "locked";
                return (
                  <div key={b.id} className="flex items-start">
                    {i > 0 && (
                      <div
                        aria-hidden="true"
                        className={cn(
                          "mt-6 h-0.5 w-6 shrink-0 rounded-full sm:w-10",
                          state === "done" ? "bg-primary" : "bg-border",
                        )}
                      />
                    )}
                    <div className="flex w-16 shrink-0 flex-col items-center gap-1.5">
                      <JourneyNode
                        level={b.label}
                        state={state}
                        active={isYou}
                        disabled
                      />
                      {isYou ? (
                        <span className="flex items-center gap-1 text-[11px] font-semibold text-primary">
                          <MapPin className="size-3" aria-hidden="true" />
                          {t("journey.you")}
                        </span>
                      ) : (
                        <span className="h-4 text-[11px] font-medium text-muted-foreground">
                          {b.title}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {hasData && (
            <div className="grid grid-cols-3 gap-3 border-t border-border/60 pt-4 text-center">
              <JourneyStat
                label={t("journey.unitsMastered")}
                value={`${unitsMastered}/${unitsTotal}`}
              />
              <JourneyStat
                label={t("journey.skillsReady")}
                value={`${skillsReady}/${readySkills.length}`}
              />
              <JourneyStat
                label={t("journey.retention")}
                value={`${Math.round(retention * 100)}%`}
              />
            </div>
          )}
        </Card>
      </section>

      {nextMilestone && (
        <section aria-label={t("journey.nextMilestone")}>
          <SectionHeading>{t("journey.nextMilestone")}</SectionHeading>
          <Card className="gap-1 p-5">
            <div className="flex items-center justify-between gap-2">
              <p className="flex items-center gap-2 text-sm font-semibold">
                <Flag className="size-4 text-primary" aria-hidden="true" />
                {t("journey.nextMilestone")}
              </p>
              <Badge variant="secondary">{nextMilestone.label}</Badge>
            </div>
            <h3 className="text-lg font-semibold">{nextMilestone.title}</h3>
            <p className="text-sm text-muted-foreground">
              {nextMilestone.description}
            </p>
          </Card>
        </section>
      )}

      {!hasData && (
        <Card className="p-6 text-center">
          <p className="text-sm text-muted-foreground">{t("journey.empty")}</p>
        </Card>
      )}
    </div>
  );
}

function JourneyStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-lg font-bold tabular-nums">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}
