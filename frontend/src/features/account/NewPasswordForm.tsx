import { useState } from "react";
import { isPlausiblePassword } from "../../utils/credentials";
import { useI18n } from "../../hooks/useI18n";
import { AccountNotice } from "./AccountPage";

interface NewPasswordFormProps {
  submitLabel: string;
  /**
   * Guarda la contraseña. Devuelve la **clave i18n** del error, o `null` si fue
   * bien. Devuelve una clave y no un texto para que las frases sigan viviendo
   * todas en `utils/i18n.ts` (y para que el test de paridad las vigile).
   */
  onSubmit: (password: string) => Promise<string | null>;
  autoFocus?: boolean;
}

/**
 * Contraseña nueva + repetición (V3.82), compartido por la activación y el
 * restablecimiento.
 *
 * La forma se valida aquí con el espejo de la política del backend
 * (`utils/credentials.ts`): no es seguridad, es no mandar una petición que el
 * servidor va a rechazar y poder decir «mínimo 8 caracteres» en un sitio.
 */
export function NewPasswordForm({
  submitLabel,
  onSubmit,
  autoFocus = true,
}: NewPasswordFormProps) {
  const { t } = useI18n();
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (busy) return;
    setError(null);
    if (!isPlausiblePassword(password)) {
      setError(t("account.passwordFormat"));
      return;
    }
    if (password !== repeat) {
      setError(t("activate.passwordMismatch"));
      return;
    }
    setBusy(true);
    const failure = await onSubmit(password);
    setBusy(false);
    if (failure) setError(t(failure));
  }

  return (
    <form
      className="flex flex-col gap-2"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <label htmlFor="new-password" className="field-label">
        {t("account.newPassword")}
      </label>
      <input
        id="new-password"
        className="field-input"
        type="password"
        autoComplete="new-password"
        value={password}
        onChange={(e) => {
          setPassword(e.target.value);
          setError(null);
        }}
        aria-label={t("account.newPassword")}
        autoFocus={autoFocus}
        disabled={busy}
      />
      <label htmlFor="new-password-repeat" className="field-label">
        {t("user.passwordRepeat")}
      </label>
      <input
        id="new-password-repeat"
        className="field-input"
        type="password"
        autoComplete="new-password"
        value={repeat}
        onChange={(e) => {
          setRepeat(e.target.value);
          setError(null);
        }}
        aria-label={t("user.passwordRepeat")}
        disabled={busy}
      />

      {error && <AccountNotice tone="error">{error}</AccountNotice>}

      <button
        type="submit"
        className="dialog-primary"
        disabled={busy || !password || !repeat}
      >
        {submitLabel}
      </button>

      <p className="text-xs leading-relaxed text-muted-foreground">
        {t("user.passwordHint")}
      </p>
    </form>
  );
}
