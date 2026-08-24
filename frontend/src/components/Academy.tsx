import { useCallback, useEffect, useState } from "react";
import {
  enroll,
  getCertificates,
  getExam,
  getLevelDetail,
  getLevels,
  getPlacement,
  submitExam,
  submitPlacement,
} from "../api/academy";
import type {
  Certificate,
  CurriculumObjective,
  Exam,
  ExamResult,
  LevelDetail,
  LevelSummary,
  ModuleProgress,
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
  const [detail, setDetail] = useState<LevelDetail | null>(null);
  const [certificates, setCertificates] = useState<Certificate[]>([]);
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

  const loadCertificates = useCallback(async () => {
    if (!userId) return;
    try {
      setCertificates(await getCertificates(userId));
    } catch {
      /* backend no disponible */
    }
  }, [userId]);

  useEffect(() => {
    void loadLevels();
    void loadCertificates();
  }, [loadLevels, loadCertificates]);

  async function openLevel(level: LevelSummary) {
    if (!userId || !level.available) return;
    setError(null);
    setFlow("none");
    try {
      if (!level.enrolled) await enroll(userId, level.level_id);
      setDetail(await getLevelDetail(userId, level.level_id));
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
    if (!userId) return;
    setError(null);
    setFlow("exam");
    setAnswers({});
    setExamResult(null);
    try {
      setExam(await getExam("a1"));
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
        setExamResult(await submitExam(userId, "a1", answers));
        void loadCertificates();
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
          <p>Currículum CEFR · A1 piloto</p>
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
                  }${!lv.available ? " locked" : ""}`}
                  onClick={() => openLevel(lv)}
                  disabled={!lv.available}
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
            <button type="button" onClick={startExam} disabled={!userId}>
              Examen final A1
            </button>
          </div>

          {certificates.length > 0 && (
            <div className="academy-certificates">
              <h3>Certificados</h3>
              {certificates.map((c) => (
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
              title={exam?.title ?? "Examen final A1"}
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
                        ? "¡A1 superado!"
                        : "Aún no superado"}
                    </strong>
                    <span>
                      Puntuación global {Math.round(examResult.overall * 100)}%
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
              <LevelView detail={detail} onStartLesson={onStartLesson} />
            ) : (
              <div className="academy-empty">
                Selecciona el nivel <strong>A1</strong> para empezar.
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
}: {
  detail: LevelDetail;
  onStartLesson: (
    objectiveId: string,
    title: string,
    levelId: string,
    skills: string[],
  ) => void;
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
            onStartLesson={onStartLesson}
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
  onStartLesson,
}: {
  module: ModuleProgress;
  objectives: CurriculumObjective[];
  levelId: string;
  onStartLesson: (
    objectiveId: string,
    title: string,
    levelId: string,
    skills: string[],
  ) => void;
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
              onStart={onStartLesson}
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
  onStart,
}: {
  objective: CurriculumObjective;
  levelId: string;
  onStart: (
    objectiveId: string,
    title: string,
    levelId: string,
    skills: string[],
  ) => void;
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
    </li>
  );
}
