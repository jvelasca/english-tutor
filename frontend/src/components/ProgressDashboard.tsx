import type { Bucket, LearningEvent, ProgressHistory } from "../types/api";
import { bucketLabel, eventLabel } from "../utils/progress";
import { useI18n } from "../hooks/useI18n";

const BUCKETS: Bucket[] = ["day", "week", "month"];

interface ProgressDashboardProps {
  history: ProgressHistory | null;
  events: LearningEvent[];
}

export function ProgressDashboard({
  history,
  events,
}: ProgressDashboardProps) {
  const { t } = useI18n();
  if (history === null) {
    return (
      <section className="progress-dashboard">
        <p className="progress-empty">{t("empty.noProgress")}</p>
      </section>
    );
  }

  const maxMessages = Math.max(1, ...history.series.map((p) => p.messages));
  const maxPron = Math.max(1, ...history.series.map((p) => p.pronunciation));

  return (
    <section className="progress-dashboard">
      <div className="pd-grid">
        <div className="pd-card">
          <h3>{t("progress.streak")}</h3>
          <p className="pd-big">
            {history.streak.current_days}
            <span className="pd-unit"> {t("progress.days")}</span>
          </p>
          <p className="pd-sub">
            {t("progress.bestStreak")}: {history.streak.best_days}{" "}
            {t("progress.days")}
          </p>
          {history.streak.last_active_date && (
            <p className="pd-sub pd-faint">
              {t("progress.lastActivity")}: {history.streak.last_active_date}
            </p>
          )}
        </div>

        <div className="pd-card">
          <h3>{t("progress.activity")}</h3>
          {history.series.length === 0 ? (
            <p className="progress-empty">{t("progress.noActivity")}</p>
          ) : (
            <div className="pd-chart" role="img" aria-label={t("progress.activity")}>
              {history.series.map((p) => (
                <div key={p.bucket} className="pd-col" title={p.bucket}>
                  <div className="pd-bars">
                    <span
                      className="pd-bar pd-bar-messages"
                      style={{
                        height:
                          p.messages === 0
                            ? "0%"
                            : `${Math.max(10, (p.messages / maxMessages) * 100)}%`,
                      }}
                    />
                    <span
                      className="pd-bar pd-bar-pron"
                      style={{
                        height:
                          p.pronunciation === 0
                            ? "0%"
                            : `${Math.max(10, (p.pronunciation / maxPron) * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="pd-axis">{p.bucket}</span>
                </div>
              ))}
            </div>
          )}
          <div className="pd-legend">
            <span>
              <span className="pd-dot pd-dot-messages" aria-hidden="true" />{" "}
              {t("progress.messages")}
            </span>
            <span>
              <span className="pd-dot pd-dot-pron" aria-hidden="true" />{" "}
              {t("progress.pronunciation")}
            </span>
          </div>
        </div>
      </div>

      <div className="pd-card">
        <h3>{t("progress.errorMastery")}</h3>
        <div className="pd-mastery">
          <div>
            <h4 className="pd-subhead">
              {t("progress.active")} ({history.mastery.active.length})
            </h4>
            {history.mastery.active.length === 0 ? (
              <p className="progress-empty">{t("progress.noActiveErrors")}</p>
            ) : (
              <ul className="pd-errors">
                {history.mastery.active.map((e) => (
                  <li key={e.rule} className="pd-error">
                    <span className="pd-error-count">{e.count}×</span>
                    <span>{e.message}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h4 className="pd-subhead">
              {t("progress.resolved")} ({history.mastery.resolved.length})
            </h4>
            {history.mastery.resolved.length === 0 ? (
              <p className="progress-empty">{t("progress.noResolved")}</p>
            ) : (
              <ul className="pd-errors">
                {history.mastery.resolved.map((e) => (
                  <li key={e.rule} className="pd-error pd-error-resolved">
                    <span className="pd-error-count">{e.count}×</span>
                    <span>{e.message}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      <div className="pd-card">
        <h3>{t("progress.milestones")}</h3>
        <ul className="pd-milestones">
          {history.milestones.map((m) => (
            <li
              key={m.id}
              className={`pd-milestone${m.achieved ? " achieved" : ""}`}
            >
              {m.label}
            </li>
          ))}
        </ul>
      </div>

      <div className="pd-card">
        <h3>{t("progress.recentActivity")}</h3>
        {events.length === 0 ? (
          <p className="progress-empty">{t("progress.noRecentActivity")}</p>
        ) : (
          <ul className="pd-timeline">
            {events.slice(0, 8).map((e) => (
              <li key={e.id} className="pd-event">
                <span className={`pd-event-type ${e.type}`}>{eventLabel(e.type)}</span>
                <span className="pd-event-detail">{e.detail || "—"}</span>
                <span className="pd-event-date">{e.created_at.slice(0, 10)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

export function BucketToggle({
  value,
  onChange,
}: {
  value: Bucket;
  onChange: (b: Bucket) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="bucket-toggle" role="group" aria-label={t("progress.bucketAria")}>
      {BUCKETS.map((b) => (
        <button
          key={b}
          type="button"
          className={b === value ? "active" : ""}
          onClick={() => onChange(b)}
          aria-pressed={b === value}
        >
          {bucketLabel(b)}
        </button>
      ))}
    </div>
  );
}
