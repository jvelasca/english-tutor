import { useI18n } from "../../hooks/useI18n";
import { ConnectDeviceCard } from "../../components/ConnectDeviceCard";

/**
 * Página de ayuda para conectar un dispositivo (móvil/tableta) a la red local:
 * instrucciones para confiar el certificado autofirmado y abrir la app por IP o
 * por nombre `.local`, por plataforma (Windows, Android, iPhone/iPad).
 */
export function ConnectHelp() {
  const { t } = useI18n();

  const steps = [
    {
      icon: "💻",
      title: t("connect.windows.title"),
      body: t("connect.windows.body"),
    },
    {
      icon: "🤖",
      title: t("connect.android.title"),
      body: t("connect.android.body"),
    },
    {
      icon: "📱",
      title: t("connect.ios.title"),
      body: t("connect.ios.body"),
    },
  ];

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-8">
      <h1 className="text-2xl font-bold tracking-tight text-foreground">
        {t("connect.title")}
      </h1>
      <p className="mt-1 text-sm text-muted-foreground">
        {t("connect.subtitle")}
      </p>

      <div className="mt-6">
        <ConnectDeviceCard />
      </div>

      <h2 className="mt-8 text-lg font-semibold text-foreground">
        {t("connect.trustTitle")}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        {t("connect.trustBody")}
      </p>

      <ol className="mt-4 space-y-4">
        {steps.map((step) => (
          <li
            key={step.title}
            className="rounded-xl border border-border bg-card p-4"
          >
            <div className="flex items-start gap-3">
              <span className="text-xl" aria-hidden="true">
                {step.icon}
              </span>
              <div>
                <p className="font-semibold text-foreground">{step.title}</p>
                <p className="mt-1 text-sm whitespace-pre-line text-muted-foreground">
                  {step.body}
                </p>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
