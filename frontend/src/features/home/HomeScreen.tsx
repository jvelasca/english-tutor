import { useEffect, useState } from "react";
import { motion, type Variants } from "motion/react";
import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import { getNextBestActivity } from "../../api/academy";
import type {
  LearningProfile,
  NextBestActivity,
  ProgressHistory,
} from "../../types/api";
import type { Section } from "../../utils/sections";
import { SKILL_LABELS } from "../../utils/learningLabels";
import { useI18n } from "../../hooks/useI18n";
import { NextBestCard } from "../../components/NextBestCard";
import { LevelBadge } from "../../components/LevelBadge";
import { SkillBar } from "../../components/SkillBar";
import { Card } from "../../components/ui/card";
import { cn } from "../../lib/utils";

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
  refreshKey?: number;
}

function sectionFor(step: NextBestActivity | null): Section | null {
  if (step?.skill && SKILL_TO_SECTION[step.skill]) {
    return SKILL_TO_SECTION[step.skill];
  }
  return null;
}

export function HomeScreen({
  userId,
  profile,
  history,
  userName,
  onStart,
  refreshKey = 0,
}: HomeScreenProps) {
  const { t } = useI18n();
  const [next, setNext] = useState<NextBestActivity | null>(null);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    void (async () => {
      try {
        const activity = await getNextBestActivity(userId);
        if (!cancelled) setNext(activity);
      } catch {
        /* backend no disponible */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, refreshKey]);

  const level = profile?.estimated_level ?? null;
  const readiness = Math.round(profile?.readiness.overall ?? 0);
  const trend = profile ? overallTrend(profile) : null;
  const nextFocus = profile?.readiness.blocking_skills[0] ?? null;

  const streak = history?.streak;
  const activityTotal = history
    ? history.series.reduce(
        (acc, p) =>
          acc + p.messages + p.exercises + p.corrections + p.pronunciation,
        0,
      )
    : 0;

  const hour = new Date().getHours();
  const greetingKey =
    hour < 12 ? "home.morning" : hour < 20 ? "home.afternoon" : "home.evening";
  const greeting = userName
    ? `${t(greetingKey)}, ${userName}`
    : t(greetingKey);

  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  const trendLabel =
    trend === "up"
      ? t("home.improving")
      : trend === "down"
        ? t("home.needsReview")
        : t("home.stable");
  const trendClass =
    trend === "up"
      ? "text-success"
      : trend === "down"
        ? "text-destructive"
        : "text-muted-foreground";

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
            {greeting}
          </h1>
          <p className="mt-1 text-muted-foreground">{t("home.subtitle")}</p>
        </motion.header>

        <motion.section variants={item} aria-label={t("home.yourProgress")}>
          <Card className="gap-5 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <LevelBadge level={level ?? "—"} showLabel={Boolean(level)} />
              {trend && (
                <span
                  className={cn(
                    "inline-flex items-center gap-1.5 text-sm font-medium",
                    trendClass,
                  )}
                >
                  <TrendIcon className="size-4" />
                  {trendLabel}
                </span>
              )}
            </div>
            <div>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="text-muted-foreground">
                  {t("home.readyFor")} {profile?.target_level ?? "…"}
                </span>
                <span className="text-lg font-bold tabular-nums">
                  {readiness}%
                </span>
              </div>
              <div className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-primary/15">
                <motion.div
                  className="h-full rounded-full bg-primary"
                  initial={{ width: 0 }}
                  animate={{ width: `${readiness}%` }}
                  transition={{
                    duration: 0.9,
                    ease: [0.22, 1, 0.36, 1],
                    delay: 0.2,
                  }}
                />
              </div>
            </div>
            {nextFocus && (
              <p className="text-sm text-muted-foreground">
                {t("home.nextFocus")}:{" "}
                <span className="font-medium text-foreground">
                  {SKILL_LABELS[nextFocus] ?? nextFocus}
                </span>
              </p>
            )}
          </Card>
        </motion.section>

        <motion.section variants={item} aria-label={t("home.nextStep")}>
          {next ? (
            <NextBestCard next={next} onStart={() => onStart(sectionFor(next), next)} />
          ) : (
            <Card className="p-5">
              <p className="text-center text-sm text-muted-foreground">
                {t("home.allDone")}
              </p>
            </Card>
          )}
        </motion.section>

        {profile && profile.skills.length > 0 && (
          <motion.section variants={item} aria-label={t("home.yourSkills")}>
            <Card className="gap-4 p-5">
              <h2 className="text-base font-semibold">{t("home.yourSkills")}</h2>
              <div className="flex flex-col gap-4">
                {profile.skills
                  .filter((s) => SKILL_TO_SECTION[s.skill])
                  .map((skill) => (
                    <SkillBar
                      key={skill.skill}
                      label={SKILL_LABELS[skill.skill] ?? skill.skill}
                      value={skill.score}
                      hint={masteryLabel(skill.score, t)}
                    />
                  ))}
              </div>
            </Card>
          </motion.section>
        )}

        {streak && (
          <motion.section variants={item}>
            <Card className="gap-0 p-0">
              <div className="grid grid-cols-3 divide-x divide-border">
                <Stat value={streak.current_days} label={t("home.streak")} />
                <Stat value={streak.best_days} label={t("home.bestStreak")} />
                <Stat value={activityTotal} label={t("home.activity")} />
              </div>
            </Card>
          </motion.section>
        )}
      </motion.div>
    </div>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex flex-col items-center gap-1 px-3 py-4">
      <span className="text-2xl font-bold tabular-nums">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

function masteryLabel(score: number, t: (k: string) => string): string {
  if (score >= 0.75) return t("mastery.strong");
  if (score >= 0.5) return t("mastery.developing");
  return t("mastery.needsPractice");
}

function overallTrend(profile: LearningProfile): "up" | "down" | "flat" | null {
  const trends = profile.skills
    .map((s) => s.trend)
    .filter((t): t is number => t !== null);
  if (trends.length === 0) return null;
  const sum = trends.reduce((a, b) => a + b, 0);
  if (sum > 0.5) return "up";
  if (sum < -0.5) return "down";
  return "flat";
}
