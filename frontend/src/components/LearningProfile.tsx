import { bandLabel, cefrTone } from "../utils/cefr";
import { formatAverage } from "../utils/progress";
import type { LearningProfile as ProfileData } from "../types/api";

interface LearningProfileProps {
  profile: ProfileData | null;
}

export function LearningProfile({ profile }: LearningProfileProps) {
  if (profile === null) {
    return (
      <section className="learning-profile">
        <p className="progress-empty">
          Aún no hay perfil de aprendizaje. Escribe en inglés y aquí verás tu nivel,
          vocabulario y recomendaciones.
        </p>
      </section>
    );
  }

  const tone = cefrTone(profile.estimated_level);

  return (
    <section className="learning-profile">
      <header className="learning-header">
        <span className="learning-title">Tu perfil</span>
        <span className={`cefr-badge ${tone}`} title="Nivel estimado a partir de tu actividad">
          Nivel estimado · {profile.estimated_level}
        </span>
      </header>

      {profile.estimated_descriptor && (
        <p className="cefr-descriptor">{profile.estimated_descriptor}</p>
      )}

      <div className="cefr-bands">
        {(["vocabulary", "grammar", "fluency", "pronunciation"] as const).map(
          (skill) => (
            <span
              key={skill}
              className={`cefr-band ${cefrTone(profile.estimated_bands[skill])}`}
            >
              <span className="cefr-band-label">{bandLabel(skill)}</span>
              <span className="cefr-band-value">
                {profile.estimated_bands[skill]}
              </span>
            </span>
          ),
        )}
      </div>

      <div className="learning-grid">
        <div className="learning-block">
          <h3>Vocabulario</h3>
          <p className="learning-big">{profile.vocabulary_size}</p>
          {(profile.vocabulary_mastered > 0 || profile.vocabulary_exposed > 0) && (
            <p className="learning-sub">
              {profile.vocabulary_mastered} dominadas · {profile.vocabulary_exposed}{" "}
              vistas
            </p>
          )}
          {profile.top_words.length > 0 ? (
            <ul className="learning-chips">
              {profile.top_words.map((w) => (
                <li key={w} className="learning-chip">
                  {w}
                </li>
              ))}
            </ul>
          ) : (
            <p className="progress-empty">Sin palabras registradas.</p>
          )}
        </div>

        <div className="learning-block">
          <h3>Pronunciación media</h3>
          <p className="learning-big">
            {profile.pronunciation_average === null
              ? "—"
              : formatAverage(profile.pronunciation_average)}
          </p>
        </div>
      </div>

      <div className="learning-block">
        <h3>Errores recurrentes</h3>
        {profile.recurring_errors.length === 0 ? (
          <p className="progress-empty">Sin errores recurrentes detectados.</p>
        ) : (
          <ul className="learning-errors">
            {profile.recurring_errors.map((e) => (
              <li key={e.rule} className="learning-error">
                <span className="learning-error-count">{e.count}×</span>
                <span>{e.message}</span>
              </li>
            ))}
          </ul>
        )}
        {profile.mastered_count > 0 && (
          <p className="learning-mastered">
            Errores superados: {profile.mastered_count}
          </p>
        )}
      </div>

      <div className="learning-block">
        <h3>Recomendaciones</h3>
        <ul className="learning-recs">
          {profile.recommendations.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
