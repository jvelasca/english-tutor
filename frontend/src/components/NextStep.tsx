import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
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

// Máxima espera por la recomendación del Adaptive Engine. Si el endpoint no
// responde (backend ocupado o conexión caída, p. ej. iPad por WiFi), se muestra
// igualmente el CTA de salida (fallback) para que el resultado nunca se quede
// sin botón "Continuar".
const NEXT_BEST_TIMEOUT_MS = 8000;

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
    // `settled` garantiza que solo la primera respuesta (fetch o timeout) pinta
    // el pie: si el endpoint se cuelga, el timeout muestra el CTA de salida y la
    // resolución tardía del fetch se descarta.
    let settled = false;
    setLoaded(false);
    setNext(null);
    const timer = setTimeout(() => {
      if (!cancelled && !settled) {
        settled = true;
        setNext(null);
        setLoaded(true);
      }
    }, NEXT_BEST_TIMEOUT_MS);
    void (async () => {
      try {
        const activity = await getNextBestActivity(userId);
        if (!cancelled && !settled) {
          settled = true;
          clearTimeout(timer);
          setNext(activity);
          setLoaded(true);
        }
      } catch {
        if (!cancelled && !settled) {
          settled = true;
          clearTimeout(timer);
          setNext(null);
          setLoaded(true);
        }
      }
    })();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [userId]);

  if (!loaded) {
    // Mientras el Adaptive Engine calcula, se muestra un placeholder visible:
    // nunca un vacío que parezca un fallo (el resultado nunca se queda sin pie).
    return (
      <div className="next-step">
        <span className="next-step__label">{t("home.nextStep")}</span>
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          {t("common.loading")}
        </p>
      </div>
    );
  }

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
