import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { useI18n } from "../../hooks/useI18n";
import { Button } from "../../components/ui/button";
import { LearnActivitySwitcher } from "../../components/LearnActivitySwitcher";
import type { LearnActivity } from "../../router/learnHub";
import { SpeakingScenarios } from "./SpeakingScenarios";
import { SpeakingMission } from "./SpeakingMission";

function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-sm font-bold tracking-tight text-foreground">
      {children}
    </h2>
  );
}

interface SpeakingFreePracticeProps {
  userId: string | null;
  /** Actividad activa (Speaking) para el atajo de la franja superior. */
  active: LearnActivity;
  /** Navega de vuelta al hub de APRENDER (`#/aprender`). */
  onBack: () => void;
}

/**
 * Tarjeta "Speaking" del hub de APRENDER: práctica oral libre que monta el
 * catálogo de escenarios comunicativos y el loop de misiones en una sola
 * pantalla con scroll. No depende del workspace conversacional: cada bloque
 * gestiona sus propios estados y fetches (`props: { userId }`).
 */
export function SpeakingFreePractice({
  userId,
  active,
  onBack,
}: SpeakingFreePracticeProps) {
  const { t } = useI18n();
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center gap-2 border-b border-border bg-background/90 px-2 py-1.5 backdrop-blur">
        <Button
          variant="ghost"
          size="sm"
          className="min-h-9 shrink-0 gap-1 px-2 text-sm font-medium"
          onClick={onBack}
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          {t("learn.back")}
        </Button>
        <LearnActivitySwitcher active={active} />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
          <header className="mb-6">
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
              {t("skill.speaking")}
            </h1>
            <p className="mt-1.5 text-muted-foreground">
              {t("learn.speakingSubtitle")}
            </p>
          </header>

          <div className="flex flex-col gap-8">
            <section className="flex flex-col gap-3" aria-labelledby="speaking-scenarios-title">
              <h2 id="speaking-scenarios-title">
                <SectionHeading>{t("scenarios.title")}</SectionHeading>
              </h2>
              <SpeakingScenarios userId={userId} />
            </section>

            <section className="flex flex-col gap-3" aria-labelledby="speaking-missions-title">
              <h2 id="speaking-missions-title">
                <SectionHeading>{t("panels.speakingMission")}</SectionHeading>
              </h2>
              <SpeakingMission userId={userId} />
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
