import type { ComponentType } from "react";
import type { NextBestActivity } from "../types/api";
import { SKILL_LABELS, SUBSKILL_LABELS } from "../utils/learningLabels";
import { useI18n } from "../hooks/useI18n";
import { ArrowRight } from "lucide-react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import {
  GrammarIcon,
  ListeningIcon,
  PronunciationIcon,
  ReadingIcon,
  SpeakingIcon,
  WritingIcon,
} from "./Icons";

const SKILL_ICONS: Record<string, ComponentType<{ size?: number }>> = {
  listening: ListeningIcon,
  speaking: SpeakingIcon,
  reading: ReadingIcon,
  writing: WritingIcon,
  grammar: GrammarIcon,
  pronunciation: PronunciationIcon,
};

export function nextBestTitle(next: NextBestActivity): string {
  if (next.kind === "listening" && next.subskill) {
    return SUBSKILL_LABELS[next.subskill] ?? next.subskill;
  }
  return next.title;
}

/**
 * Tarjeta compartida "Siguiente mejor actividad" (Learning UX 2.0). Es la
 * acción protagonista del bucle Activity → Result → Feedback → Next: una única
 * acción dominante derivada del Adaptive Engine, con su CTA.
 */
export function NextBestCard({
  next,
  onStart,
}: {
  next: NextBestActivity;
  onStart: () => void;
}) {
  const { t } = useI18n();
  const Icon = next.skill ? SKILL_ICONS[next.skill] : undefined;
  const skillLabel = next.skill ? (SKILL_LABELS[next.skill] ?? next.skill) : "";

  return (
    <Card className="gap-0 overflow-hidden border-primary/25 bg-gradient-to-br from-primary/10 to-card p-0">
      <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:gap-6">
        {Icon && (
          <span className="grid size-14 shrink-0 place-items-center rounded-2xl bg-primary/15 text-primary">
            <Icon size={28} />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("home.nextStep")}
          </p>
          <h3 className="mt-1 truncate text-lg font-bold text-foreground">
            {skillLabel && <span>{skillLabel} · </span>}
            {nextBestTitle(next)}
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {t(`reason.${next.reason}`)} · {next.minutes} {t("home.min")}
          </p>
          {next.why && (
            <p className="mt-2 text-sm text-foreground/90">
              <span className="font-semibold">
                {t("home.whyThisActivity")}
              </span>{" "}
              {next.why}
            </p>
          )}
          {next.because && next.because.length > 0 && (
            <div className="mt-2 text-sm text-foreground/90">
              <p className="font-semibold">{t("home.because")}</p>
              <ol className="mt-1 list-decimal space-y-0.5 pl-4 text-muted-foreground">
                {next.because.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ol>
              {next.limiting_factor && (
                <p className="mt-1 text-xs">
                  {t("home.limitingFactor")}:{" "}
                  <span className="font-medium text-foreground">
                    {next.limiting_factor.id}
                    {next.limiting_factor.missing
                      ? ` (${t("home.missing")})`
                      : ` · ${Math.round(next.limiting_factor.score * 100)}%`}
                  </span>
                </p>
              )}
            </div>
          )}
        </div>
        <Button size="lg" className="shrink-0 gap-2" onClick={onStart}>
          {t("home.continue")}
          <ArrowRight className="size-4" />
        </Button>
      </div>
    </Card>
  );
}
