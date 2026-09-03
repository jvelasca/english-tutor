import { ArrowRight } from "lucide-react";
import { useI18n } from "@/hooks/useI18n";
import { navigateTo } from "@/router/hash";
import { PROGRESS_PATH } from "@/router/paths";
import { TutorQualityPanel } from "@/components/TutorQualityPanel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { Message } from "@/types/api";

interface AnalysisPanelProps {
  messages: Message[];
}

/**
 * Panel "Analysis" en su versión ligera contextual (UI_V3.1 §4.5). El resto de
 * contenido experto (progreso, plan de hoy, perfil, recorridos, assessment…)
 * vive ya en MI PROGRESO e INICIO; aquí queda solo el contexto de la
 * conversación en curso — la calidad del tutor, visible en cuanto hay turns de
 * asistente — y una tarjeta discreta que abre MI PROGRESO para que el panel
 * nunca quede vacío.
 */
export function AnalysisPanel({ messages }: AnalysisPanelProps) {
  const { t } = useI18n();

  // TutorQualityPanel ya devuelve null sin turns de asistente; reflejamos el
  // mismo filtro para no dejar una cabecera de sección huérfana.
  const hasTutorTurns = messages.some(
    (m) => m.role === "assistant" && m.content.trim().length > 0,
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        {hasTutorTurns && (
          <section
            className="space-y-2"
            aria-labelledby="analysis-tutor-quality-heading"
          >
            <h2
              id="analysis-tutor-quality-heading"
              className="px-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
            >
              {t("panels.tutorQuality")}
            </h2>
            <TutorQualityPanel messages={messages} />
          </section>
        )}

        <Card className="p-3">
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-between px-3"
            onClick={() => navigateTo(PROGRESS_PATH)}
          >
            {t("home.seeProgress")}
            <ArrowRight className="size-4 shrink-0" aria-hidden="true" />
          </Button>
        </Card>
      </div>
    </div>
  );
}
