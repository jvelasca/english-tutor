import { useEffect, useState } from "react";
import { Check, Lock, RefreshCw } from "lucide-react";
import { getCourseMap, getStudentModel } from "../../api/academy";
import type { CourseMap, StudentModel } from "../../types/api";
import { navigateTo } from "../../router/hash";
import { FORMATION_PATH } from "../../router/paths";
import { useI18n } from "../../hooks/useI18n";
import { LevelBadge } from "../../components/LevelBadge";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Progress } from "../../components/ui/progress";
import { cn } from "../../lib/utils";
import { SectionHeading, TabLoading } from "./tabBits";

interface CursoTabProps {
  userId: string;
  refreshKey: number;
}

type LoadState = "idle" | "loading" | "done" | "error";

/**
 * Curso — nivel actual del curso: nivel CEFR + % de unidades completadas +
 * lista READ-ONLY de unidades del nivel (gating visible, sin navegación) +
 * CTA "Continuar en Formación".
 */
export function CursoTab({ userId, refreshKey }: CursoTabProps) {
  const { t } = useI18n();
  const [model, setModel] = useState<StudentModel | null>(null);
  const [course, setCourse] = useState<CourseMap | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [retryTick, setRetryTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    void (async () => {
      try {
        const m = await getStudentModel(userId);
        if (cancelled) return;
        setModel(m);
        const c = await getCourseMap(userId, m.level_id);
        if (cancelled) return;
        setCourse(c);
        setState("done");
      } catch {
        if (!cancelled) setState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, refreshKey, retryTick]);

  if (state === "loading") return <TabLoading />;

  if (state === "error" || !model || !course) {
    return (
      <Card className="flex flex-col items-center gap-3 p-6 text-center">
        <p className="text-sm text-muted-foreground">
          {model ? t("empty.noProgress") : t("empty.noProfile")}
        </p>
        <Button
          variant="outline"
          size="sm"
          className="gap-2"
          onClick={() => setRetryTick((n) => n + 1)}
        >
          <RefreshCw className="size-4" aria-hidden="true" />
          {t("home.retry")}
        </Button>
      </Card>
    );
  }

  const done = course.units.filter((u) => u.status === "done").length;
  const total = course.units.length;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  const pos = course.position;
  const nextLabel =
    pos.objective_title ??
    pos.lesson_title ??
    pos.unit_title ??
    pos.module_title;

  return (
    <div className="flex flex-col gap-5">
      <section aria-label={t("progress.currentCourseLevel")}>
        <SectionHeading>{t("progress.currentCourseLevel")}</SectionHeading>
        <Card className="gap-4 p-5">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <LevelBadge level={course.level} showLabel={false} />
              <div>
                <p className="text-base font-bold leading-tight text-foreground">
                  {course.title}
                </p>
                <p className="text-xs text-muted-foreground">
                  {course.progress.mastered}/{course.progress.total}{" "}
                  {t("progress.unitsCompleted")}
                </p>
              </div>
            </div>
            <span className="text-2xl font-bold tabular-nums text-primary">
              {pct}%
            </span>
          </div>

          <Progress
            value={pct}
            aria-label={t("progress.currentCourseLevel")}
          />

          {!pos.complete && nextLabel ? (
            <div className="rounded-lg border border-border/60 bg-muted/40 px-3 py-2 text-sm">
              <span className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                {t("progress.nextUp")}:{" "}
              </span>
              <span className="font-medium text-foreground">{nextLabel}</span>
            </div>
          ) : (
            <p className="flex items-center gap-2 rounded-lg border border-success/25 bg-success/10 px-3 py-2 text-sm font-medium text-success">
              <Check className="size-4" aria-hidden="true" />
              {t("progress.levelComplete")}
            </p>
          )}

          <Button
            className="min-h-11 w-full sm:w-auto"
            onClick={() => navigateTo(FORMATION_PATH)}
          >
            {t("progress.continueFormation")}
          </Button>
        </Card>
      </section>

      <section aria-label={t("course.units")}>
        <SectionHeading>{t("course.units")}</SectionHeading>
        <Card className="gap-4 p-5">
          <ul className="flex flex-col gap-2">
            {course.units.map((unit) => {
              const isLocked = unit.status === "locked";
              const gatesMet = unit.gates.filter((g) => g.met).length;
              const subInfo = isLocked
                ? t("course.locked")
                : unit.status === "current" && unit.gates.length > 0
                  ? `${gatesMet}/${unit.gates.length} ${t("course.gates")}`
                  : `${unit.mastered}/${unit.total}`;
              return (
                <li
                  key={unit.unit_id}
                  className={cn(
                    "flex items-center gap-3 rounded-xl border px-4 py-3",
                    unit.status === "current"
                      ? "border-primary/60 bg-primary/5"
                      : "border-border bg-card",
                    isLocked && "opacity-60",
                  )}
                >
                  <span
                    aria-hidden="true"
                    className={cn(
                      "grid size-9 shrink-0 place-items-center rounded-full",
                      unit.status === "done" && "bg-success/10 text-success",
                      unit.status === "current" &&
                        "bg-primary/10 text-primary",
                      isLocked && "bg-muted text-muted-foreground/60",
                    )}
                  >
                    {unit.status === "done" ? (
                      <Check className="size-4" />
                    ) : isLocked ? (
                      <Lock className="size-4" />
                    ) : (
                      <span className="size-2 rounded-full bg-current" />
                    )}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-foreground">
                      {t("course.unit")} {unit.unit_order} · {unit.unit_title}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      {subInfo}
                    </span>
                  </span>
                  {unit.status === "current" && (
                    <Badge variant="secondary" className="shrink-0">
                      {t("course.inProgress")}
                    </Badge>
                  )}
                </li>
              );
            })}
          </ul>
        </Card>
      </section>
    </div>
  );
}
