import { useCallback, useEffect, useState } from "react";
import {
  enroll,
  getExam,
  getLevelCompletions,
  getLevelDetail,
  getLevels,
  getPlacement,
  submitExam,
  submitObjectiveAssessment,
  submitPlacement,
} from "../api/academy";
import type {
  CurriculumObjective,
  Exam,
  ExamResult,
  LevelCompletion,
  LevelDetail,
  LevelSummary,
  ModuleProgress,
  ObjectiveAssessmentResult,
  Placement,
  PlacementResult,
} from "../types/api";

type Flow = "none" | "placement" | "exam";

interface AcademyProps {
  userId: string | null;
  onStartLesson: (
    objectiveId: string,
    title: string,
    levelId: string,
    skills: string[],
  ) => void;
  onClose: () => void;
}

function statusLabel(status: string): string {
  if (status === "mastered") return "Dominado";
  if (status === "review") return "A repasar";
  if (status === "available") return "Disponible";
  return "Bloqueado";
}

export function Academy({ userId, onStartLesson, onClose }: AcademyProps) {
  const [levels, setLevels] = useState<LevelSummary[]>([]);
  const [selectedLevel, setSelectedLevel] = useState<LevelSummary | null>(null);
  const [detail, setDetail] = useState<LevelDetail | null>(null);
  const [completions, setCompletions] = useState<LevelCompletion[]>([]);
  const [flow, setFlow] = useState<Flow>("none");
  const [placement, setPlacement] = useState<Placement | null>(null);
  const [exam, setExam] = useState<Exam | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [placementResult, setPlacementResult] = useState<PlacementResult | null>(
    null,
  );
  const [examResult, setExamResult] = useState<ExamResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadLevels = useCallback(async () => {
    if (!userId) return;
    try {
      setLevels((await getLevels(userId)).levels);
    } catch {
      /* backend no disponible */
    }
  }, [userId]);

  const loadCompletions = useCallback(async () => {
    if (!userId) return;
    try {
      setCompletions(await getLevelCompletions(userId));
    } catch {
      /* backend no disponible */
    }
  }, [userId]);

  useEffect(() => {
    void loadLevels();
    void loadCompletions();
  }, [loadLevels, loadCompletions]);

  async function openLevel(level: LevelSummary) {
    if (!userId || !level.available || !level.unlocked) return;
    setError(null);
    setFlow("none");
    try {
      if (!level.enrolled) await enroll(userId, level.level_id);
      setDetail(await getLevelDetail(userId, level.level_id));
      setSelectedLevel(level);
      void loadLevels();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function reloadDetail() {
    if (!userId || !detail) return;
    try {
      setDetail(await getLevelDetail(userId, detail.level_id));
      void loadLevels();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function startPlacement() {
    if (!userId) return;
    setError(null);
    setFlow("placement");
    setAnswers({});
    setPlacementResult(null);
    try {
      setPlacement(await getPlacement());
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function startExam() {
    if (!userId || !selectedLevel) return;
    setError(null);
    setFlow("exam");
    setAnswers({});
    setExamResult(null);
    try {
      setExam(await getExam(selectedLevel.level_id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function submit() {
    if (!userId || busy) return;
    setBusy(true);
    setError(null);
    try {
      if (flow === "placement") {
        setPlacementResult(await submitPlacement(userId, answers));
      } else if (flow === "exam") {
        if (!selectedLevel) return;
        setExamResult(await submitExam(userId, selectedLevel.level_id, answers));
        void loadCompletions();
        void loadLevels();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function choose(itemId: string, index: number) {
    setAnswers((prev) => ({ ...prev, [itemId]: index }));
  }

  const closeFlow = () => {
    setFlow("none");
    setPlacementResult(null);
    setExamResult(null);
  };

  return (
    <div className="academy">
      <header className="academy-header">
        <div>
          <h2>English Tutor Academy</h2>
          <p>Currículum CEFR · A1 → C2</p>
        </div>
        <button type="button" className="academy-close" onClick={onClose}>
          Volver al chat
        </button>
      </header>

      <div className="academy-body">
        <aside className="academy-side">
          <h3>Niveles</h3>
          <ul className="academy-levels">
            {levels.map((lv) => (
              <li key={lv.level_id}>
                <button
                  type="button"
                  className={`academy-level${
                    detail?.level_id === lv.level_id ? " active" : ""
                  }${!lv.available || !lv.unlocked ? " locked" : ""}`}
                  onClick={() => openLevel(lv)}
                  disabled={!lv.available || !lv.unlocked}
                >
                  <span className="academy-level-code">{lv.level}</span>
                  <span className="academy-level-title">{lv.title}</span>
                  {lv.available && lv.enrolled && (
                    <span className="academy-level-progress">
                      {Math.round(lv.progress * 100)}%
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>

          <div className="academy-actions">
            <button type="button" onClick={startPlacement} disabled={!userId}>
              Test de nivel
            </button>
            <button
              type="button"
              onClick={startExam}
              disabled={!userId || !selectedLevel}
            >
              Examen final {selectedLevel?.level ?? ""}
            </button>
          </div>

          {completions.length > 0 && (
            <div className="academy-certificates">
              <h3>Niveles completados</h3>
              {completions.map((c) => (
                <div key={c.id} className="academy-certificate">
                  <strong>{c.level}</strong> · {Math.round(c.overall * 100)}%
                </div>
              ))}
            </div>
          )}
        </aside>

        <main className="academy-main">
          {error && <p className="academy-error">{error}</p>}

          {flow === "placement" && (
            <AssessmentFlow
              title={placement?.title ?? "Test de nivel"}
              description={placement?.description}
              items={placement?.items.map((i) => ({
                id: i.id,
                prompt: i.prompt,
                options: i.options,
              })) ?? []}
              answers={answers}
              onChoose={choose}
              onSubmit={submit}
              busy={busy}
              onClose={closeFlow}
              resultNode={
                placementResult && (
                  <div className="academy-result">
                    <strong>Nivel estimado: {placementResult.level}</strong>
                    <span>
                      Confianza {Math.round(placementResult.confidence * 100)}% ·{" "}
                      {placementResult.correct}/{placementResult.answered} aciertos
                    </span>
                  </div>
                )
              }
            />
          )}

          {flow === "exam" && (
            <AssessmentFlow
              title={exam?.title ?? `Examen final ${selectedLevel?.level ?? ""}`}
              items={exam?.items.map((i) => ({
                id: i.id,
                prompt: i.prompt,
                options: i.options,
              })) ?? []}
              answers={answers}
              onChoose={choose}
              onSubmit={submit}
              busy={busy}
              onClose={closeFlow}
              resultNode={
                examResult && (
                  <div
                    className={`academy-result ${
                      examResult.passed ? "ok" : "ko"
                    }`}
                  >
                    <strong>
                      {examResult.passed
                        ? `Evaluación ${selectedLevel?.level ?? ""} superada`
                        : "Evaluación aún no superada"}
                    </strong>
                    <span>
                      Puntuación global {Math.round(examResult.overall * 100)}%
                    </span>
                    <span>
                      Mide grammar, vocabulary, reading y listening (sin
                      producción oral/escrita).
                    </span>
                    {examResult.failed_skills.length > 0 && (
                      <span>
                        Destrezas a reforzar:{" "}
                        {examResult.failed_skills.join(", ")}
                      </span>
                    )}
                  </div>
                )
              }
            />
          )}

          {flow === "none" &&
            (detail ? (
              <LevelView
                detail={detail}
                onStartLesson={onStartLesson}
                userId={userId ?? ""}
                onUpdated={() => void reloadDetail()}
              />
            ) : (
              <div className="academy-empty">
                Selecciona un nivel para empezar.
              </div>
            ))}
        </main>
      </div>
    </div>
  );
}

interface FlowItem {
  id: string;
  prompt: string;
  options: string[];
}

function AssessmentFlow({
  title,
  description,
  items,
  answers,
  onChoose,
  onSubmit,
  busy,
  onClose,
  resultNode,
}: {
  title: string;
  description?: string;
  items: FlowItem[];
  answers: Record<string, number>;
  onChoose: (id: string, index: number) => void;
  onSubmit: () => void;
  busy: boolean;
  onClose: () => void;
  resultNode?: React.ReactNode;
}) {
  return (
    <div className="academy-flow">
      <div className="academy-flow-head">
        <h3>{title}</h3>
        <button type="button" onClick={onClose}>
          Cerrar
        </button>
      </div>
      {description && <p className="academy-flow-desc">{description}</p>}
      {items.map((item) => (
        <div key={item.id} className="academy-question">
          <p>{item.prompt}</p>
          <div className="academy-options">
            {item.options.map((opt, i) => (
              <button
                key={opt}
                type="button"
                className={
                  answers[item.id] === i ? "selected" : ""
                }
                onClick={() => onChoose(item.id, i)}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      ))}
      {resultNode}
      <button
        type="button"
        className="academy-submit"
        onClick={onSubmit}
        disabled={busy || items.length === 0}
      >
        {busy ? "Enviando…" : "Enviar respuestas"}
      </button>
    </div>
  );
}

function CounterBadges({
  correct,
  incorrect,
  toReview,
}: {
  correct: number;
  incorrect: number;
  toReview?: number;
}) {
  return (
    <span className="academy-counters">
      {correct > 0 && (
        <span className="academy-counter correct" title="Aciertos">
          ✓ {correct}
        </span>
      )}
      {incorrect > 0 && (
        <span className="academy-counter incorrect" title="Fallos">
          ✗ {incorrect}
        </span>
      )}
      {toReview ? (
        <span className="academy-counter review" title="A repasar">
          ⟳ {toReview}
        </span>
      ) : null}
    </span>
  );
}

function LevelView({
  detail,
  onStartLesson,
  userId,
  onUpdated,
}: {
  detail: LevelDetail;
  onStartLesson: (
    objectiveId: string,
    title: string,
    levelId: string,
    skills: string[],
  ) => void;
  userId: string;
  onUpdated: () => void;
}) {
  return (
    <div className="academy-level-view">
      <div className="academy-level-head">
        <h3>
          {detail.level} · {detail.title}
        </h3>
        <p>
          {detail.progress.mastered}/{detail.progress.total} objetivos dominados (
          {Math.round(detail.progress.progress * 100)}%)
        </p>
        <CounterBadges
          correct={detail.progress.correct}
          incorrect={detail.progress.incorrect}
          toReview={detail.progress.to_review}
        />
      </div>

      {detail.modules_progress.map((mod) => {
        const objectives = detail.objectives.filter(
          (o) => o.module_id === mod.module_id,
        );
        return (
          <ModuleSection
            key={mod.module_id}
            module={mod}
            objectives={objectives}
            levelId={detail.level_id}
            userId={userId}
            onStartLesson={onStartLesson}
            onUpdated={onUpdated}
          />
        );
      })}
    </div>
  );
}

function ModuleSection({
  module,
  objectives,
  levelId,
  userId,
  onStartLesson,
  onUpdated,
}: {
  module: ModuleProgress;
  objectives: CurriculumObjective[];
  levelId: string;
  userId: string;
  onStartLesson: (
    objectiveId: string,
    title: string,
    levelId: string,
    skills: string[],
  ) => void;
  onUpdated: () => void;
}) {
  const [expanded, setExpanded] = useState(true);
  return (
    <section className="academy-module">
      <button
        type="button"
        className="academy-module-head"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <span className="academy-module-arrow">
          {expanded ? "▾" : "▸"}
        </span>
        <h4>
          {module.order}. {module.title}
        </h4>
        <span className="academy-module-count">
          {module.mastered}/{module.total}
        </span>
        <CounterBadges
          correct={module.correct}
          incorrect={module.incorrect}
          toReview={module.to_review}
        />
      </button>
      {expanded && (
        <ol className="academy-objectives">
          {objectives.map((obj) => (
            <ObjectiveRow
              key={obj.id}
              objective={obj}
              levelId={levelId}
              userId={userId}
              onStart={onStartLesson}
              onUpdated={onUpdated}
            />
          ))}
        </ol>
      )}
    </section>
  );
}

function ObjectiveRow({
  objective,
  levelId,
  userId,
  onStart,
  onUpdated,
}: {
  objective: CurriculumObjective;
  levelId: string;
  userId: string;
  onStart: (
    objectiveId: string,
    title: string,
    levelId: string,
    skills: string[],
  ) => void;
  onUpdated: () => void;
}) {
  return (
    <li className={`academy-objective status-${objective.status}`}>
      <div className="academy-objective-main">
        <span className="academy-objective-status">
          {statusLabel(objective.status)}
        </span>
        <div>
          <p className="academy-objective-title">{objective.title}</p>
          <p className="academy-objective-cando">{objective.can_do}</p>
        </div>
      </div>
      <CounterBadges
        correct={objective.correct}
        incorrect={objective.incorrect}
      />
      {objective.status !== "locked" && (
        <button
          type="button"
          className="academy-objective-start"
          onClick={() =>
            onStart(
              objective.id,
              objective.title,
              levelId,
              objective.skills,
            )
          }
        >
          {objective.status === "mastered" ? "Repasar" : "Empezar"}
        </button>
      )}
      {objective.checks.length > 0 && (
        <ObjectiveChecks
          objective={objective}
          levelId={levelId}
          userId={userId}
          onUpdated={onUpdated}
        />
      )}
    </li>
  );
}

function ObjectiveChecks({
  objective,
  levelId,
  userId,
  onUpdated,
}: {
  objective: CurriculumObjective;
  levelId: string;
  userId: string;
  onUpdated: () => void;
}) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [result, setResult] = useState<ObjectiveAssessmentResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const answeredAll = objective.checks.every((c) => c.id in answers);

  async function submit() {
    if (busy || !answeredAll) return;
    setBusy(true);
    setError(null);
    try {
      setResult(
        await submitObjectiveAssessment(userId, levelId, objective.id, answers),
      );
      onUpdated();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="academy-checks">
      <h5>Evaluación rápida</h5>
      {objective.checks.map((check) => (
        <div key={check.id} className="academy-check">
          <p>{check.prompt}</p>
          <div className="academy-options">
            {check.options.map((opt, i) => (
              <button
                key={opt}
                type="button"
                className={answers[check.id] === i ? "selected" : ""}
                onClick={() =>
                  setAnswers((prev) => ({ ...prev, [check.id]: i }))
                }
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      ))}
      {error && <p className="academy-error">{error}</p>}
      {result && (
        <div
          className={`academy-result ${
            result.overall >= 0.8 ? "ok" : "ko"
          }`}
        >
          <strong>Resultado: {Math.round(result.overall * 100)}%</strong>
          <span>
            {result.correct}/{result.total} aciertos
          </span>
        </div>
      )}
      <button
        type="button"
        className="academy-check-submit"
        onClick={submit}
        disabled={busy || !answeredAll}
      >
        {busy ? "Enviando…" : "Comprobar respuestas"}
      </button>
    </div>
  );
}
