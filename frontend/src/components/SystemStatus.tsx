import { useEffect, useState } from "react";
import QRCode from "react-qr-code";
import {
  getDependencies,
  getHealth,
  type DependencyStatus,
} from "../api/health";
import { getNetwork, type NetworkInfo } from "../api/network";
import { useAudioCapabilities } from "../hooks/useAudioCapabilities";
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
  { key: "audio_library", i18nKey: "status.audioLibrary" },
];

function Check({ ok }: { ok: boolean }) {
  return (
    <span
      className={`status-dot ${ok ? "status-dot--ok" : "status-dot--off"}`}
      aria-hidden="true"
    />
  );
}

export function SystemStatus() {
  const { t } = useI18n();
  const capabilities = useAudioCapabilities();
  const [deps, setDeps] = useState<DependencyStatus | null>(null);
  const [version, setVersion] = useState("");
  const [network, setNetwork] = useState<NetworkInfo | null>(null);

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
      try {
        const n = await getNetwork();
        if (!cancelled) setNetwork(n);
      } catch {
        /* red no disponible */
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

      <div className="system-status__section" aria-label={t("status.secureContext")}>
        <p className="system-status__section-title">{t("status.microphone")}</p>
        <ul className="system-status__list">
          <li className="system-status__item">
            <Check ok={capabilities.secureContext} />
            <span>{t("status.secureContext")}</span>
          </li>
          <li className="system-status__item">
            <Check ok={capabilities.supported} />
            <span>{t("status.microphone")}</span>
          </li>
        </ul>
      </div>

      {network && (
        <div className="system-status__section">
          <p className="system-status__section-title">
            {t("status.scanToConnect")}
          </p>
          <div className="system-status__qr">
            <QRCode value={network.url} size={112} bgColor="transparent" />
          </div>
          <div className="system-status__urls">
            <a href={network.url} target="_blank" rel="noreferrer">
              {network.url}
            </a>
            <a href={network.local_url} target="_blank" rel="noreferrer">
              {network.local_url}
            </a>
          </div>
        </div>
      )}

      <div className="system-status__meta">
        {version && <span className="status-bar-muted">v{version}</span>}
        <span className="status-bar-muted" title={t("status.urlTitle")}>
          {appUrl()}
        </span>
      </div>
    </div>
  );
}
