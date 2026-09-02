import { useEffect, useState } from "react";
import { getNextBestActivity } from "../api/academy";
import type { NextBestActivity } from "../types/api";
import type { Section } from "../utils/sections";
import { SKILL_LABELS } from "../utils/learningLabels";
import { useI18n } from "../hooks/useI18n";
import { nextBestTitle } from "./NextBestCard";
import { Button } from "./ui/button";

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
 *
 * `fallback`: cuando el motor no tiene pasos pendientes (o el backend no
 * responde), en lugar de no renderizar nada se muestra un único CTA con
 * `label` que dispara `onClick` (p. ej. seguir practicando en la misma
 * sección), evitando que el resultado quede sin salida.
 */
export function NextStep({
  userId,
  onNext,
  fallback,
}: {
  userId: string | null;
  onNext: (section: Section | null, step: NextBestActivity) => void;
  fallback?: { label: string; onClick: () => void };
}) {
  const { t } = useI18n();
  const [next, setNext] = useState<NextBestActivity | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!userId) {
      setLoaded(true);
      return;
    }
    let cancelled = false;
    setLoaded(false);
    setNext(null);
    void (async () => {
      try {
        const activity = await getNextBestActivity(userId);
        if (!cancelled) {
          setNext(activity);
          setLoaded(true);
        }
      } catch {
        if (!cancelled) {
          setNext(null);
          setLoaded(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  if (!loaded) return null;

  if (!next) {
    if (fallback) {
      return (
        <Button
          type="button"
          className="min-h-10 gap-2"
          onClick={fallback.onClick}
        >
          {fallback.label}
        </Button>
      );
    }
    return null;
  }

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
