import { useEffect, useState } from "react";
import QRCode from "react-qr-code";
import { getNetwork, type NetworkInfo } from "../api/network";
import { useI18n } from "../hooks/useI18n";

/**
 * Tarjeta "Connect a device": QR para escanear con el móvil y URLs de acceso
 * (IP siempre, `.local` solo si mDNS resuelve). La guía de conexión y de
 * confianza del certificado vive en SystemStatus (Ajustes → Sistema).
 */
export function ConnectDeviceCard() {
  const { t } = useI18n();
  const [network, setNetwork] = useState<NetworkInfo | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getNetwork()
      .then((n) => {
        if (!cancelled) setNetwork(n);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!network) {
    return (
      <div className="rounded-xl border border-border bg-card p-4">
        <p className="text-sm font-semibold text-foreground">
          {t("connect.cardTitle")}
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {t("connect.cardSubtitle")}
        </p>
        <p className="mt-3 text-xs text-muted-foreground">
          {t("connect.noNetwork")}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-sm font-semibold text-foreground">
        {t("connect.cardTitle")}
      </p>
      <p className="mt-0.5 text-xs text-muted-foreground">
        {t("connect.cardSubtitle")}
      </p>

      <div className="mt-3 flex justify-center rounded-lg bg-background p-3">
        <QRCode value={network.url} size={128} bgColor="transparent" />
      </div>

      <div className="mt-3 space-y-1.5 text-xs">
        <a
          className="block break-all font-medium text-primary underline-offset-2 hover:underline"
          href={network.url}
          target="_blank"
          rel="noreferrer"
        >
          {network.url}
        </a>
        {network.local_url_available && (
          <a
            className="block break-all text-primary underline-offset-2 hover:underline"
            href={network.local_url}
            target="_blank"
            rel="noreferrer"
          >
            {network.local_url}
          </a>
        )}
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        {t("connect.localOnly")}
      </p>
    </div>
  );
}
