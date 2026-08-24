import { useEffect, useState } from "react";
import { getNetwork } from "../api/network";
import type { NetworkInfo } from "../types/api";

async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* sigue al fallback */
  }
  try {
    const el = document.createElement("textarea");
    el.value = text;
    el.style.position = "fixed";
    el.style.opacity = "0";
    document.body.appendChild(el);
    el.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(el);
    return ok;
  } catch {
    return false;
  }
}

export function NetworkBadge() {
  const [info, setInfo] = useState<NetworkInfo | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getNetwork()
      .then((d) => {
        if (!cancelled) setInfo(d);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  async function copy() {
    if (!info) return;
    if (await copyText(info.url)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    }
  }

  if (!info) return null;

  return (
    <div
      className="network-badge"
      title={`Accede desde cualquier equipo de tu red en ${info.url}`}
    >
      <span className="network-badge-dot" aria-hidden="true" />
      <span className="network-badge-url">{info.url}</span>
      <button
        type="button"
        className="network-badge-copy"
        onClick={copy}
        aria-label="Copiar dirección de acceso"
      >
        {copied ? "¡Copiado!" : "Copiar"}
      </button>
    </div>
  );
}
