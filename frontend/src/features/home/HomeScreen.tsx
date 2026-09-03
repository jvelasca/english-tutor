import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { motion, type Variants } from "motion/react";
import {
  ArrowRight,
  BookOpenCheck,
  CheckCircle2,
  Flame,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { getFsrsSummary, getNextBestActivity } from "../../api/academy";
import type {
  FsrsSummary,
  LearningProfile,
  NextBestActivity,
  ProgressHistory,
  SessionStep,
} from "../../types/api";
import type { Section } from "../../utils/sections";
import { SKILL_LABELS } from "../../utils/learningLabels";
import { useI18n } from "../../hooks/useI18n";
import { NextBestCard } from "../../components/NextBestCard";
import { EstimatedLevelBadge } from "../../components/LevelBadge";
import { SkillBar } from "../../components/SkillBar";
import { TodayPlan } from "../../components/TodayPlan";
import { FsrsReviewPanel } from "../../features/review/FsrsReviewPanel";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";

const SKILL_TO_SECTION: Record<string, Section> = {
  listening: "listening",
  speaking: "speaking",
  reading: "reading",
  writing: "writing",
  grammar: "grammar",
  pronunciation: "pronunciation",
};

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

interface HomeScreenProps {
  userId: string | null;
  profile: LearningProfile | null;
  history: ProgressHistory | null;
  userName?: string;
  onStart: (section: Section | null, step: NextBestActivity) => void;
  /** Lanza la primera actividad del plan del día (TodayPlan → [Start]). */
  onStep?: (step: SessionStep) => void;
  /** Navega a MI PROGRESO (#/progreso). */
  onOpenProgress?: () => void;
  refreshKey?: number;
}

function sectionFor(step: NextBestActivity | null): Section | null {
  if (step?.skill && SKILL_TO_SECTION[step.skill]) {
    return SKILL_TO_SECTION[step.skill];
  }
  return null;
}

/** Etiqueta de sección del panel de mando (dashboard, no tablero de stats). */
function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
      {children}
    </h2>
  );
}

/**
 * INICIO V3.1 — panel de mando de acción diaria.
 * Una única acción protagonista por tarjeta; el resto son resúmenes con
 * llamadas secundarias/compactas (reglas de zona útil, docs/UI_V3.1.md §6).
 */
