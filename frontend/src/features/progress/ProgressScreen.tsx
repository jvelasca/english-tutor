import { useEffect, useState } from "react";
import { motion, type Variants } from "motion/react";
import { ChevronDown } from "lucide-react";
import { getStudentModel } from "../../api/academy";
import type {
  MasteryRecord,
  SkillProfile,
  StudentModel,
} from "../../types/api";
import { SKILL_LABELS } from "../../utils/learningLabels";
import { useI18n } from "../../hooks/useI18n";
import { SpeakingDiagnostic } from "../speaking/SpeakingDiagnostic";
import { WritingJourney } from "../writing/WritingJourney";
import { LevelBadge } from "../../components/LevelBadge";
import { SkillBar } from "../../components/SkillBar";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { Progress } from "../../components/ui/progress";
import { cn } from "../../lib/utils";

const PRIMARY = ["listening", "speaking", "reading", "writing"] as const;
type PrimarySkill = (typeof PRIMARY)[number];

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
  },
};

const MASTERY_TONE: Record<string, string> = {
  strong: "border-transparent bg-success/15 text-success",
  developing: "border-transparent bg-warning/15 text-warning",
  needs: "border-transparent bg-destructive/10 text-destructive",
};

interface ProgressScreenProps {
  userId: string | null;
}

function masteryLabel(score: number, t: (k: string) => string): string {
  if (score >= 0.75) return t("mastery.strong");
  if (score >= 0.5) return t("mastery.developing");
  return t("mastery.needsPractice");
}

function masteryClass(score: number): string {
  if (score >= 0.75) return "strong";
  if (score >= 0.5) return "developing";
  return "needs";
}

export function ProgressScreen({ userId }: ProgressScreenProps) {
  const { t } = useI18n();
  const [model, setModel] = useState<StudentModel | null>(null);
  const [selected, setSelected] = useState<PrimarySkill | null>(null);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    void (async () => {
      try {
        const m = await getStudentModel(userId);
        if (!cancelled) setModel(m);
      } catch {
        /* backend no disponible */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const level = model?.estimated_level ?? null;
  const overall = Math.round(model?.readiness.overall ?? 0);
  const band = model?.readiness.band ?? "developing";

  const skills = model?.skills ?? [];
  const bySkill = new Map(skills.map((s) => [s.skill, s]));
  const masteryBySkill = new Map(
    (model?.mastery ?? []).map((m) => [m.skill, m]),
  );

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-5"
      >
        <motion.header
          variants={item}
          className="flex flex-wrap items-center justify-between gap-3"
        >
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            {t("progress.title")}
          </h1>
          <div className="flex items-center gap-2">
            <LevelBadge level={level ?? "—"} showLabel={Boolean(level)} />
            {model && (
              <Badge variant="secondary" className="gap-1.5">
                {model.target_level} · {t(`readiness.${band}`)}
              </Badge>
            )}
          </div>
        </motion.header>

        <motion.section variants={item} aria-label={t("progress.overall")}>
          <Card className="gap-2 p-5">
            <SkillBar
              label={t("progress.overall")}
              value={overall / 100}
              hint={`${overall}%`}
            />
          </Card>
        </motion.section>

        <motion.section variants={item} aria-label={t("progress.title")}>
          <Card className="gap-2 p-3 sm:p-4">
            <ul className="flex flex-col gap-2">
              {PRIMARY.map((skill) => {
                const p = bySkill.get(skill);
                if (!p) return null;
                const open = selected === skill;
                return (
                  <li
                    key={skill}
                    className="overflow-hidden rounded-lg border border-border/60"
                  >
                    <button
                      type="button"
                      className="flex min-h-10 w-full items-center gap-3 rounded-lg p-3 text-left transition-colors hover:bg-accent/50"
                      onClick={() =>
                        setSelected((cur) => (cur === skill ? null : skill))
                      }
                      aria-expanded={open}
                    >
                      <span className="min-w-0 flex-1 text-sm font-semibold text-foreground">
                        {SKILL_LABELS[skill] ?? skill}
                      </span>
                      <Badge
                        className={cn(
                          "shrink-0",
                          MASTERY_TONE[masteryClass(p.score)],
                        )}
                      >
                        {masteryLabel(p.score, t)}
                      </Badge>
                      <Progress
                        value={Math.round(p.score * 100)}
                        className="hidden h-1.5 w-24 sm:block"
                      />
                      <ChevronDown
                        className={cn(
                          "size-4 shrink-0 text-muted-foreground transition-transform",
                          open && "rotate-180",
                        )}
                        aria-hidden="true"
                      />
                    </button>

                    {open && (
                      <div className="border-t border-dashed border-border p-3">
                        {skill === "speaking" ? (
                          <SpeakingDiagnostic userId={userId} />
                        ) : skill === "writing" ? (
                          <WritingJourney userId={userId} />
                        ) : (
                          <SkillDetail
                            profile={p}
                            mastery={masteryBySkill.get(skill)}
                          />
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </Card>
        </motion.section>
      </motion.div>
    </div>
  );
}

function SkillDetail({
  profile,
  mastery,
}: {
  profile: SkillProfile;
  mastery?: MasteryRecord;
}) {
  const { t } = useI18n();
  const reviewIn = mastery?.review_due ? mastery.review_in_days : null;
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-muted-foreground">
            {t("progress.score")}
          </span>
          <strong className="text-base text-foreground">
            {Math.round(profile.score * 100)}%
          </strong>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-muted-foreground">
            {t("progress.confidence")}
          </span>
          <strong className="text-base text-foreground">
            {Math.round(profile.confidence * 100)}%
          </strong>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-muted-foreground">
            {t("progress.evidence")}
          </span>
          <strong className="text-base text-foreground">
            {profile.evidence_count}
          </strong>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-muted-foreground">
            {t("progress.stability")}
          </span>
          <strong className="text-base text-foreground">
            {Math.round(profile.stability * 100)}%
          </strong>
        </div>
      </div>
      {profile.review_due && (
        <Badge className="w-fit border-transparent bg-warning/15 text-warning">
          {reviewIn != null && reviewIn > 1
            ? t("mastery.reviewIn").replace("{days}", String(reviewIn))
            : t("mastery.reviewNow")}
        </Badge>
      )}
    </div>
  );
}
