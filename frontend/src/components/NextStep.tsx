import { useEffect, useState } from "react";
import { getNextBestActivity } from "../api/academy";
import type { NextBestActivity } from "../types/api";
import type { Section } from "../utils/sections";
import { SKILL_LABELS } from "../utils/learningLabels";
import { useI18n } from "../hooks/useI18n";
import { nextBestTitle } from "./NextBestCard";

const SKILL_TO_SECTION: Record<string, Section> = {
  listening: "listening",
  speaking: "speaking",
  reading: "reading",
  writing: "writing",
  grammar: "grammar",
  pronunciation: "pronunciation",
};

/**
 * Pie "Next" compartido del bucle Activity → Result → Feedback → Next.
 * Consulta el Adaptive Engine (`/api/academy/next-best`) y muestra una única
 * acción dominante con un CTA "Continuar"; el frontend no decide pedagogía.
 */
export function NextStep({
  userId,
  onNext,
}: {
  userId: string | null;
  onNext: (section: Section | null, step: NextBestActivity) => void;
}) {
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
  }, [userId]);

  if (!next) return null;

  const section = next.skill ? SKILL_TO_SECTION[next.skill] : null;

  return (
    <div className="next-step">
      <span className="next-step__label">{t("home.nextStep")}</span>
      <div className="next-step__row">
        <span className="next-step__skill">
          {next.skill ? SKILL_LABELS[next.skill] ?? next.skill : ""}
        </span>
        <span className="next-step__title">{nextBestTitle(next)}</span>
        <span className="next-step__meta">
          {t(`reason.${next.reason}`)} · {next.minutes} {t("home.min")}
        </span>
        <button
          type="button"
          className="next-step__cta"
          onClick={() => onNext(section, next)}
        >
          {t("home.continue")}
        </button>
      </div>
    </div>
  );
}
