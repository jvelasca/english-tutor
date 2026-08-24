import type { Message } from "../types/api";
import { averageEvaluations, evaluateTutorReply } from "../utils/tutorEvaluation";

interface TutorQualityPanelProps {
  messages: Message[];
}

export function TutorQualityPanel({ messages }: TutorQualityPanelProps) {
  const assistantTurns = messages
    .filter((m) => m.role === "assistant" && m.content.trim().length > 0)
    .map((m) => m.content);

  if (assistantTurns.length === 0) {
    return null;
  }

  const average = averageEvaluations(
    assistantTurns.map(evaluateTutorReply),
  );

  const recentTurns = assistantTurns
    .slice(-3)
    .reverse()
    .map((reply) => ({ reply, evaluation: evaluateTutorReply(reply) }));

  const chips = [
    { label: "Total", value: average.total },
    { label: "Inglés", value: average.english },
    { label: "Concisión", value: average.conciseness },
    { label: "Engagement", value: average.engagement },
  ];

  return (
    <section className="tutor-quality" aria-label="Calidad del tutor">
      <h3 className="tutor-quality-title">Calidad del tutor</h3>

      <div className="tutor-quality-stats" role="status" aria-live="polite">
        {chips.map((chip) => (
          <div key={chip.label} className="stat-chip">
            <span className="stat-chip-value">
              {chip.value === null ? "—" : chip.value}
            </span>
            <span className="stat-chip-label">{chip.label}</span>
          </div>
        ))}
      </div>

      <ul className="tutor-turns">
        {recentTurns.map(({ reply, evaluation }) => (
          <li key={reply} className="tutor-turn">
            <span className="tutor-turn-total">{evaluation.total}</span>
            <span className="tutor-turn-summary">
              Inglés {evaluation.english} · Concisión {evaluation.conciseness} ·
              Engagement {evaluation.engagement}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
