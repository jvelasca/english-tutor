import { useEffect, useState } from "react";
import type { ComponentType, ReactNode, SVGProps } from "react";
import { motion, type Variants } from "motion/react";
import { ArrowRight, BookOpen, CheckCircle2, Loader2, MessageSquareText, RefreshCw } from "lucide-react";
import {
  GrammarIcon,
  ListeningIcon,
  PronunciationIcon,
  SpeakingIcon,
} from "../../components/Icons";
import { NextBestCard } from "../../components/NextBestCard";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { getNextBestActivity } from "../../api/academy";
import type { NextBestActivity } from "../../types/api";
import type { Section } from "../../utils/sections";
import { useI18n } from "../../hooks/useI18n";
import { cn } from "../../lib/utils";
import { navigateTo } from "../../router/hash";
import { learnActivityPath } from "../../router/paths";
import {
  CONVERSATION_ACTIVITY,
  GRAMMAR_ACTIVITY,
  LISTENING_ACTIVITY,
  PRONUNCIATION_ACTIVITY,
  SPEAKING_ACTIVITY,
  VOCABULARY_ACTIVITY,
  type LearnActivity,
} from "../../router/learnHub";

type IconType = ComponentType<{ size?: number; className?: string } & SVGProps<SVGSVGElement>>;

interface ActivityDef {
  id: LearnActivity;
  titleKey: string;
  descKey: string;
  Icon: IconType;
}

const ACTIVITIES: ActivityDef[] = [
  { id: LISTENING_ACTIVITY, titleKey: "skill.listening", descKey: "learn.desc.listening", Icon: ListeningIcon },
  { id: SPEAKING_ACTIVITY, titleKey: "skill.speaking", descKey: "learn.desc.speaking", Icon: SpeakingIcon },
  { id: PRONUNCIATION_ACTIVITY, titleKey: "skill.pronunciation", descKey: "learn.desc.pronunciation", Icon: PronunciationIcon },
  { id: CONVERSATION_ACTIVITY, titleKey: "learn.conversation", descKey: "learn.desc.conversation", Icon: MessageSquareText },
  { id: VOCABULARY_ACTIVITY, titleKey: "skill.vocabulary", descKey: "learn.desc.vocabulary", Icon: BookOpen },
  { id: GRAMMAR_ACTIVITY, titleKey: "skill.grammar", descKey: "learn.desc.grammar", Icon: GrammarIcon },
];

// Destrezas que el motor adaptativo puede sugerir, mapeadas a sección del
// workspace para lanzar el paso desde "Recomendado para ti".
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
  show: { transition: { staggerChildren: 0.06 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] } },
};

function sectionFor(step: NextBestActivity | null): Section | null {
  if (step?.skill && SKILL_TO_SECTION[step.skill]) {
    return SKILL_TO_SECTION[step.skill];
  }
  return null;
}

function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-3 px-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
      {children}
    </h2>
  );
}

/**
 * Tarjeta grande del hub de APRENDER (decisión D3). Toda la tarjeta es un
 * botón: el tap target supera 44px y navega a la sub-ruta canónica de la
 * actividad (`#/aprender/<id>`).
 */
function ActivityCard({
  activity,
  onOpen,
}: {
  activity: ActivityDef;
  onOpen: (id: LearnActivity) => void;
}) {
  const { t } = useI18n();
  const Icon = activity.Icon;
  return (
    <motion.div variants={item} className="h-full">
      <button
        type="button"
        onClick={() => onOpen(activity.id)}
        aria-label={`${t("learn.activityAria")}: ${t(activity.titleKey)}`}
        className={cn(
          "group flex h-full min-h-[132px] w-full flex-col items-start gap-3 rounded-2xl border border-border bg-card p-5 text-left shadow-sm",
          "transition-colors hover:border-primary/40 hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
          "active:scale-[0.995]",
        )}
      >
        <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary transition-colors group-hover:bg-primary/15">
          <Icon size={24} className="size-6" />
        </span>
        <span className="flex w-full items-baseline justify-between gap-2">
          <span className="text-base font-bold tracking-tight text-foreground">
            {t(activity.titleKey)}
          </span>
          <ArrowRight
            className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
            aria-hidden="true"
          />
        </span>
        <span className="text-sm leading-relaxed text-muted-foreground">
          {t(activity.descKey)}
        </span>
      </button>
    </motion.div>
  );
}

interface LearnHubProps {
  userId: string | null;
  /** Lanza la actividad recomendada por el Adaptive Engine (plan/next-best). */
  onStart: (section: Section | null, step: NextBestActivity) => void;
  refreshKey?: number;
}

/**
 * Hub de APRENDER (decisión D1/D3): cabecera del mundo + 6 tarjetas de
 * práctica libre (3x2 en escritorio, lista en móvil) + "Recomendado para ti"
 * servido por el Adaptive Engine. Cada tarjeta abre su sub-ruta de práctica;
 * aquí no existe gating (docs/UI_V3.1.md §4.3).
 */
export function LearnHub({ userId, onStart, refreshKey = 0 }: LearnHubProps) {
  const { t } = useI18n();
  const [next, setNext] = useState<NextBestActivity | null>(null);
  const [nextState, setNextState] = useState<"loading" | "error" | "done">("loading");
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

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 lg:py-10">
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-8"
      >
        <motion.header variants={item}>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            {t("learn.title")}
          </h1>
          <p className="mt-1.5 text-muted-foreground">{t("learn.subtitle")}</p>
        </motion.header>

        <motion.section variants={item} aria-labelledby="learn-hub-grid-title">
          <SectionHeading>{t("learn.pickActivity")}</SectionHeading>
          <ul className="grid list-none grid-cols-1 gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">
            {ACTIVITIES.map((activity) => (
              <li key={activity.id} className="flex">
                <ActivityCard activity={activity} onOpen={openLearnActivity} />
              </li>
            ))}
          </ul>
        </motion.section>

        <motion.section variants={item} aria-label={t("learn.recommended")}>
          <SectionHeading>{t("learn.recommended")}</SectionHeading>
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
              <p className="text-sm text-muted-foreground">{t("home.unavailable")}</p>
              {userId && (
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => setNextTick((n) => n + 1)}
                >
                  <RefreshCw className="size-4" aria-hidden="true" />
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
      </motion.div>
    </div>
  );
}

function openLearnActivity(id: LearnActivity): void {
  navigateTo(learnActivityPath(id));
}
