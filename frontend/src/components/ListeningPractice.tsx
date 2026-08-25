import { useEffect, useState } from "react";
import {
  getListeningDiagnostic,
  getListeningQuestion,
  getListeningStats,
  submitListeningAnswer,
} from "../api/listening";
import { speak } from "../api/voz";
import type {
  ListeningAnswerResponse,
  ListeningDiagnostic,
  ListeningQuestion,
  ListeningStats,
} from "../types/api";

function topicLabel(topic: string): string {
  return topic.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function trendLabel(direction: string): string {
  switch (direction) {
    case "up":
      return "mejorando";
    case "down":
      return "empeorando";
    case "flat":
      return "estable";
    default:
      return "—";
  }
}

interface ListeningPracticeProps {
  userId: string | null;
  onAttempt: () => void;
}

export function ListeningPractice({
  userId,
  onAttempt,
}: ListeningPracticeProps) {
  const [question, setQuestion] = useState<ListeningQuestion | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [result, setResult] = useState<ListeningAnswerResponse | null>(null);
  const [stats, setStats] = useState<ListeningStats | null>(null);
  const [diagnostic, setDiagnostic] = useState<ListeningDiagnostic | null>(null);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [replayCount, setReplayCount] = useState(0);
  const [startedAt, setStartedAt] = useState(0);

  async function load() {
    if (!userId) return;
    setError(null);
    setResult(null);
    setSelected(null);
    try {
      setQuestion(await getListeningQuestion(userId));
      setStartedAt(Date.now());
      setReplayCount(0);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function refreshStats() {
    if (!userId) return;
    try {
      setStats(await getListeningStats(userId));
    } catch {
      /* backend no disponible */
    }
    try {
      setDiagnostic(await getListeningDiagnostic(userId));
    } catch {
      /* backend no disponible */
    }
  }

  useEffect(() => {
    void load();
    void refreshStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  async function play() {
    if (!question || playing) return;
    setPlaying(true);
    setReplayCount((count) => count + 1);
    try {
      await speak(question.script);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPlaying(false);
    }
  }

  async function choose(index: number) {
    if (!userId || !question || result) return;
    setSelected(index);
    try {
      setResult(
        await submitListeningAnswer(
          userId,
          question.id,
          index,
          Date.now() - startedAt,
          replayCount,
        ),
      );
      setReplayCount(0);
      onAttempt();
      void refreshStats();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="listening">
      <h3>Comprensión auditiva</h3>
      {error && <p className="listening-error">{error}</p>}
      {!question ? (
        <p className="progress-empty">Cargando ejercicio…</p>
      ) : (
        <>
          <button
            type="button"
            className="listen-button"
            onClick={play}
            disabled={playing || !userId}
          >
            {playing ? "Reproduciendo…" : "Escuchar audio"}
          </button>
          {question.speech_rate > 0 && (
            <p className="listening-audio-meta">
              {question.accent} · {Math.round(question.speech_rate)} wpm ·{" "}
              {question.duration.toFixed(1)}s
            </p>
          )}
          <p className="listening-question">{question.question}</p>
          <div className="listening-options">
            {question.options.map((opt, i) => {
              let cls = "listening-option";
              if (result && i === result.correct_index) cls += " correct";
              if (result && i === selected && !result.correct) cls += " wrong";
              return (
                <button
                  key={opt}
                  type="button"
                  className={cls}
                  onClick={() => choose(i)}
                  disabled={!!result}
                >
                  {opt}
                </button>
              );
            })}
          </div>
          {result && (
            <div className={`listening-result ${result.correct ? "ok" : "ko"}`}>
              {result.correct ? "¡Correcto!" : "Incorrecto."}{" "}
              <span className="listening-script">{question.script}</span>
            </div>
          )}
          {stats && (
            <div className="listening-stats">
              <p>
                Aciertos: {stats.correct} de {stats.attempts}
                {stats.accuracy !== null ? ` (${stats.accuracy}%)` : ""}
              </p>
              <p className="listening-level">
                Nivel actual: <strong>{stats.level}</strong>
              </p>
              <ul className="listening-levels">
                {stats.levels.map((lv) => (
                  <li
                    key={lv.level}
                    className={`listening-level-pill${
                      lv.completed ? " completed" : ""
                    }`}
                  >
                    {lv.level} · {lv.mastered}/{lv.total}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {diagnostic && (
            <div className="listening-diagnostic">
              <p className="listening-recommendation">
                {diagnostic.recommendation}
              </p>
              <ul className="listening-subskills">
                {diagnostic.subskills.map((s) => (
                  <li
                    key={s.skill}
                    className={`listening-subskill${
                      s.review_due ? " review" : ""
                    }`}
                  >
                    {s.skill} · {s.attempts} ·{" "}
                    {s.accuracy !== null ? `${s.accuracy}%` : "—"}
                    {s.automaticity !== null
                      ? ` · auto ${Math.round(s.automaticity * 100)}%`
                      : ""}
                    {s.review_due ? " · revisar" : ""}
                  </li>
                ))}
              </ul>
              {diagnostic.trend.direction !== "n/a" && (
                <p className="listening-trend">
                  Tendencia reciente:{" "}
                  <strong className={`trend-${diagnostic.trend.direction}`}>
                    {trendLabel(diagnostic.trend.direction)}
                  </strong>
                  {diagnostic.trend.delta !== null
                    ? ` (${diagnostic.trend.delta > 0 ? "+" : ""}${
                        diagnostic.trend.delta
                      })`
                    : ""}
                </p>
              )}
              {diagnostic.by_topic.length > 0 && (
                <div className="listening-breakdown">
                  <p className="listening-breakdown-title">Precisión por tema</p>
                  <ul className="listening-pills">
                    {diagnostic.by_topic.map((t) => (
                      <li key={t.topic} className="listening-pill">
                        {topicLabel(t.topic)} ·{" "}
                        {t.accuracy !== null ? `${t.accuracy}%` : "—"}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {diagnostic.by_difficulty.length > 0 && (
                <div className="listening-breakdown">
                  <p className="listening-breakdown-title">
                    Precisión por dificultad
                  </p>
                  <ul className="listening-pills">
                    {diagnostic.by_difficulty.map((d) => (
                      <li key={d.difficulty} className="listening-pill">
                        Nivel {d.difficulty} ·{" "}
                        {d.accuracy !== null ? `${d.accuracy}%` : "—"}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {diagnostic.recurrence.questions_seen > 0 && (
                <p className="listening-recurrence">
                  Reintentos: {diagnostic.recurrence.retried} de{" "}
                  {diagnostic.recurrence.questions_seen} · recuperados{" "}
                  {diagnostic.recurrence.recovered}
                </p>
              )}
            </div>
          )}
          {stats?.completed && (
            <p className="listening-completed">
              ¡Has completado todos los niveles de comprensión auditiva!
            </p>
          )}
          <button
            type="button"
            className="listening-next"
            onClick={load}
            disabled={!userId}
          >
            Siguiente
          </button>
        </>
      )}
    </section>
  );
}
