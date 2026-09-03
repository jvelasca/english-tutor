import { useEffect, useState } from "react";
import { AlertTriangle, ChevronDown } from "lucide-react";
import { getStudentModel } from "../../api/academy";
import { getProfile } from "../../api/learning";
import type {
  LearningProfile,
  MasteryRecord,
  SkillProfile,
  StudentModel,
} from "../../types/api";
import { SKILL_LABELS } from "../../utils/learningLabels";
import { useI18n } from "../../hooks/useI18n";
import { LearningProfile as LearningProfilePanel } from "../../components/LearningProfile";
import { EvidenceGraphPanel } from "../evidence/EvidenceGraphPanel";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { SkillBar } from "../../components/SkillBar";
import { cn } from "../../lib/utils";
import { SectionHeading, TabLoading } from "./tabBits";

interface HabilidadesTabProps {
  userId: string;
  refreshKey: number;
}

const MASTERY_TONE: Record<string, string> = {
  strong: "border-transparent bg-success/15 text-success",
  developing: "border-transparent bg-warning/15 text-warning",
  needs: "border-transparent bg-destructive/10 text-destructive",
};

function masteryClass(score: number): "strong" | "developing" | "needs" {
  if (score >= 0.75) return "strong";
  if (score >= 0.5) return "developing";
  return "needs";
}

function masteryLabel(
  score: number,
  t: (key: string) => string,
): string {
  if (score >= 0.75) return t("mastery.strong");
  if (score >= 0.5) return t("mastery.developing");
  return t("mastery.needsPractice");
}

function skillLabel(skill: string): string {
  return SKILL_LABELS[skill] ?? skill.replace(/_/g, " ");
}

/**
 * Habilidades — barras por TODAS las destrezas del Student Model con detalle
 * expansible por fila (no acordeones de secciones), hint de destreza
 * limitante (critical_skills), perfil de aprendizaje y grafo de evidencia.
 */
export function HabilidadesTab({ userId, refreshKey }: HabilidadesTabProps) {
  const { t } = useI18n();
  const [model, setModel] = useState<StudentModel | null>(null);
  const [profile, setProfile] = useState<LearningProfile | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [openSkill, setOpenSkill] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    void (async () => {
      const [m, p] = await Promise.allSettled([
        getStudentModel(userId),
        getProfile(userId),
      ]);
      if (cancelled) return;
      if (m.status === "fulfilled") setModel(m.value);
      if (p.status === "fulfilled") setProfile(p.value);
      setLoaded(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, refreshKey]);

  const skills = model?.skills ?? [];
  const masteryBySkill = new Map(
    (model?.mastery ?? []).map((m) => [m.skill, m]),
  );
  const critical = model?.critical_skills ?? [];

  if (!loaded) return <TabLoading />;

  return (
    <div className="flex flex-col gap-5">
      <section aria-label={t("progress.skillsTab")}>
        <SectionHeading>{t("progress.skillsTab")}</SectionHeading>
        <Card className="gap-3 p-5">
          <p className="text-sm text-muted-foreground">
            {t("progress.skillsHint")}
          </p>

          {skills.length === 0 ? (
            <p className="rounded-lg border border-border/60 bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
              {t("empty.noProgress")}
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {skills.map((p) => {
                const open = openSkill === p.skill;
                const mastery = masteryBySkill.get(p.skill);
                return (
                  <li
                    key={p.skill}
                    className="overflow-hidden rounded-lg border border-border/60"
                  >
                    <button
                      type="button"
                      aria-expanded={open}
                      aria-controls={`progress-skill-detail-${p.skill}`}
                      onClick={() =>
                        setOpenSkill((cur) => (cur === p.skill ? null : p.skill))
                      }
                      className="flex min-h-10 w-full items-center gap-3 rounded-lg p-3 text-left transition-colors hover:bg-accent/50"
                    >
                      <span className="min-w-0 flex-1 space-y-1">
                        <span className="flex items-center justify-between gap-2">
                          <span className="text-sm font-semibold text-foreground">
                            {skillLabel(p.skill)}
                          </span>
                          <Badge
                            className={cn(
                              "shrink-0",
                              MASTERY_TONE[masteryClass(p.score)],
                            )}
                          >
                            {masteryLabel(p.score, t)}
                          </Badge>
                        </span>
                        <SkillBar
                          value={p.score}
                          hint={`${Math.round(p.score * 100)}%`}
                        />
                      </span>
                      <ChevronDown
                        className={cn(
                          "size-4 shrink-0 text-muted-foreground transition-transform",
                          open && "rotate-180",
                        )}
                        aria-hidden="true"
                      />
                    </button>
                    {open && (
                      <div
                        id={`progress-skill-detail-${p.skill}`}
                        className="border-t border-dashed border-border p-3"
                      >
                        <SkillDetail profile={p} mastery={mastery} />
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}

          {critical.length > 0 && (
            <div
              role="note"
              className="flex flex-wrap items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning"
            >
              <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
              <span className="font-medium">{t("progress.limitingSkill")}:</span>
              <span>
                {critical.map(skillLabel).join(", ")}
              </span>
            </div>
          )}
        </Card>
      </section>

      <section aria-label={t("panels.yourProfile")}>
        <SectionHeading>{t("panels.yourProfile")}</SectionHeading>
        <Card className="gap-4 p-5">
          <LearningProfilePanel profile={profile} />
        </Card>
      </section>

      <section aria-label={t("panels.evidenceGraph")}>
        <SectionHeading>{t("panels.evidenceGraph")}</SectionHeading>
        <Card className="gap-4 p-5">
          <EvidenceGraphPanel
            userId={userId}
            levelId={model?.level_id ?? undefined}
          />
        </Card>
      </section>
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
        <DetailStat
          label={t("progress.score")}
          value={`${Math.round(profile.score * 100)}%`}
        />
        <DetailStat
          label={t("progress.confidence")}
          value={`${Math.round(profile.confidence * 100)}%`}
        />
        <DetailStat label={t("progress.evidence")} value={String(profile.evidence_count)} />
        <DetailStat
          label={t("progress.stability")}
          value={`${Math.round(profile.stability * 100)}%`}
        />
      </div>
      {mastery?.retention != null && (
        <p className="text-xs text-muted-foreground">
          {t("journey.retention")}: {Math.round(mastery.retention * 100)}%
          {mastery.review_due && reviewIn != null ? ` · ${t("mastery.reviewIn").replace("{days}", String(reviewIn))}` : ""}
        </p>
      )}
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

function DetailStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <strong className="text-base text-foreground">{value}</strong>
    </div>
  );
}