export function HomeScreen({
  userId,
  profile,
  history,
  userName,
  onStart,
  onStep,
  onOpenProgress,
  refreshKey = 0,
}: HomeScreenProps) {
  const { t } = useI18n();
  const [next, setNext] = useState<NextBestActivity | null>(null);
  const [nextState, setNextState] = useState<"loading" | "error" | "done">(
    "loading",
  );
  const [nextTick, setNextTick] = useState(0);

  useEffect(() => {
    if (!userId) {
      setNext(null);
      setNextState("error");
      return;
    }
    let cancelled = false;
    setNextState("loading");
    void (async () => {
      try {
        const activity = await getNextBestActivity(userId);
        if (!cancelled) {
          setNext(activity);
          setNextState("done");
        }
      } catch {
        if (!cancelled) {
          setNext(null);
          setNextState("error");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, refreshKey, nextTick]);

  const [summary, setSummary] = useState<FsrsSummary | null>(null);
  const [fsrsState, setFsrsState] = useState<"loading" | "error" | "done">(
    "loading",
  );
  const [reviewOpen, setReviewOpen] = useState(false);
  const [fsrsTick, setFsrsTick] = useState(0);

  useEffect(() => {
    if (!userId) {
      setSummary(null);
      setFsrsState("error");
      return;
    }
    let cancelled = false;
    setFsrsState("loading");
    void (async () => {
      try {
        const data = await getFsrsSummary(userId);
        if (!cancelled) {
          setSummary(data);
          setFsrsState("done");
        }
      } catch {
        if (!cancelled) {
          setSummary(null);
          setFsrsState("error");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, refreshKey, fsrsTick]);

  /** Cierra el repaso y refresca el contador de pendientes al volver. */
  function closeReview() {
    setReviewOpen(false);
    setFsrsTick((n) => n + 1);
  }

  const level = profile?.estimated_level ?? null;
  const streak = history?.streak;

  const hour = new Date().getHours();
  const greetingKey =
    hour < 12 ? "home.morning" : hour < 20 ? "home.afternoon" : "home.evening";
  const greeting = userName
    ? `${t(greetingKey)}, ${userName}`
    : t(greetingKey);

  const visibleSkills = profile
    ? profile.skills.filter((s) => SKILL_TO_SECTION[s.skill])
    : [];

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6 lg:py-10">
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-6"
      >
        {/* 1. Cabecera de bienvenida: saludo + nivel CEFR y racha compactos. */}
        <motion.header
          variants={item}
          className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3"
        >
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            {greeting}
          </h1>
          {(level || streak) && (
            <div className="flex flex-wrap items-center gap-2">
              {level && <EstimatedLevelBadge level={level} />}
              {streak && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                  <Flame className="size-3.5" aria-hidden="true" />
                  {streak.current_days} {t("home.streak")}
                </span>
              )}
            </div>
          )}
        </motion.header>

        {/* 2. TU OBJETIVO DE HOY */}
        <motion.section variants={item} aria-label={t("home.todayGoal")}>
          <SectionHeading>{t("home.todayGoal")}</SectionHeading>
          <Card className="p-5">
            <TodayPlan
              userId={userId}
              onStep={onStep}
              refreshKey={refreshKey}
            />
          </Card>
        </motion.section>

        {/* 3. RECOMENDADO PARA TI */}
        <motion.section variants={item} aria-label={t("home.recommended")}>
          <SectionHeading>{t("home.recommended")}</SectionHeading>
          {next ? (
            <NextBestCard
              next={next}
              onStart={() => onStart(sectionFor(next), next)}
            />
          ) : nextState === "loading" ? (
            <Card
              role="status"
              aria-busy="true"
              aria-live="polite"
              className="flex items-center justify-center gap-2 p-6 text-sm text-muted-foreground"
            >
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              {t("common.loading")}
            </Card>
          ) : nextState === "error" ? (
            <Card className="flex flex-col items-center gap-2 p-6 text-center">
              <p className="text-sm text-muted-foreground">
                {t("home.unavailable")}
              </p>
              {userId && (
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => setNextTick((n) => n + 1)}
                >
                  <RefreshCw className="size-4" />
                  {t("home.retry")}
                </Button>
              )}
            </Card>
          ) : (
            <Card className="flex flex-col items-center gap-2 p-6 text-center">
              <CheckCircle2 className="size-8 text-success" aria-hidden="true" />
              <p className="text-sm text-muted-foreground">{t("home.allDone")}</p>
            </Card>
          )}
        </motion.section>

        {/* 4. REPASO (FSRS) — decisión D2: tarjeta diaria en INICIO. */}
        <motion.section variants={item} aria-label={t("fsrs.title")}>
          <Card className="gap-0 overflow-hidden">
            {reviewOpen ? (
              <>
                <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
                  <p className="text-sm font-semibold">{t("fsrs.title")}</p>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-expanded={true}
                    aria-controls="home-fsrs-panel"
                    onClick={closeReview}
                  >
                    {t("common.close")}
                  </Button>
                </div>
                <div id="home-fsrs-panel" className="p-4">
                  <FsrsReviewPanel userId={userId} />
                </div>
              </>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
                    <BookOpenCheck className="size-5" aria-hidden="true" />
                  </span>
                  <div className="min-w-0">
                    <h2 className="text-base font-semibold leading-tight">
                      {t("fsrs.title")}
                    </h2>
                    {fsrsState === "loading" && !summary && (
                      <p
                        role="status"
                        className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground"
                      >
                        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                        {t("common.loading")}
                      </p>
                    )}
                    {fsrsState === "error" && !summary && (
                      <p className="mt-0.5 text-sm text-muted-foreground">
                        {t("home.reviewUnavailable")}
                      </p>
                    )}
                    {summary &&
                      (summary.due_count > 0 ? (
                        <p className="mt-0.5 text-sm text-muted-foreground">
                          {t("fsrs.dueCount")}:{" "}
                          <span className="font-semibold tabular-nums text-foreground">
                            {summary.due_count}
                          </span>
                        </p>
                      ) : (
                        <p className="mt-0.5 text-sm text-muted-foreground">
                          {t("fsrs.empty")}
                        </p>
                      ))}
                  </div>
                </div>
                {userId &&
                  fsrsState === "done" &&
                  summary &&
                  summary.due_count > 0 && (
                    <Button
                      className="shrink-0 gap-2"
                      aria-expanded={false}
                      aria-controls="home-fsrs-panel"
                      onClick={() => setReviewOpen(true)}
                    >
                      {t("mastery.reviewNow")}
                      <ArrowRight className="size-4" aria-hidden="true" />
                    </Button>
                  )}
              </div>
            )}
          </Card>
        </motion.section>

        {/* 5. TU PROGRESO — mini-barras + acceso a MI PROGRESO. */}
        {(onOpenProgress || visibleSkills.length > 0) && (
          <motion.section variants={item} aria-label={t("home.yourProgress")}>
            <Card className="gap-4 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-base font-semibold">
                  {t("home.yourProgress")}
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
              {visibleSkills.length > 0 && (
                <div className="flex flex-col gap-4">
                  {visibleSkills.map((skill) => (
                    <SkillBar
                      key={skill.skill}
                      label={SKILL_LABELS[skill.skill] ?? skill.skill}
                      value={skill.score}
                      hint={masteryLabel(skill.score, t)}
                    />
                  ))}
                </div>
              )}
            </Card>
          </motion.section>
        )}
      </motion.div>
    </div>
  );
}

function masteryLabel(score: number, t: (k: string) => string): string {
  if (score >= 0.75) return t("mastery.strong");
  if (score >= 0.5) return t("mastery.developing");
  return t("mastery.needsPractice");
}
