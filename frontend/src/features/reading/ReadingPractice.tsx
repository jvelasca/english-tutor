import { useCallback, useEffect, useState } from "react";
import { getLevelDetail, getLevels } from "../../api/academy";
import type { CurriculumObjective, LevelDetail, LevelSummary } from "../../types/api";
import { ReadingIcon } from "../../components/Icons";
import { useI18n } from "../../hooks/useI18n";

interface ReadingPracticeProps {
  userId: string | null;
  onOpenCourse: () => void;
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
      return "reading.status.mastered";
    case "review":
      return "reading.status.review";
    case "available":
      return "reading.status.available";
    default:
      return "reading.status.locked";
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
  onOpenCourse,
  onStartLesson,
}: ReadingPracticeProps) {
  const { t } = useI18n();
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
      <header className="reading-practice-header flex-wrap">
        <span className="reading-practice-icon" aria-hidden="true">
          <ReadingIcon size={22} />
        </span>
        <div className="min-w-0 flex-1">
          <h2>{t("reading.title")}</h2>
          <p>
            {level ? `${level.level} · ${level.title}` : t("reading.subtitle")}
          </p>
        </div>
        <button
          type="button"
          className="reading-academy-button"
          onClick={onOpenCourse}
        >
          {t("reading.viewCourse")}
        </button>
      </header>

      {objectives.length === 0 ? (
        <p className="reading-empty">{t("reading.empty")}</p>
      ) : (
        <ol className="reading-list">
          {objectives.map((obj) => (
            <li key={obj.id} className={`reading-card status-${obj.status}`}>
              <div className="reading-card-main">
                <span className="reading-card-status">
                  {t(statusLabel(obj.status))}
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
                  {obj.status === "mastered" ? t("reading.review") : t("reading.start")}
                </button>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
