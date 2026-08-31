import { useEffect, useState } from "react";
import { motion, type Variants } from "motion/react";
import { Flag, MapPin } from "lucide-react";
import {
  getCefrLadder,
  getCourseMap,
  getStudentModel,
} from "../../api/academy";
import type { CefrLadder, CourseMap, StudentModel } from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { JourneyNode } from "../../components/JourneyNode";
import { TriadCard } from "../../components/TriadCard";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { cn } from "../../lib/utils";

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] },
  },
};

interface JourneyScreenProps {
  userId: string | null;
}

/**
 * Learning Journey (V2.2): la escalera Pre-A1 → C2 con el marcador "YOU",
 * junto a `units mastered`, `skills ready`, `retention %` y `next milestone`.
 * Reutiliza cefr-ladder, course_map, readiness y mastery (sin backend nuevo).
 */
export function JourneyScreen({ userId }: JourneyScreenProps) {
  const { t } = useI18n();
  const [ladder, setLadder] = useState<CefrLadder | null>(null);
  const [model, setModel] = useState<StudentModel | null>(null);
  const [course, setCourse] = useState<CourseMap | null>(null);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
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
        if (!cancelled) setCourse(c);
      } catch {
        /* backend no disponible */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

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
    <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-5"
      >
        <motion.header variants={item}>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            {t("journey.title")}
          </h1>
          <p className="mt-1 text-muted-foreground">{t("journey.subtitle")}</p>
        </motion.header>

        <motion.section variants={item}>
          <TriadCard userId={userId} />
        </motion.section>

        <motion.section variants={item} aria-label={t("journey.title")}>
          <Card className="gap-5 p-5">
            <div className="flex items-start overflow-x-auto pb-3">
              {bands.map((b, i) => {
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
              })}
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
        </motion.section>

        {nextMilestone && (
          <motion.section variants={item} aria-label={t("journey.nextMilestone")}>
            <Card className="gap-1 p-5">
              <div className="flex items-center justify-between gap-2">
                <p className="flex items-center gap-2 text-sm font-semibold">
                  <Flag className="size-4 text-primary" aria-hidden="true" />
                  {t("journey.nextMilestone")}
                </p>
                <Badge variant="secondary">{nextMilestone.label}</Badge>
              </div>
              <h2 className="text-lg font-semibold">{nextMilestone.title}</h2>
              <p className="text-sm text-muted-foreground">
                {nextMilestone.description}
              </p>
            </Card>
          </motion.section>
        )}

        {!hasData && (
          <motion.p variants={item} className="text-sm text-muted-foreground">
            {t("journey.empty")}
          </motion.p>
        )}
      </motion.div>
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
