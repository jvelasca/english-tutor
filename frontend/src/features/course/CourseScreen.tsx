import { useCallback, useEffect, useState } from "react";
import { motion, type Variants } from "motion/react";
import { ArrowRight, Check, Circle, CircleDot, Lock } from "lucide-react";
import {
  getCefrLadder,
  getCourseMap,
  getLevelCompletions,
  getLevelDetail,
  getLevels,
} from "../../api/academy";
import type {
  CefrLadder,
  CourseMap,
  LearningProfile,
  LevelCompletion,
  LevelDetail,
  LevelSummary,
} from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { JourneyNode } from "../../components/JourneyNode";
import { Milestone } from "../../components/Milestone";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { Progress } from "../../components/ui/progress";
import { LevelBadge } from "../../components/LevelBadge";
import { SkillBar } from "../../components/SkillBar";
import { TriadCard } from "../../components/TriadCard";
import { cn } from "../../lib/utils";

const JOURNEY_LEVELS = ["a1", "a2", "b1", "b2"];

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
  },
};

interface CourseScreenProps {
  userId: string | null;
  profile: LearningProfile | null;
  onStartLesson: (
    objectiveId: string,
    title: string,
    levelId: string,
    skills: string[],
  ) => void;
}

function levelState(lv: LevelSummary): "done" | "current" | "locked" {
  if (lv.progress >= 1) return "done";
  if (lv.available && lv.unlocked) return "current";
  return "locked";
}

type CefrState = "mastered" | "in_progress" | "not_started";

function DimensionStateIcon({ state }: { state: CefrState }) {
  if (state === "mastered") {
    return <Check className="size-4 shrink-0 text-success" />;
  }
  if (state === "in_progress") {
    return <CircleDot className="size-4 shrink-0 text-amber-500" />;
  }
  return <Circle className="size-4 shrink-0 text-muted-foreground" />;
}

function sectionLabel(t: (k: string) => string, section: string): string {
  if (["vocabulary", "grammar", "listening", "speaking"].includes(section)) {
    return t(`skill.${section}`);
  }
  return t(`section.${section}`);
}

