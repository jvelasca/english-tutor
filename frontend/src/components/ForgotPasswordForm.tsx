import { useState } from "react";
import { isPlausibleEmail } from "../utils/credentials";
import { useI18n } from "../hooks/useI18n";

interface ForgotPasswordFormProps {
  /** Pide el enlace de restablecimiento. Responde 200 aunque no haya cuenta. */
  onForgot: (email: string) => Promise<{ sent: boolean }>;
  /** Volver a la entrada (login). */
  onBack: () => void;
}

/**
 * «Olvidé mi contraseña» (V3.82), ahora de verdad.
 *
 * Hasta V3.81 este botón solo **explicaba** que la contraseña la restablecía el
 * webmaster: era un texto informativo disfrazado de acción. Ahora pide el enlace
 * y la persona elige su contraseña sola.
 *
 * Dos honestidades deliberadas:
 *
 * - La respuesta no revela si el email tiene cuenta (el backend responde igual
 *   siempre), así que el texto tampoco lo promete: «si ese email tiene una
 *   cuenta…».
 * - Sin SMTP no sale ningún correo. Se dice en vez de fingir un envío, porque un
 *   mensaje que promete un correo inexistente solo sirve para hacer esperar.
 */
export function ForgotPasswordForm({ onForgot, onBack }: ForgotPasswordFormProps) {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [noMail, setNoMail] = useState(false);

  async function submit() {
    if (busy || sent) return;
    setMessage(null);
    if (!isPlausibleEmail(email)) {
      setMessage(t("account.emailFormat"));
      return;
    }
    setBusy(true);
    try {
      const res = await onForgot(email);
      setSent(true);
      setNoMail(!res.sent);
    } catch {
      setMessage(t("account.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="flex flex-col gap-3"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <p className="text-sm leading-relaxed text-muted-foreground">
        {t("forgot.prompt")}
      </p>

      <label className="field">
        <span className="field-label">{t("user.email")}</span>
        <input
          className="field-input"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            setMessage(null);
          }}
          aria-label={t("user.email")}
          autoFocus
          disabled={busy || sent}
        />
      </label>

      {sent && (
        <p
          className="rounded-md border border-border bg-muted px-3 py-2 text-sm leading-relaxed text-muted-foreground"
          role="status"
        >
          {noMail ? t("forgot.noMail") : t("forgot.sent")}
        </p>
      )}
      {message && (
        <p className="dialog-error" role="alert">
          {message}
        </p>
      )}

      <div className="flex gap-2">
        <button
          type="submit"
          className="dialog-primary flex-1"
          disabled={busy || sent}
        >
          {t("forgot.submit")}
        </button>
        <button type="button" className="dialog-secondary" onClick={onBack}>
          {t("forgot.back")}
        </button>
      </div>
    </form>
  );
}
