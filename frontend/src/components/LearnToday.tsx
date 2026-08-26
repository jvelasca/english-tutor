import { useEffect, useState } from "react";
import type { ComponentType } from "react";
import {
  completeSessionStep,
  getSession,
} from "../api/academy";
import type { Session as SessionData, SessionStep } from "../types/api";
import {
  KIND_LABELS,
  SUBSKILL_LABELS,
  stepTitle,
} from "../utils/learningLabels";
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
  vocabulary: ReadingIcon,
};

interface LearnTodayProps {
  userId: string | null;
  onStep: (step: SessionStep) => void;
  refreshKey?: number;
}

/**
 * Plan de hoy como tarjetas de acción (una tarjeta = una acción), pensado para
 * la pantalla HOME. Reutiliza el Session Engine existente: `getSession` para el
 * plan del día y `completeSessionStep` para marcar pasos como hechos.
 */
export function LearnToday({ userId, onStep, refreshKey = 0 }: LearnTodayProps) {
  const [session, setSession] = useState<SessionData | null>(null);
  const [completing, setCompleting] = useState(false);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    void (async () => {
      try {
        const s = await getSession(userId);
        if (!cancelled) setSession(s);
      } catch {
        /* backend no disponible */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, refreshKey]);

  async function markDone(step: SessionStep) {
    if (!userId || completing) return;
    setCompleting(true);
    try {
      const next = await completeSessionStep(userId, step.step_key);
      setSession(next);
    } catch {
      /* backend no disponible */
    } finally {
      setCompleting(false);
    }
  }

  const items = session?.items ?? [];

  return (
    <section className="learn-today" aria-label="Plan de hoy">
      <div className="learn-today__head">
        <h2 className="learn-today__title">Today</h2>
        {session && (
          <span className="learn-today__meta">
            {session.total_minutes} min · repasa {session.review_count} · practica{" "}
            {session.practice_count}
          </span>
        )}
      </div>

      {items.length === 0 ? (
        <p className="progress-empty">
          Aún no hay plan de hoy. Practica y aquí verás tu próxima actividad.
        </p>
      ) : (
        <ul className="learn-today__grid">
          {items.map((item, i) => (
            <LearnTodayCard
              key={`${item.kind}-${item.subskill ?? item.objective_id ?? item.title}-${i}`}
              item={item}
              onStart={() => onStep(item)}
              onDone={() => markDone(item)}
              busy={completing}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function LearnTodayCard({
  item,
  onStart,
  onDone,
  busy,
}: {
  item: SessionStep;
  onStart: () => void;
  onDone: () => void;
  busy: boolean;
}) {
  const Icon = (item.skill && SKILL_ICONS[item.skill]) || SpeakingIcon;
  const kind = KIND_LABELS[item.kind] ?? item.kind;
  const reason =
    item.kind === "listening" && item.subskill
      ? SUBSKILL_LABELS[item.subskill] ?? item.subskill
      : item.reason;

  return (
    <li className="today-card">
      <div className="today-card__body">
        <span className="today-card__icon" aria-hidden="true">
          <Icon size={20} />
        </span>
        <div className="today-card__text">
          <span className="today-card__title">{stepTitle(item)}</span>
          <span className="today-card__reason">{reason}</span>
        </div>
        <span className="today-card__kind">{kind}</span>
        <span className="today-card__minutes">{item.minutes} min</span>
      </div>
      <div className="today-card__footer">
        <button
          type="button"
          className="today-card__cta"
          onClick={onStart}
          aria-label={`Empezar: ${stepTitle(item)}`}
        >
          {item.kind === "review" ? "Review" : "Start"}
        </button>
        <button
          type="button"
          className="today-card__done"
          onClick={onDone}
          disabled={busy}
          aria-label={`Marcar como hecho: ${stepTitle(item)}`}
          title="Marcar como hecho"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M20 6L9 17l-5-5" />
          </svg>
        </button>
      </div>
    </li>
  );
}
