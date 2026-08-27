import { useEffect, useState } from "react";
import {
  getDependencies,
  getHealth,
  type DependencyStatus,
} from "../api/health";
import { useI18n } from "../hooks/useI18n";

type Dot = "ok" | "warn" | "off" | "unknown";

function toDot(value: string | undefined): Dot {
  switch (value) {
    case "ok":
    case "ready":
      return "ok";
    case "error":
      return "off";
    case "unavailable":
      return "warn";
    default:
      return "unknown";
  }
}

function appUrl(): string {
  if (typeof window === "undefined") return "";
  return window.location.host || "localhost:5173";
}

const ITEMS: { key: keyof DependencyStatus; i18nKey: string }[] = [
  { key: "api", i18nKey: "status.api" },
  { key: "database", i18nKey: "status.database" },
  { key: "ollama", i18nKey: "status.ollama" },
  { key: "stt", i18nKey: "status.stt" },
  { key: "tts", i18nKey: "status.tts" },
];

export function SystemStatus() {
  const { t } = useI18n();
  const [deps, setDeps] = useState<DependencyStatus | null>(null);
  const [version, setVersion] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      try {
        const [d, h] = await Promise.all([getDependencies(), getHealth()]);
        if (cancelled) return;
        setDeps(d);
        setVersion(h.version);
      } catch {
        if (cancelled) return;
        setDeps(null);
      }
    }
    void refresh();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="system-status">
      <ul className="system-status__list">
        {ITEMS.map((item) => {
          const dot = deps ? toDot(deps[item.key]) : "off";
          return (
            <li className="system-status__item" key={item.key}>
              <span className={`status-dot status-dot--${dot}`} aria-hidden="true" />
              <span>{t(item.i18nKey)}</span>
            </li>
          );
        })}
      </ul>
      <div className="system-status__meta">
        {version && (
          <span className="status-bar-muted">
            v{version}
          </span>
        )}
        <span className="status-bar-muted" title={t("status.urlTitle")}>
          {appUrl()}
        </span>
      </div>
    </div>
  );
}
