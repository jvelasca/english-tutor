import { useEffect, useState } from "react";
import { motion, type Variants } from "motion/react";
import { AlertTriangle, MapPin, TrendingDown, TrendingUp } from "lucide-react";
import { getCefrLadder, getStudentModel } from "../../api/academy";
import { getEvents } from "../../api/learning";
import { getProgressHistory } from "../../api/progress";
import type {
  Bucket,
  CefrLadder,
  LearningEvent,
  Message,
  ProgressHistory,
  StudentModel,
} from "../../types/api";
import { SKILL_LABELS } from "../../utils/learningLabels";
import { useI18n } from "../../hooks/useI18n";
import {
  BucketToggle,
  ProgressDashboard,
} from "../../components/ProgressDashboard";
import { EstimatedLevelBadge } from "../../components/LevelBadge";
import { JourneyNode } from "../../components/JourneyNode";
import { SkillBar } from "../../components/SkillBar";
import { TriadCard } from "../../components/TriadCard";
import { TutorQualityPanel } from "../../components/TutorQualityPanel";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { cn } from "../../lib/utils";
import { SectionHeading, TabLoading } from "../progress/tabBits";

interface AnalysisScreenProps {
  userId: string | null;
  /** Turns de la sesión en curso: alimentan la calidad del tutor. */
  messages: Message[];
  refreshKey?: number;
}

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

/**
 * Análisis (V3.75.3): la evolución del alumno en su conjunto.
 *
 * Sustituye al panel flotante «Analysis» de la práctica, que en V3.1 se había
 * quedado sin analítica propia (calidad del tutor y un enlace a MI PROGRESO) y
 * se abría desde un botón dentro del ejercicio. Ahora vive en su propia ruta
 * auxiliar (`/analisis`), se abre desde la cabecera junto al usuario y **sintetiza**
 * lo que ya está medido —posición, actividad, tríada, destrezas y escalera CEFR—
 * en una sola lectura, sin duplicar las pestañas de MI PROGRESO.
 *
 * No inventa datos ni endpoints: consume `student-model`, `progress/history`,
 * `learning/events` y `cefr-ladder`, los mismos que alimentan MI PROGRESO.
 */
