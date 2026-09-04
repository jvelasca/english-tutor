import { useCallback, useEffect, useState } from "react";
import { motion, type Variants } from "motion/react";
import {
  ArrowRight,
  Check,
  Circle,
  CircleDot,
  Loader2,
  Lock,
} from "lucide-react";
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
import { LevelBadge } from "../../components/LevelBadge";
import { SkillBar } from "../../components/SkillBar";
import { AssessmentLadder } from "../assessment/AssessmentLadder";
import { cn } from "../../lib/utils";

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

/**
 * FORMACIÓN V3.1 — una única pantalla de curso por nivel:
 *  A) escalera CEFR completa A1→C2 ("Mi nivel"),
 *  B) hero del curso actual con [Continuar curso],
 *  C) lista vertical de unidades con gating visible,
 *  D) detalle de la unidad seleccionada,
 *  E) evaluaciones (AssessmentLadder, D5) siempre visibles,
 *  F) badges de niveles certificados.
 */
interface CourseScreenProps {
  userId: string | null;
  profile: LearningProfile | null;
  onStartLesson: (
    objectiveId: string,
    title: string,
    levelId: string,
    skills: string[],
  ) => void;
  /** Navega a MI PROGRESO (#/progreso), CTA de la tarjeta "Mi nivel". */
  onOpenProgress?: () => void;
}

type LoadState = "idle" | "loading" | "error" | "done";

