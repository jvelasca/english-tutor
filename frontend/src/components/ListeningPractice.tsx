import { useEffect, useState } from "react";
import {
  getListeningQuestion,
  getListeningStats,
  submitListeningAnswer,
} from "../api/listening";
import { speak } from "../api/voz";
import type {
  ListeningAnswerResponse,
  ListeningQuestion,
  ListeningStats,
} from "../types/api";

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
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!userId) return;
    setError(null);
    setResult(null);
    setSelected(null);
    try {
      setQuestion(await getListeningQuestion(userId));
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
  }

  useEffect(() => {
    void load();
    void refreshStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  async function play() {
    if (!question || playing) return;
    setPlaying(true);
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
      setResult(await submitListeningAnswer(userId, question.id, index));
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
            <p className="listening-stats">
              Aciertos: {stats.correct} de {stats.attempts}
              {stats.accuracy !== null ? ` (${stats.accuracy}%)` : ""}
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