export function AnalysisScreen({
  userId,
  messages,
  refreshKey = 0,
}: AnalysisScreenProps) {
  const { t } = useI18n();
  const [model, setModel] = useState<StudentModel | null>(null);
  const [ladder, setLadder] = useState<CefrLadder | null>(null);
  const [history, setHistory] = useState<ProgressHistory | null>(null);
  const [events, setEvents] = useState<LearningEvent[]>([]);
  const [bucket, setBucket] = useState<Bucket>("week");
  const [positionReady, setPositionReady] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);

  // Posición y escalera: el modelo del alumno y el eje CEFR.
  useEffect(() => {
    if (!userId) {
      setModel(null);
      setLadder(null);
      setPositionReady(true);
      return;
    }
    let cancelled = false;
    setPositionReady(false);
    void (async () => {
      try {
        const [m, l] = await Promise.all([
          getStudentModel(userId),
          getCefrLadder(userId),
        ]);
        if (cancelled) return;
        setModel(m);
        setLadder(l);
      } catch {
        if (!cancelled) {
          setModel(null);
          setLadder(null);
        }
      } finally {
        if (!cancelled) setPositionReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, refreshKey]);

  // Evolución temporal: la serie real de actividad y sus hitos.
  useEffect(() => {
    if (!userId) {
      setHistory(null);
      setHistoryLoading(false);
      return;
    }
    let cancelled = false;
    setHistoryLoading(true);
    void (async () => {
      try {
        const h = await getProgressHistory(userId, bucket);
        if (!cancelled) setHistory(h);
      } catch {
        if (!cancelled) setHistory(null);
      } finally {
        if (!cancelled) setHistoryLoading(false);
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

  if (!userId) {
    return (
      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 lg:py-8">
        <Card className="p-6 text-center">
          <p className="text-sm text-muted-foreground">{t("empty.noProfile")}</p>
        </Card>
      </div>
    );
  }

  const band = model?.readiness.band ?? "developing";
  const overall = Math.round(model?.readiness.overall ?? 0);
  const skills = model?.skills ?? [];
  const critical = model?.critical_skills ?? [];
  const bands = (ladder?.bands ?? []).filter((b) => !b.id.endsWith("+"));
  const you = ladder?.estimated_band ?? model?.current_level.toLowerCase() ?? null;
  const youNumeric = ladder?.estimated_numeric ?? null;
  const hasTutorTurns = messages.some(
    (m) => m.role === "assistant" && m.content.trim().length > 0,
  );

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 lg:py-8">
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-5"
      >
        <motion.header
          variants={item}
          className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3"
        >
          <div>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
              {t("analysis.title")}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {t("analysis.subtitle")}
            </p>
          </div>
          {model && (
            <div className="flex flex-wrap items-center gap-2">
              <EstimatedLevelBadge level={model.estimated_level} />
              {model.demonstrated_level && (
                <Badge
                  variant="outline"
                  title={t("progress.certifiedTitle")}
                  className="gap-1.5"
                >
                  <span aria-hidden="true">✓</span>
                  {t("progress.certified")} {model.demonstrated_level}
                </Badge>
              )}
              <Badge variant="secondary">
                {model.target_level} · {t(`readiness.${band}`)}
              </Badge>
            </div>
          )}
        </motion.header>

        {/* Dónde estás: la lectura de posición, en una tarjeta. */}
        <motion.section variants={item} aria-label={t("analysis.position")}>
          <SectionHeading>{t("analysis.position")}</SectionHeading>
          {!positionReady ? (
            <TabLoading />
          ) : model ? (
            <Card className="gap-3 p-5">
              <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
                <p className="text-sm font-semibold text-foreground">
                  {t("progress.overall")}
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary" title={t("progress.inLevelTitle")}>
                    {Math.round(model.level_progress * 100)}%{" "}
                    {t("progress.inLevel")} {model.current_level}
                  </Badge>
                  <Badge variant="secondary">
                    {Math.round(model.confidence * 100)}% {t("analysis.confidence")}
                  </Badge>
                </div>
              </div>
              <SkillBar
                label={t("progress.overall")}
                value={overall / 100}
                hint={`${overall}%`}
              />
              {critical.length > 0 && (
                <div
                  role="note"
                  className="flex flex-wrap items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning"
                >
                  <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
                  <span className="font-medium">
                    {t("progress.limitingSkill")}:
                  </span>
                  <span>{critical.map(skillLabel).join(", ")}</span>
                </div>
              )}
            </Card>
          ) : (
            <Card className="p-6 text-center">
              <p className="text-sm text-muted-foreground">
                {t("empty.noProgress")}
              </p>
            </Card>
          )}
        </motion.section>

        {/* Evolución: la serie real de actividad, con su agrupación. */}
        <motion.section variants={item} aria-label={t("progress.activityTitle")}>
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
        </motion.section>

        {/* Las tres métricas base, coherentes con Home/Formación. */}
        <motion.section variants={item} aria-label={t("triad.progress")}>
          <SectionHeading>
            {t("triad.progress")} · {t("triad.mastery")} · {t("triad.readiness")}
          </SectionHeading>
          <TriadCard userId={userId} refreshKey={refreshKey} />
        </motion.section>

        {/* Destrezas: dónde está fuerte y hacia dónde va cada una. */}
        <motion.section variants={item} aria-label={t("progress.skillsTab")}>
          <SectionHeading>{t("progress.skillsTab")}</SectionHeading>
          <Card className="gap-4 p-5">
            {skills.length === 0 ? (
              <p className="rounded-lg border border-border/60 bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
                {t("empty.noProgress")}
              </p>
            ) : (
              <ul className="flex flex-col gap-3">
                {skills.map((p) => (
                  <li key={p.skill} className="flex flex-col gap-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-foreground">
                        {skillLabel(p.skill)}
                      </span>
                      <TrendChip trend={p.trend} />
                    </div>
                    <SkillBar value={p.score} hint={`${Math.round(p.score * 100)}%`} />
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </motion.section>

        {/* Escalera CEFR: el recorrido con «tú estás aquí». */}
        <motion.section variants={item} aria-label={t("journey.subtitle")}>
          <SectionHeading>{t("journey.subtitle")}</SectionHeading>
          <Card className="gap-5 p-5">
            {bands.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("journey.empty")}</p>
            ) : (
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
                })}
              </div>
            )}
            {ladder?.estimated_numeric != null && (
              <p className="border-t border-border/60 pt-4 text-xs text-muted-foreground">
                {t("analysis.numericHint").replace(
                  "{n}",
                  ladder.estimated_numeric.toFixed(1),
                )}
              </p>
            )}
          </Card>
        </motion.section>

        {/* Calidad del tutor: lo único que el panel retirado aportaba en vivo. */}
        {hasTutorTurns && (
          <motion.section
            variants={item}
            aria-label={t("panels.tutorQuality")}
            aria-labelledby="analysis-tutor-quality-heading"
          >
            <h2
              id="analysis-tutor-quality-heading"
              className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
            >
              {t("panels.tutorQuality")}
            </h2>
            <TutorQualityPanel messages={messages} />
          </motion.section>
        )}
      </motion.div>
    </div>
  );
}

/** Flecha de tendencia por destreza (`trend` del Student Model, V3.25). */
function TrendChip({ trend }: { trend: number | null }) {
  const { t } = useI18n();
  if (trend === null || trend === 0) {
    return (
      <span className="text-[11px] font-medium text-muted-foreground">
        {t("analysis.trendSteady")}
      </span>
    );
  }
  const up = trend > 0;
  const Icon = up ? TrendingUp : TrendingDown;
  return (
    <span
      className={cn(
        "flex items-center gap-1 text-[11px] font-medium",
        up ? "text-success" : "text-warning",
      )}
    >
      <Icon className="size-3.5 shrink-0" aria-hidden="true" />
      {t(up ? "analysis.trendUp" : "analysis.trendDown")}
    </span>
  );
}

function skillLabel(skill: string): string {
  return SKILL_LABELS[skill] ?? skill.replace(/_/g, " ");
}