function nodeState(lv: LevelSummary, currentLevelId: string | null) {
  if (lv.progress >= 1) return "done" as const;
  if (lv.level_id === currentLevelId) return "current" as const;
  return "locked" as const;
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
  onOpenProgress,
}: CourseScreenProps) {
  const { t } = useI18n();
  const [levels, setLevels] = useState<LevelSummary[]>([]);
  const [completions, setCompletions] = useState<LevelCompletion[]>([]);
  const [detail, setDetail] = useState<LevelDetail | null>(null);
  const [course, setCourse] = useState<CourseMap | null>(null);
  const [currentLevelId, setCurrentLevelId] = useState<string | null>(null);
  // Escalera CEFR (getCefrLadder) se mantiene en el cableado de arranque para
  // no cambiar el contrato; los can-do viven en MI PROGRESO (UI_V3.1 §4.4).
  const [, setLadder] = useState<CefrLadder | null>(null);
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(null);
  const [lockedLevel, setLockedLevel] = useState<LevelSummary | null>(null);
  const [topState, setTopState] = useState<LoadState>("idle");
  const [levelState, setLevelState] = useState<LoadState>("idle");
  const [retryTick, setRetryTick] = useState(0);

  const loadTop = useCallback(async () => {
    if (!userId) return;
    setTopState("loading");
    try {
      const [ls, cs, cefr] = await Promise.all([
        getLevels(userId),
        getLevelCompletions(userId),
        getCefrLadder(userId),
      ]);
      setLevels(ls.levels);
      setCompletions(cs);
      setLadder(cefr);
      setTopState("done");
    } catch {
      setTopState("error");
    }
  }, [userId]);

  useEffect(() => {
    void loadTop();
  }, [loadTop, retryTick]);

  // Nivel objetivo por defecto: estimado del perfil aún no dominado, si no el
  // primer nivel abierto, si no el estimado (repaso) y por último el primero.
  useEffect(() => {
    if (!userId) return;
    const estimated = profile?.estimated_level?.toLowerCase();
    const openInLevel = levels.find(
      (l) => l.level_id === estimated && l.progress < 1,
    );
    const firstOpen = levels.find((l) => l.available && l.unlocked);
    const match = levels.find((l) => l.level_id === estimated);
    const target = openInLevel ?? firstOpen ?? match ?? levels[0] ?? null;
    setCurrentLevelId((prev) => target?.level_id ?? prev);
  }, [userId, profile, levels]);

  useEffect(() => {
    if (!userId || !currentLevelId) {
      setLevelState("idle");
      return;
    }
    let cancelled = false;
    setLevelState("loading");
    void (async () => {
      try {
        const [d, c] = await Promise.all([
          getLevelDetail(userId, currentLevelId),
          getCourseMap(userId, currentLevelId),
        ]);
        if (!cancelled) {
          setDetail(d);
          setCourse(c);
          setLevelState("done");
        }
      } catch {
        if (!cancelled) setLevelState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, currentLevelId]);

  // Al cambiar de nivel/curso, la unidad seleccionada vuelve a la "current".
  useEffect(() => {
    if (!course) {
      setSelectedUnitId(null);
      return;
    }
    const current =
      course.units.find((u) => u.status === "current") ??
      course.units.find((u) => u.status !== "locked");
    setSelectedUnitId(current?.unit_id ?? null);
  }, [course]);

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

  function handleLevelClick(lv: LevelSummary) {
    const state = nodeState(lv, currentLevelId);
    if (state === "locked") {
      setLockedLevel(lv);
      return;
    }
    setLockedLevel(null);
    setCurrentLevelId(lv.level_id);
  }

  const selectedUnit =
    course?.units.find((u) => u.unit_id === selectedUnitId) ?? null;

  const unitObjectives =
    detail && selectedUnit
      ? detail.objectives.filter((o) => o.unit_id === selectedUnit.unit_id)
      : [];

  const continueInUnit =
    !!nextObjective && nextObjective.unit_id === selectedUnitId;

  if (!userId) {
    return (
      <div className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6 lg:py-10">
        <Card
          role="status"
          className="p-8 text-center text-sm text-muted-foreground"
        >
          {t("empty.noProfile")}
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6 lg:py-10">
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-6"
      >
        <motion.header variants={item}>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            {t("course.title")}
          </h1>
          <p className="mt-1 text-muted-foreground">{t("course.subtitle")}</p>
        </motion.header>

        {/* A. Mi nivel — escalera CEFR A1→C2 con selección de nivel. */}
        <motion.section variants={item} aria-label={t("course.myLevel")}>
          {topState === "loading" ? (
            <Card
              role="status"
              aria-busy="true"
              aria-live="polite"
              className="flex items-center justify-center gap-2 p-6 text-sm text-muted-foreground"
            >
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              {t("common.loading")}
            </Card>
          ) : topState === "error" ? (
            <Card className="flex flex-col items-center gap-3 p-6 text-center">
              <p className="text-sm text-muted-foreground">
                {t("home.unavailable")}
              </p>
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                onClick={() => setRetryTick((n) => n + 1)}
              >
                {t("home.retry")}
              </Button>
            </Card>
          ) : (
            <Card className="gap-4 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-base font-semibold">
                  {t("course.myLevel")}
                </h2>
                {onOpenProgress && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1.5"
                    onClick={onOpenProgress}
                  >
                    {t("home.seeProgress")}
                    <ArrowRight className="size-4" aria-hidden="true" />
                  </Button>
                )}
              </div>

              {levels.length > 0 ? (
                <>
                  <div
                    role="group"
                    aria-label={t("course.cefrLevel")}
                    className="flex items-start overflow-x-auto pb-2"
                  >
                    {levels.map((lv, i) => {
                      const state = nodeState(lv, currentLevelId);
                      const isYou = lv.level_id === currentLevelId;
                      return (
                        <div key={lv.level_id} className="flex items-start">
                          {i > 0 && (
                            <div
                              aria-hidden="true"
                              className={cn(
                                "mt-6 h-0.5 w-6 shrink-0 rounded-full sm:w-10",
                                state === "done" ? "bg-primary" : "bg-border",
                              )}
                            />
                          )}
                          <div className="flex w-16 shrink-0 flex-col items-center gap-2">
                            <JourneyNode
                              level={lv.level}
                              state={state}
                              active={isYou}
                              onClick={() => handleLevelClick(lv)}
                            />
                            <span
                              className={cn(
                                "h-4 text-[11px] font-semibold",
                                isYou
                                  ? "text-primary"
                                  : "text-muted-foreground",
                              )}
                            >
                              {isYou ? t("course.you") : ""}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {lockedLevel && (
                    <p
                      role="status"
                      className="flex items-center gap-2 rounded-lg border border-border/60 bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
                    >
                      <Lock className="size-4 shrink-0" aria-hidden="true" />
                      <span>
                        <span className="font-semibold text-foreground">
                          {lockedLevel.level}
                        </span>{" "}
                        · {t("course.lockedHint")}
                      </span>
                    </p>
                  )}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {t("journey.empty")}
                </p>
              )}
            </Card>
          )}
        </motion.section>

        {/* B. Curso actual — hero del nivel con [Continuar curso]. */}
        <motion.section
          variants={item}
          aria-label={detail?.title ?? t("course.title")}
        >
          {detail ? (
            <Card className="gap-5 p-5">
              <div className="flex items-center gap-3">
                <LevelBadge level={detail.level} />
                <div className="min-w-0">
                  <h2 className="text-lg font-bold leading-tight">
                    {detail.title}
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    {detail.description}
                  </p>
                </div>
              </div>

              <SkillBar
                value={detail.progress.progress}
                hint={`${detail.progress.mastered}/${detail.progress.total} ${t("course.mastered")}`}
              />

              {course && (course.position.unit_title || course.position.lesson_title) && (
                <p className="text-sm">
                  <span className="text-muted-foreground">
                    {t("course.currentLesson")}:
                  </span>{" "}
                  <span className="font-medium">
                    {course.position.unit_title}
                    {course.position.lesson_title
                      ? ` · ${course.position.lesson_title}`
                      : ""}
                  </span>
                </p>
              )}

              <div className="flex flex-wrap items-center gap-3">
                <Button
                  size="lg"
                  className="w-full gap-2 sm:w-auto"
                  onClick={continueLesson}
                  disabled={!nextObjective}
                >
                  {nextObjective ? (
                    <>
                      {t("course.continueCourse")}
                      <ArrowRight className="size-4" aria-hidden="true" />
                    </>
                  ) : (
                    <>
                      <Check className="size-4" aria-hidden="true" />
                      {t("course.levelComplete")}
                    </>
                  )}
                </Button>
              </div>
            </Card>
          ) : levelState === "error" ? (
            <Card className="flex flex-col items-center gap-2 p-6 text-center">
              <p className="text-sm text-muted-foreground">
                {t("home.unavailable")}
              </p>
            </Card>
          ) : topState === "error" ? null : (
            <Card
              role="status"
              aria-busy="true"
              aria-live="polite"
              className="flex items-center justify-center gap-2 p-6 text-sm text-muted-foreground"
            >
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              {t("common.loading")}
            </Card>
          )}
        </motion.section>

        {/* C. Unidades del nivel — lista vertical con gating visible. */}
        {course && course.units.length > 0 && (
          <motion.section variants={item} aria-label={t("course.units")}>
            <Card className="gap-4 p-5">
              <h2 className="text-base font-semibold">{t("course.units")}</h2>
              <ul className="flex flex-col gap-2">
                {course.units.map((unit) => {
                  const isSelected = unit.unit_id === selectedUnitId;
                  const isLocked = unit.status === "locked";
                  const gatesMet = unit.gates.filter((g) => g.met).length;
                  const subInfo =
                    isLocked
                      ? t("course.locked")
                      : unit.status === "current" && unit.gates.length > 0
                        ? `${gatesMet}/${unit.gates.length} ${t("course.gates")}`
                        : `${unit.mastered}/${unit.total}`;
                  return (
                    <li key={unit.unit_id}>
                      <button
                        type="button"
                        disabled={isLocked}
                        aria-current={isSelected ? "step" : undefined}
                        onClick={() => {
                          setSelectedUnitId(unit.unit_id);
                          setLockedLevel(null);
                        }}
                        className={cn(
                          "flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition-colors",
                          isSelected
                            ? "border-primary/60 bg-primary/5"
                            : "border-border bg-card hover:bg-accent/50",
                          !isSelected && unit.status === "done" && "opacity-70",
                          isLocked && "cursor-not-allowed opacity-50",
                        )}
                      >
                        <span
                          aria-hidden="true"
                          className={cn(
                            "grid size-9 shrink-0 place-items-center rounded-full",
                            unit.status === "done" &&
                              "bg-success/10 text-success",
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
                          <span className="block truncate text-sm font-semibold">
                            {t("course.unit")} {unit.unit_order} ·{" "}
                            {unit.unit_title}
                          </span>
                          <span className="block text-xs text-muted-foreground">
                            {subInfo}
                          </span>
                        </span>
                        {isSelected && (
                          <ArrowRight
                            className="size-4 shrink-0 text-primary"
                            aria-hidden="true"
                          />
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </Card>
          </motion.section>
        )}

        {/* D. Detalle de la unidad seleccionada. */}
        {course && selectedUnit && (
          <motion.section
            variants={item}
            aria-label={`${t("course.unit")} ${selectedUnit.unit_order}`}
          >
            <Card className="gap-4 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  {detail && <LevelBadge level={detail.level} />}
                  <h3 className="text-base font-bold leading-tight">
                    {t("course.unit")} {selectedUnit.unit_order} ·{" "}
                    {selectedUnit.unit_title}
                  </h3>
                </div>
                {selectedUnit.status === "done" && (
                  <Badge className="gap-1.5">
                    <Check className="size-3" aria-hidden="true" />
                    {t("course.unitMastered")}
                  </Badge>
                )}
              </div>

              {selectedUnit.objectives.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("course.byTheEnd")}
                  </p>
                  <ul className="flex flex-col gap-1.5">
                    {selectedUnit.objectives.map((o, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <ArrowRight
                          className="mt-0.5 size-4 shrink-0 text-primary"
                          aria-hidden="true"
                        />
                        <span>{o}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {selectedUnit.sections.length > 0 && (
                <div className="flex flex-col gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("course.sections")}
                  </p>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {selectedUnit.sections.map((s) => (
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
                          {s.needs_content
                            ? ` · ${t("course.needsContent")}`
                            : ""}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selectedUnit.gates.length > 0 && (
                <div className="flex flex-col gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("course.masteryGate")}
                  </p>
                  <ul className="flex flex-col gap-1.5">
                    {selectedUnit.gates.map((g) => {
                      const gateValue =
                        g.section === "transfer"
                          ? `${g.value}/${g.required}`
                          : g.section === "retention"
                            ? g.met
                              ? t("course.gatePass")
                              : t("course.gateDue")
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
                              className={
                                g.declared ? "" : "text-muted-foreground"
                              }
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

              {unitObjectives.length > 0 && (
                <div className="flex flex-col gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("course.milestones")}
                  </p>
                  <div className="flex flex-col gap-1.5">
                    {unitObjectives.map((o) => (
                      <Milestone key={o.id} objective={o} />
                    ))}
                  </div>
                </div>
              )}

              {continueInUnit && (
                <Button
                  className="w-full gap-2 sm:w-auto"
                  onClick={continueLesson}
                >
                  {t("course.continue")}
                  <ArrowRight className="size-4" aria-hidden="true" />
                </Button>
              )}
            </Card>
          </motion.section>
        )}

        {/* E. Evaluaciones (D5) — bloque siempre visible. */}
        <motion.section variants={item} aria-label={t("course.evaluations")}>
          <Card className="gap-4 p-5">
            <h2 className="text-base font-semibold">
              {t("course.evaluations")}
            </h2>
            <AssessmentLadder
              userId={userId}
              levelId={detail?.level_id ?? undefined}
            />
          </Card>
        </motion.section>

        {/* F. Niveles certificados (badges). */}
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
