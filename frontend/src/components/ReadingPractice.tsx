import { useCallback, useEffect, useState } from "react";
import { getLevelDetail, getLevels } from "../api/academy";
import type { CurriculumObjective, LevelDetail, LevelSummary } from "../types/api";
import { ReadingIcon } from "./Icons";

interface ReadingPracticeProps {
  userId: string | null;
  onOpenAcademy: () => void;
  onStartLesson: (
    objectiveId: string,
    title: string,
    levelId: string,
    skills: string[],
  ) => void;
}

function statusLabel(status: string): string {
  switch (status) {
    case "mastered":
      return "Dominado";
    case "review":
      return "A repasar";
    case "available":
      return "Disponible";
    default:
      return "Bloqueado";
  }
}

function pickLevel(levels: LevelSummary[]): LevelSummary | null {
  return (
    levels.find((l) => l.available && l.unlocked && l.enrolled) ??
    levels.find((l) => l.available && l.unlocked) ??
    null
  );
}

export function ReadingPractice({
  userId,
  onOpenAcademy,
  onStartLesson,
}: ReadingPracticeProps) {
  const [level, setLevel] = useState<LevelSummary | null>(null);
  const [detail, setDetail] = useState<LevelDetail | null>(null);

  const load = useCallback(async () => {
    if (!userId) return;
    try {
      const { levels } = await getLevels(userId);
      const current = pickLevel(levels);
      setLevel(current);
      if (current) {
        setDetail(await getLevelDetail(userId, current.level_id));
      }
    } catch {
      /* backend no disponible */
    }
  }, [userId]);

  useEffect(() => {
    void load();
  }, [load]);

  const objectives: CurriculumObjective[] = (detail?.objectives ?? []).filter(
    (o) => o.skills.includes("reading"),
  );

  return (
    <section className="reading-practice">
      <header className="reading-practice-header">
        <span className="reading-practice-icon" aria-hidden="true">
          <ReadingIcon size={22} />
        </span>
        <div>
          <h2>Práctica de lectura</h2>
          <p>
            {level
              ? `${level.level} · ${level.title}`
              : "Lectura guiada por el currículum CEFR"}
          </p>
        </div>
        <button
          type="button"
          className="reading-academy-button"
          onClick={onOpenAcademy}
        >
          Abrir en Academy
        </button>
      </header>

      {objectives.length === 0 ? (
        <p className="reading-empty">
          Aún no hay objetivos de lectura disponibles para tu nivel. Explora la
          Academy para matricularte en un nivel.
        </p>
      ) : (
        <ol className="reading-list">
          {objectives.map((obj) => (
            <li key={obj.id} className={`reading-card status-${obj.status}`}>
              <div className="reading-card-main">
                <span className="reading-card-status">
                  {statusLabel(obj.status)}
                </span>
                <h3>{obj.title}</h3>
                <p>{obj.can_do}</p>
              </div>
              {obj.status !== "locked" && (
                <button
                  type="button"
                  className="reading-card-start"
                  onClick={() =>
                    onStartLesson(obj.id, obj.title, level?.level_id ?? "", obj.skills)
                  }
                >
                  {obj.status === "mastered" ? "Repasar" : "Empezar"}
                </button>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
