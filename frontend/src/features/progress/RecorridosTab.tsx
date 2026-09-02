import { useState } from "react";
import type { ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ClipboardCheck, Headphones, Mic, PenLine } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useI18n } from "../../hooks/useI18n";
import { navigateTo } from "../../router/hash";
import { learnActivityPath } from "../../router/paths";
import { CONVERSATION_ACTIVITY } from "../../router/learnHub";
import { SpeakingPanel } from "../speaking/SpeakingPanel";
import { SpeakingJourney } from "../speaking/SpeakingJourney";
import { SpeakingDiagnostic } from "../speaking/SpeakingDiagnostic";
import { SpeakingAssessment } from "../speaking/SpeakingAssessment";
import { WritingPanel } from "../writing/WritingPanel";
import { WritingJourney } from "../writing/WritingJourney";
import { AssessmentLadder } from "../assessment/AssessmentLadder";
import { ListeningRecorridoPanel } from "../listening/ListeningRecorridoPanel";
import { SectionHeading } from "./tabBits";
import { cn } from "../../lib/utils";

interface RecorridosTabProps {
  userId: string;
  refreshKey: number;
}

type TrackId = "listening" | "speaking" | "writing" | "assessment";

interface TrackDef {
  id: TrackId;
  labelKey: string;
  Icon: LucideIcon;
}

const TRACKS: TrackDef[] = [
  { id: "listening", labelKey: "skill.listening", Icon: Headphones },
  { id: "speaking", labelKey: "skill.speaking", Icon: Mic },
  { id: "writing", labelKey: "skill.writing", Icon: PenLine },
  { id: "assessment", labelKey: "progress.assessmentTab", Icon: ClipboardCheck },
];

/**
 * Recorridos — sub-pestañas Listening / Speaking / Writing / Assessment.
 * Misma semántica aria que el tablist principal (premisa #19: pestañas, nunca
 * acordeones) reutilizando los paneles expertos que vivían en el workspace.
 */
export function RecorridosTab({ userId }: RecorridosTabProps) {
  const { t } = useI18n();
  const [track, setTrack] = useState<TrackId>("listening");

  // Tras un Speaking Assessment el siguiente paso recomendado no puede arrancar
  // una práctica desde MI PROGRESO (no hay workspace): se lleva al mundo
  // Aprender → Conversar, la práctica conversacional libre.
  const handleAssessmentNext = () =>
    navigateTo(learnActivityPath(CONVERSATION_ACTIVITY));

  let content: ReactNode = null;
  if (track === "listening") {
    content = <ListeningRecorridoPanel userId={userId} />;
  } else if (track === "speaking") {
    content = (
      <div className="flex flex-col gap-4">
        <section aria-label={t("panels.speaking")}>
          <SectionHeading>{t("panels.speaking")}</SectionHeading>
          <div className="flex flex-col gap-4">
            <SpeakingDiagnostic userId={userId} />
            <SpeakingPanel userId={userId} />
          </div>
        </section>
        <section aria-label={t("panels.speakingJourney")}>
          <SectionHeading>{t("panels.speakingJourney")}</SectionHeading>
          <SpeakingJourney userId={userId} />
        </section>
      </div>
    );
  } else if (track === "writing") {
    content = (
      <div className="flex flex-col gap-4">
        <section aria-label={t("panels.writing")}>
          <SectionHeading>{t("panels.writing")}</SectionHeading>
          <WritingPanel userId={userId} />
        </section>
        <section aria-label={t("panels.writingJourney")}>
          <SectionHeading>{t("panels.writingJourney")}</SectionHeading>
          <WritingJourney userId={userId} />
        </section>
      </div>
    );
  } else {
    content = (
      <div className="flex flex-col gap-4">
        <section aria-label={t("panels.assessmentLadder")}>
          <SectionHeading>{t("panels.assessmentLadder")}</SectionHeading>
          <AssessmentLadder userId={userId} />
        </section>
        <section aria-label={t("panels.speakingAssessment")}>
          <SectionHeading>{t("panels.speakingAssessment")}</SectionHeading>
          <SpeakingAssessment
            userId={userId}
            onAttempt={() => {}}
            onNext={handleAssessmentNext}
          />
        </section>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        {t("progress.tracksIntro")}
      </p>
      <div
        role="tablist"
        aria-label={t("progress.tracksTab")}
        className="flex gap-1 overflow-x-auto rounded-xl border border-border bg-card p-1 shadow-sm"
      >
        {TRACKS.map((item) => {
          const selected = track === item.id;
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              id={`progress-track-tab-${item.id}`}
              aria-selected={selected}
              aria-controls={`progress-track-panel-${item.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => setTrack(item.id)}
              className={cn(
                "relative flex min-h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg px-3.5 py-2 text-sm font-medium transition-colors sm:px-4",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                selected
                  ? "text-primary"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {selected && (
                <motion.span
                  layoutId="progress-track-tab-pill"
                  className="absolute inset-0 rounded-lg bg-accent"
                  transition={{
                    type: "spring",
                    stiffness: 500,
                    damping: 40,
                  }}
                />
              )}
              <item.Icon
                className="relative z-10 size-4 shrink-0"
                aria-hidden="true"
              />
              <span className="relative z-10">{t(item.labelKey)}</span>
            </button>
          );
        })}
      </div>

      <div
        role="tabpanel"
        id={`progress-track-panel-${track}`}
        aria-labelledby={`progress-track-tab-${track}`}
      >
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={track}
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
          >
            {content}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
