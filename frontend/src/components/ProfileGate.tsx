import { useState } from "react";
import type {
  ProfileRequestOutcome,
  RequestedAvatar,
} from "../api/profileRequests";
import type { LoginOutcome } from "../hooks/useChat";
import { useI18n } from "../hooks/useI18n";
import { ForgotPasswordForm } from "./ForgotPasswordForm";
import { RequestAccessForm } from "./RequestAccessForm";

type GateMode = "login" | "request" | "forgot";

interface ProfileGateProps {
  /**
   * Abre sesión con email + contraseña (V3.82). Es el **único** camino de
   * entrada: ya no hay lista de cuentas que elegir.
   */
  onLogin: (email: string, password: string) => Promise<LoginOutcome>;
  /** Pide una cuenta nueva. No la crea: la autoriza el webmaster. */
  onRequest: (
    name: string,
    email: string,
    avatar: RequestedAvatar,
    note: string,
  ) => Promise<ProfileRequestOutcome>;
  /** Pide el enlace de restablecimiento de contraseña. */
  onForgot: (email: string) => Promise<{ sent: boolean }>;
  /**
   * V3.80.2: no se pudo **comprobar** la sesión (servidor caído, arrancando o a
   * medio responder). Se distingue de «no hay sesión» a propósito: sin esa
   * diferencia, la puerta ofrecía entrar como única acción y no había forma de
   * salir cuando lo que fallaba era la lectura.
   */
  loadFailed?: boolean;
  /** Vuelve a comprobar la sesión sin recargar la página. */
  onRetry?: () => void;
}

/**
 * Puerta de entrada de la app (V3.82).
 *
 * V3.81 era «elige un usuario y demuestra la contraseña». V3.82 cierra ese
 * modelo: **entrar es escribir email y contraseña**, y eso hace imposible
 * nombrar a otra persona. La lista de cuentas deja de existir en la puerta —y de
 * existir para cualquiera sin sesión—, así que la app ya no enumera quién tiene
 * cuenta.
 *
 * Tres pantallas, todas aquí porque las tres son «puerta»:
 *
 * - **Entrar** (por defecto): email + contraseña.
 * - **Solicitar acceso**: nombre, email y avatar → cola del webmaster.
 * - **Recuperar contraseña**: email → enlace por correo.
 *
 * La activación y el restablecimiento **no** son modos de esta puerta: viven en
 * su propia ruta (`/cuenta/activar`, `/cuenta/restablecer`) porque el enlace del
 * correo puede abrirse en otro navegador, sin sesión y sin pasar por aquí.
 */
export function ProfileGate({
  onLogin,
  onRequest,
  onForgot,
  loadFailed = false,
  onRetry,
}: ProfileGateProps) {
  const { t } = useI18n();
  const [mode, setMode] = useState<GateMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  async function submitLogin() {
    if (busy || !email.trim() || !password) return;
    setBusy(true);
    setFeedback(null);
    const outcome = await onLogin(email, password);
    setBusy(false);
    setPassword("");
    if (outcome.ok) return; // la app entra: la puerta se desmonta
    setFeedback(t(loginErrorKey(outcome.reason)));
  }

  function go(next: GateMode) {
    setMode(next);
    setFeedback(null);
  }

  const title =
    mode === "request"
      ? t("request.title")
      : mode === "forgot"
        ? t("forgot.title")
        : t("password.title");

  return (
    <div className="dialog-backdrop" role="presentation">
      <div
        className="dialog dialog--profile-gate"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="dialog-body">
          <div className="flex flex-col items-center gap-2 text-center">
            <span className="grid size-16 place-items-center rounded-2xl bg-gradient-to-br from-primary to-[var(--color-accent-2)] text-2xl font-bold text-primary-foreground shadow-sm">
              EN
            </span>
            <h2 className="mt-2 text-xl font-bold tracking-tight text-foreground">
              {title}
            </h2>
            {mode === "login" && (
              <p className="text-sm leading-relaxed text-muted-foreground">
                {t("password.prompt")}
              </p>
            )}
          </div>

          {loadFailed ? (
            // No es lo mismo «no hay sesión» que «no se pudo comprobar».
            <div className="flex flex-col items-center gap-2">
              <p
                className="rounded-md border border-border bg-muted px-3 py-2 text-center text-sm text-muted-foreground"
                role="alert"
              >
                {t("user.loadFailed")}
              </p>
              <button type="button" className="dialog-secondary" onClick={onRetry}>
                {t("common.retry")}
              </button>
            </div>
          ) : mode === "request" ? (
            <RequestAccessForm onRequest={onRequest} onBack={() => go("login")} />
          ) : mode === "forgot" ? (
            <ForgotPasswordForm onForgot={onForgot} onBack={() => go("login")} />
          ) : (
            <form
              className="flex flex-col gap-2"
              // `noValidate` deliberado (mismo criterio que el resto de la app):
              // la validación de forma la hace la app, en su idioma, y un globito
              // nativo cancelando el envío no se puede probar ni traducir.
              noValidate
              onSubmit={(e) => {
                e.preventDefault();
                void submitLogin();
              }}
            >
              <label htmlFor="gate-email" className="field-label">
                {t("user.email")}
              </label>
              <input
                id="gate-email"
                className="field-input"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setFeedback(null);
                }}
                aria-label={t("user.email")}
                autoFocus
                disabled={busy}
              />
              <label htmlFor="gate-password" className="field-label">
                {t("password.label")}
              </label>
              <input
                id="gate-password"
                className="field-input"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  setFeedback(null);
                }}
                aria-label={t("password.label")}
                disabled={busy}
              />
              {feedback && (
                <p className="dialog-error" role="alert">
                  {feedback}
                </p>
              )}
              <button
                type="submit"
                className="dialog-primary"
                disabled={busy || !email.trim() || !password}
              >
                {t("password.submit")}
              </button>

              <div className="flex flex-col items-center gap-1 pt-1">
                <button
                  type="button"
                  className="dialog-link"
                  onClick={() => go("request")}
                >
                  {t("user.createAccount")}
                </button>
                <button
                  type="button"
                  className="dialog-link"
                  onClick={() => go("forgot")}
                >
                  {t("user.forgotPassword")}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Qué decir cuando el intento de entrada no cuaja. Se traduce a una clave de i18n
 * y no a texto aquí dentro: las frases viven todas en `utils/i18n.ts`.
 *
 * El caso `invalid-credentials` junta «ese email no existe» y «esa contraseña no
 * es» **a propósito**: el backend no los distingue para no servir de oráculo de
 * qué correos tienen cuenta, y decir aquí «ese email no existe» sería deshacer
 * esa decisión en la última capa.
 */
function loginErrorKey(reason: string): string {
  switch (reason) {
    case "not-activated":
      return "password.notActivated";
    case "disabled":
      return "password.disabled";
    case "unenrolled":
      return "password.unenrolled";
    case "throttled":
      return "password.throttled";
    case "error":
      return "account.error";
    default:
      return "password.invalid";
  }
}
