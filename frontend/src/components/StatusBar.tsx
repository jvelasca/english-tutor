import { useEffect, useState } from "react";
import { getDependencies, getHealth, type DependencyStatus } from "../api/health";

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

const ITEMS: { key: keyof DependencyStatus; label: string }[] = [
  { key: "api", label: "API" },
  { key: "database", label: "BD" },
  { key: "ollama", label: "Ollama" },
  { key: "stt", label: "STT" },
  { key: "tts", label: "TTS" },
];

export function StatusBar() {
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
    const id = window.setInterval(() => void refresh(), 10_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const apiDot = deps ? toDot(deps.api) : "off";

  return (
    <footer className="status-bar" aria-label="Estado del servidor">
      <span className="status-bar-group">
        <span className={`status-dot status-dot--${apiDot}`} aria-hidden="true" />
        <span className="status-bar-label">Servidor</span>
        {version && <span className="status-bar-muted">v{version}</span>}
      </span>

      <span className="status-bar-sep" aria-hidden="true" />

      <span className="status-bar-group">
        {ITEMS.map((item) => {
          const dot = deps ? toDot(deps[item.key]) : "off";
          return (
            <span className="status-bar-item" key={item.key}>
              <span
                className={`status-dot status-dot--${dot}`}
                aria-hidden="true"
              />
              <span>{item.label}</span>
            </span>
          );
        })}
      </span>

      <span className="status-bar-sep" aria-hidden="true" />

      <span className="status-bar-group status-bar-url" title="URL de acceso en tu red">
        {appUrl()}
      </span>
    </footer>
  );
}
