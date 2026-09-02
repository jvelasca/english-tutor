import { useState } from "react";
import type { ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  BadgeCheck,
  CalendarDays,
  ChartColumn,
  ClipboardCheck,
  Mic,
  PenLine,
  UserRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/hooks/useI18n";
import { BucketToggle, ProgressDashboard } from "@/components/ProgressDashboard";
import { TodayPlan } from "@/components/TodayPlan";
import { FsrsReviewPanel } from "@/features/review/FsrsReviewPanel";
import { LearningProfile } from "@/components/LearningProfile";
import { EvidenceGraphPanel } from "@/features/evidence/EvidenceGraphPanel";
import { TutorQualityPanel } from "@/components/TutorQualityPanel";
import { SpeakingDiagnostic } from "@/features/speaking/SpeakingDiagnostic";
import { SpeakingPanel } from "@/features/speaking/SpeakingPanel";
import { SpeakingJourney } from "@/features/speaking/SpeakingJourney";
import { SpeakingScenarios } from "@/features/speaking/SpeakingScenarios";
import { SpeakingMission } from "@/features/speaking/SpeakingMission";
import { WritingPanel } from "@/features/writing/WritingPanel";
import { WritingJourney } from "@/features/writing/WritingJourney";
import { SpeakingAssessment } from "@/features/speaking/SpeakingAssessment";
import { AssessmentLadder } from "@/features/assessment/AssessmentLadder";
import type {
  Bucket,
  LearningEvent,
  LearningProfile as LearningProfileData,
  Message,
  NextBestActivity,
  ProgressHistory,
  SessionStep,
} from "@/types/api";
import type { Section } from "@/utils/sections";

type TabId =
  | "overview"
  | "today"
  | "profile"
  | "speaking"
  | "writing"
  | "assessment"
  | "tutor";

interface TabDef {
  id: TabId;
  label: string;
  Icon: LucideIcon;
}

const TABS: TabDef[] = [
  { id: "overview", label: "panels.yourProgress", Icon: ChartColumn },
  { id: "today", label: "panels.todayPlan", Icon: CalendarDays },
  { id: "profile", label: "panels.yourProfile", Icon: UserRound },
  { id: "speaking", label: "panels.speaking", Icon: Mic },
  { id: "writing", label: "panels.writing", Icon: PenLine },
  { id: "assessment", label: "panels.speakingAssessment", Icon: ClipboardCheck },
  { id: "tutor", label: "panels.tutorQuality", Icon: BadgeCheck },
];

interface AnalysisPanelProps {
  messages: Message[];
  history: ProgressHistory | null;
  events: LearningEvent[];
  bucket: Bucket;
  onBucketChange: (bucket: Bucket) => void;
  profile: LearningProfileData | null;
  currentUserId: string | null;
  onStep: (step: SessionStep) => void;
  onAttempt: () => void;
  onNextBestStart: (section: Section | null, step: NextBestActivity) => void;
}

export function AnalysisPanel({
  messages,
  history,
  events,
  bucket,
  onBucketChange,
  profile,
  currentUserId,
  onStep,
  onAttempt,
  onNextBestStart,
}: AnalysisPanelProps) {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  function renderContent() {
    switch (activeTab) {
      case "overview":
        return (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-2">
              <SubHeader>{t("panels.yourProgress")}</SubHeader>
              <BucketToggle value={bucket} onChange={onBucketChange} />
            </div>
            <ProgressDashboard history={history} events={events} />
          </div>
        );
      case "today":
        return (
          <div className="space-y-6">
            <TodayPlan userId={currentUserId} onStep={onStep} refreshKey={0} />
            <SubSection label={t("panels.fsrsReview")}>
              <FsrsReviewPanel userId={currentUserId} />
            </SubSection>
          </div>
        );
      case "profile":
        return (
          <div className="space-y-6">
            <LearningProfile profile={profile} />
            <SubSection label={t("panels.evidenceGraph")}>
              <EvidenceGraphPanel userId={currentUserId} />
            </SubSection>
          </div>
        );
      case "speaking":
        return (
          <div className="space-y-6">
            <SubSection label={t("scenarios.title")}>
              <SpeakingScenarios userId={currentUserId} />
            </SubSection>
            <SubSection label={t("panels.speakingMission")}>
              <SpeakingMission userId={currentUserId} />
            </SubSection>
            <SubSection label={t("panels.speaking")}>
              <SpeakingDiagnostic userId={currentUserId} />
              <SpeakingPanel userId={currentUserId} />
            </SubSection>
            <SubSection label={t("panels.speakingJourney")}>
              <SpeakingJourney userId={currentUserId} />
            </SubSection>
          </div>
        );
      case "writing":
        return (
          <div className="space-y-6">
            <SubSection label={t("panels.writing")}>
              <WritingPanel userId={currentUserId} />
            </SubSection>
            <SubSection label={t("panels.writingJourney")}>
              <WritingJourney userId={currentUserId} />
            </SubSection>
          </div>
        );
      case "assessment":
        return (
          <div className="space-y-6">
            <SubSection label={t("panels.assessmentLadder")}>
              <AssessmentLadder userId={currentUserId} />
            </SubSection>
            <SubSection label={t("panels.speakingAssessment")}>
              <SpeakingAssessment
                userId={currentUserId}
                onAttempt={onAttempt}
                onNext={onNextBestStart}
              />
            </SubSection>
          </div>
        );
      case "tutor":
        return <TutorQualityPanel messages={messages} />;
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        role="tablist"
        aria-label={t("panels.analysis")}
        className="flex shrink-0 flex-wrap gap-1 border-b border-border px-2 py-1.5"
      >
        {TABS.map((tab) => {
          const selected = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`analysis-tab-${tab.id}`}
              aria-selected={selected}
              aria-controls={`analysis-panel-${tab.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "relative flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                selected
                  ? "text-primary"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {selected && (
                <motion.span
                  layoutId="analysis-tab-pill"
                  className="absolute inset-0 rounded-md bg-accent"
                  transition={{ type: "spring", stiffness: 500, damping: 40 }}
                />
              )}
              <tab.Icon
                className="relative z-10 size-4 shrink-0"
                aria-hidden="true"
              />
              <span className="relative z-10">{t(tab.label)}</span>
            </button>
          );
        })}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={activeTab}
            role="tabpanel"
            id={`analysis-panel-${activeTab}`}
            aria-labelledby={`analysis-tab-${activeTab}`}
            className="p-4"
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
          >
            {renderContent()}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

function SubSection({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <SubHeader>{label}</SubHeader>
      {children}
    </section>
  );
}

function SubHeader({ children }: { children: ReactNode }) {
  return (
    <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </h3>
  );
}