export function CourseScreen({
  userId,
  profile,
  onStartLesson,
}: CourseScreenProps) {
  const { t } = useI18n();
  const [levels, setLevels] = useState<LevelSummary[]>([]);
  const [completions, setCompletions] = useState<LevelCompletion[]>([]);
  const [detail, setDetail] = useState<LevelDetail | null>(null);
  const [course, setCourse] = useState<CourseMap | null>(null);
  const [currentLevelId, setCurrentLevelId] = useState<string | null>(null);
  const [ladder, setLadder] = useState<CefrLadder | null>(null);

  const load = useCallback(async () => {
    if (!userId) return;
    try {
      const [ls, cs, cefr] = await Promise.all([
        getLevels(userId),
        getLevelCompletions(userId),
        getCefrLadder(userId),
      ]);
      setLevels(ls.levels.filter((l) => JOURNEY_LEVELS.includes(l.level_id)));
      setCompletions(cs);
      setLadder(cefr);
    } catch {
      /* backend no disponible */
    }
  }, [userId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!userId) return;
    const estimated = profile?.estimated_level?.toLowerCase();
    const journey = levels.filter((l) => JOURNEY_LEVELS.includes(l.level_id));
    const match = journey.find((l) => l.level_id === estimated);
    const firstOpen = journey.find((l) => l.available && l.unlocked);
    const target = match ?? firstOpen ?? journey[0] ?? null;
    setCurrentLevelId(target?.level_id ?? null);
  }, [userId, profile, levels]);

  useEffect(() => {
    if (!userId || !currentLevelId) return;
    let cancelled = false;
    void (async () => {
      try {
        const [d, c] = await Promise.all([
          getLevelDetail(userId, currentLevelId),
          getCourseMap(userId, currentLevelId),
        ]);
        if (!cancelled) {
          setDetail(d);
          setCourse(c);
        }
      } catch {
        /* backend no disponible */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, currentLevelId]);

  const nextObjective = detail
    ? detail.objectives.find((o) => o.status === "available")
    : null;

  function continueLesson() {
    if (!detail || !nextObjective) return;
    onStartLesson(
      nextObjective.id,
      nextObjective.title,
      detail.level_id,
      nextObjective.skills,
    );
  }

  const masteredCount = detail?.progress.mastered ?? 0;
  const totalCount = detail?.progress.total ?? 0;
  const readiness = profile?.readiness;
  const readinessPct = Math.max(
    0,
    Math.min(100, Math.round(readiness?.overall ?? 0)),
  );

  const currentUnit =
    course?.units.find((u) => u.status === "current") ??
    course?.units.find((u) => u.status !== "locked") ??
    null;
  const gatesMet = currentUnit?.gates.filter((g) => g.met).length ?? 0;
  const gatesTotal = currentUnit?.gates.length ?? 0;

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
            {t("course.title")}
          </h1>
          <p className="mt-1 text-muted-foreground">
            {t("course.subtitle")} · A1 → B2
          </p>
        </motion.header>

        <motion.section variants={item} aria-label={t("triad.progress")}>
          <TriadCard userId={userId} />
        </motion.section>

        <motion.section variants={item} aria-label={t("course.title")}>
          <Card className="gap-4 p-5">
            <div className="flex items-start overflow-x-auto pb-1">
              {levels.map((lv, i) => {
                const state = levelState(lv);
                const isYou = lv.level_id === currentLevelId;
                return (
                  <div key={lv.level_id} className="flex items-start">
                    {i > 0 && (
                      <div
                        aria-hidden="true"
                        className={cn(
                          "mt-6 h-0.5 w-8 shrink-0 rounded-full sm:w-12",
                          state === "done" ? "bg-primary" : "bg-border",
                        )}
                      />
                    )}
                    <div className="flex w-14 shrink-0 flex-col items-center gap-2">
                      <JourneyNode
                        level={lv.level}
                        state={state}
                        active={isYou}
                        onClick={() => setCurrentLevelId(lv.level_id)}
                        disabled={state === "locked"}
                      />
                      <span
                        className={cn(
                          "h-4 text-[11px] font-semibold",
                          isYou ? "text-primary" : "text-muted-foreground",
                        )}
                      >
                        {isYou ? t("course.you") : ""}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </motion.section>

        {ladder && (
          <motion.section variants={item} aria-label={t("course.cefrLevel")}>
            <Card className="gap-4 p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-base font-semibold">
                  {t("course.cefrLevel")}
                </h2>
                {ladder.estimated_band && (
                  <Badge variant="secondary" className="gap-1.5 tabular-nums">
                    {ladder.estimated_band.toUpperCase()} ·{" "}
                    {ladder.estimated_numeric}
                  </Badge>
                )}
              </div>

              <div className="flex items-start overflow-x-auto pb-1">
                {ladder.bands.map((band, i) => {
                  const current = band.is_current;
                  return (
                    <div key={band.id} className="flex items-start">
                      {i > 0 && (
                        <div
                          aria-hidden="true"
                          className={cn(
                            "mt-4 h-0.5 w-5 shrink-0 rounded-full sm:w-7",
                            current ? "bg-primary" : "bg-border",
                          )}
                        />
                      )}
                      <div className="flex w-14 shrink-0 flex-col items-center gap-1.5">
                        <div
                          className={cn(
                            "grid size-8 place-items-center rounded-full border text-[11px] font-bold",
                            current
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-border bg-card text-muted-foreground",
                          )}
                        >
                          {band.label}
                        </div>
                        <span
                          className={cn(
                            "h-4 text-[11px] font-semibold",
                            current ? "text-primary" : "text-muted-foreground",
                          )}
                        >
                          {current ? t("course.youAreHere") : ""}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          </motion.section>
        )}

        {ladder && (() => {
          const band = ladder.bands.find((b) => b.is_current);
          if (!band) return null;
          return (
            <motion.section variants={item} aria-label={t("course.canDo")}>
              <Card className="gap-4 p-5">
                <div>
                  <h2 className="text-base font-semibold">
                    {t("course.canDo")} · {band.label}
                  </h2>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    {band.title} — {band.description}
                  </p>
                </div>
                <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
                  {ladder.dimensions.map((dim) => {
                    const state = dim.state ?? "not_started";
                    return (
                      <div key={dim.id} className="flex flex-col gap-1.5">
                        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          <DimensionStateIcon state={state} />
                          {dim.label}
                        </p>
                        <ul className="flex flex-col gap-1.5">
                          {(band.can_do[dim.id] ?? []).map((statement, j) => (
                            <li
                              key={j}
                              className="flex items-start gap-2 text-sm text-foreground/90"
                            >
                              <span
                                className={cn(
                                  "mt-2 size-1.5 shrink-0 rounded-full",
                                  state === "mastered"
                                    ? "bg-success"
                                    : state === "in_progress"
                                      ? "bg-amber-500"
                                      : "bg-muted-foreground/40",
                                )}
                              />
                              <span>{statement}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    );
                  })}
                </div>
              </Card>
            </motion.section>
          );
        })()}

        {detail && (
          <motion.section variants={item} aria-label={detail.title}>
            <Card className="gap-5 p-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <LevelBadge level={detail.level} />
                  <div>
                    <h2 className="text-lg font-bold">{detail.title}</h2>
                    <p className="text-sm text-muted-foreground">
                      {detail.description}
                    </p>
                  </div>
                </div>
                <Button
                  size="lg"
                  className="gap-2"
                  onClick={continueLesson}
                  disabled={!nextObjective}
                >
                  {t("course.continue")}
                  <ArrowRight className="size-4" />
                </Button>
              </div>

              <SkillBar
                value={detail.progress.progress}
                hint={`${masteredCount}/${totalCount} ${t("course.mastered")}`}
              />

              {readiness && (
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-baseline justify-between gap-2 text-sm">
                    <span className="text-muted-foreground">
                      {t("home.readyFor")} {readiness.target_level}
                    </span>
                    <span className="text-sm font-semibold tabular-nums">
                      {readinessPct}%
                    </span>
                  </div>
                  <Progress value={readinessPct} className="h-1.5" />
                </div>
              )}
            </Card>
          </motion.section>
        )}

        {course && (
          <motion.section variants={item} aria-label={t("course.whereAmI")}>
            <Card className="gap-4 p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-base font-semibold">
                  {t("course.whereAmI")}
                </h2>
                <span className="text-sm font-semibold tabular-nums text-muted-foreground">
                  {course.level} ·{" "}
                  {Math.round((course.progress.progress ?? 0) * 100)}%
                </span>
              </div>

              <div className="flex items-center overflow-x-auto pb-1">
                {course.units.map((unit, i) => {
                  const state = unit.status;
                  return (
                    <div key={unit.unit_id} className="flex items-center">
                      {i > 0 && (
                        <div
                          aria-hidden="true"
                          className={cn(
                            "h-0.5 w-4 shrink-0 rounded-full",
                            state === "locked" ? "bg-border" : "bg-primary/60",
                          )}
                        />
                      )}
                      <div
                        title={unit.unit_title}
                        className={cn(
                          "flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold",
                          state === "done" &&
                            "border-primary/40 bg-primary/10 text-primary",
                          state === "current" &&
                            "border-primary bg-primary text-primary-foreground",
                          state === "locked" &&
                            "border-border bg-card text-muted-foreground",
                        )}
                      >
                        {state === "done" ? (
                          <Check className="size-3.5" />
                        ) : state === "locked" ? (
                          <Lock className="size-3" />
                        ) : (
                          <span
                            aria-hidden="true"
                            className="size-1.5 rounded-full bg-current"
                          />
                        )}
                        <span>
                          {t("course.unit")} {i + 1}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {course.position.lesson_title && (
                <p className="text-sm">
                  <span className="text-muted-foreground">
                    {t("course.currentLesson")}:
                  </span>{" "}
                  <span className="font-medium">
                    {course.position.unit_title} ·{" "}
                    {course.position.lesson_title}
                  </span>
                </p>
              )}
            </Card>
          </motion.section>
        )}

        {currentUnit && (
          <motion.section variants={item} aria-label={t("course.unit")}>
            <Card className="gap-4 p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-base font-semibold">
                  {t("course.unit")} {currentUnit.unit_order} ·{" "}
                  {currentUnit.unit_title}
                </h2>
                <Badge
                  variant={currentUnit.gate_mastered ? "default" : "secondary"}
                >
                  {currentUnit.gate_mastered
                    ? t("course.unitMastered")
                    : `${gatesMet}/${gatesTotal} ${t("course.gates")}`}
                </Badge>
              </div>

              {currentUnit.objectives.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("course.byTheEnd")}
                  </p>
                  <ul className="flex flex-col gap-1.5">
                    {currentUnit.objectives.map((o, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <ArrowRight className="mt-0.5 size-4 shrink-0 text-primary" />
                        <span>{o}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="flex flex-col gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("course.sections")}
                </p>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {currentUnit.sections.map((s) => (
                    <div
                      key={s.section}
                      className={cn(
                        "flex flex-col gap-0.5 rounded-lg border px-2.5 py-2 text-xs",
                        s.needs_content
                          ? "border-dashed border-border text-muted-foreground"
                          : "border-border bg-card",
                      )}
                    >
                      <span className="font-medium">
                        {sectionLabel(t, s.section)}
                      </span>
                      <span className="tabular-nums">
                        {s.count}
                        {s.needs_content ? ` · ${t("course.needsContent")}` : ""}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {currentUnit.gates.length > 0 && (
                <div className="flex flex-col gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("course.masteryGate")}
                  </p>
                  <ul className="flex flex-col gap-1.5">
                    {currentUnit.gates.map((g) => {
                      const gateValue =
                        g.section === "transfer"
                          ? `${g.value}/${g.required}`
                          : g.section === "retention"
                            ? g.met
                              ? "PASS"
                              : "DUE"
                            : `${Math.round(g.value * 100)}% / ${Math.round(g.required * 100)}%`;
                      return (
                        <li
                          key={g.section}
                          className="flex items-center justify-between gap-2 text-sm"
                        >
                          <span className="flex items-center gap-1.5">
                            {g.met ? (
                              <Check className="size-4 text-success" />
                            ) : g.declared ? (
                              <CircleDot className="size-4 text-amber-500" />
                            ) : (
                              <Circle className="size-4 text-muted-foreground/50" />
                            )}
                            <span
                              className={g.declared ? "" : "text-muted-foreground"}
                            >
                              {g.label}
                            </span>
                          </span>
                          <span className="text-xs tabular-nums text-muted-foreground">
                            {g.declared ? gateValue : "—"}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </Card>
          </motion.section>
        )}

        {detail && (
          <motion.section variants={item} aria-label={t("course.milestones")}>
            <Card className="gap-3 p-5">
              <h2 className="text-base font-semibold">
                {t("course.milestones")}
              </h2>
              <div className="flex flex-col gap-2">
                {detail.objectives.map((obj) => (
                  <Milestone key={obj.id} objective={obj} />
                ))}
              </div>
            </Card>
          </motion.section>
        )}

        {completions.length > 0 && (
          <motion.section variants={item} aria-label={t("course.completed")}>
            <Card className="gap-3 p-5">
              <h2 className="text-base font-semibold">
                {t("course.completed")}
              </h2>
              <div className="flex flex-wrap gap-2">
                {completions.map((c) => (
                  <Badge key={c.id} variant="secondary" className="gap-1.5">
                    {c.level} · {Math.round(c.overall * 100)}%
                  </Badge>
                ))}
              </div>
            </Card>
          </motion.section>
        )}
      </motion.div>
    </div>
  );
}
