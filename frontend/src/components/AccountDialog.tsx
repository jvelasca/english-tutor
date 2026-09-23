import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import type { User } from "../types/api";
import type { AccountActionOutcome } from "../hooks/useChat";
import { UserAvatar } from "./UserAvatar";
import { useI18n } from "../hooks/useI18n";
import {
  isPlausibleEmail,
  isPlausiblePassword,
} from "../utils/credentials";

interface AccountDialogProps {
  user: User;
  onClose: () => void;
  /**
   * V3.81: la contraseña vigente es **temporal** (la puso el webmaster). El
   * diálogo se abre directamente en «cambiar contraseña» y no se puede cerrar:
   * una contraseña temporal que sobrevive al primer acceso deja de ser temporal,
   * y el servidor lo hace cumplir igual con `403 PASSWORD_CHANGE_REQUIRED`.
   */
  forced?: boolean;
  /** Cambia la contraseña. `current` solo hace falta si ya tenía una. */
  onChangePassword: (
    current: string | null,
    next: string,
  ) => Promise<AccountActionOutcome>;
  /** Cambia el email (exige la contraseña: la re-autenticación es deliberada). */
  onChangeEmail: (password: string, email: string) => Promise<AccountActionOutcome>;
  /** Reenvía la verificación. `true` = salió el correo; `false` = no hay SMTP. */
  onResendVerification: () => Promise<boolean>;
  /**
   * Baja autoservicio: cierra la cuenta **sin borrar nada**. El borrado definitivo
   * es de la consola de gestión, con copia previa y confirmación por nombre.
   */
  onUnenroll: (password: string) => Promise<AccountActionOutcome>;
  /** Salir: cierra la sesión y vuelve a la puerta. */
  onSignOut: () => void;
}

/**
 * Diálogo de cuenta (V3.81): lo que el alumno puede hacer con la suya.
 *
 * Es deliberadamente aburrido y en secciones, porque cada sección es una decisión
 * distinta y las tres se pisan: cambiar la contraseña tumba las sesiones abiertas,
 * cambiar el email **reinicia** la verificación, y darse de baja no borra nada.
 * Mezclarlas en un formulario único haría que un cambio de email pareciera un
 * cambio de contraseña.
 *
 * Exige la contraseña en las tres acciones destructivas o de identidad. No es
 * ceremonia: un equipo de casa con la sesión abierta no debe bastar para quedarse
 * una cuenta ni para darla de baja. `has_password` decide si se pide: las cuentas
 * heredadas sin credencial todavía pueden cambiar la suya **poniéndola** por
 * primera vez, que es justo lo que se quiere de ellas.
 */
export function AccountDialog({
  user,
  onClose,
  forced = false,
  onChangePassword,
  onChangeEmail,
  onResendVerification,
  onUnenroll,
  onSignOut,
}: AccountDialogProps) {
  const { t } = useI18n();
  const hasPassword = user.has_password === true;
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [passwordMsg, setPasswordMsg] = useState<string | null>(null);
  const [emailPassword, setEmailPassword] = useState("");
  const [newEmail, setNewEmail] = useState(user.email ?? "");
  const [emailBusy, setEmailBusy] = useState(false);
  const [emailMsg, setEmailMsg] = useState<string | null>(null);
  const [resendBusy, setResendBusy] = useState(false);
  const [unenrollPassword, setUnenrollPassword] = useState("");
  const [unenrollOpen, setUnenrollOpen] = useState(false);
  const [unenrollBusy, setUnenrollBusy] = useState(false);
  const [unenrollMsg, setUnenrollMsg] = useState<string | null>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // Con cambio de contraseña forzado no hay Escape: la salida es cambiarla (o
      // «Salir», que también está en el diálogo y cierra la sesión entera).
      if (e.key === "Escape" && !forced) onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, forced]);

  async function submitPassword() {
    if (passwordBusy) return;
    if (hasPassword && !current) {
      setPasswordMsg(t("account.passwordRequired"));
      return;
    }
    if (!isPlausiblePassword(next)) {
      setPasswordMsg(t("account.passwordFormat"));
      return;
    }
    if (next !== repeat) {
      setPasswordMsg(t("user.passwordMismatch"));
      return;
    }
    setPasswordBusy(true);
    setPasswordMsg(null);
    const outcome = await onChangePassword(hasPassword ? current : null, next);
    setPasswordBusy(false);
    if (outcome.ok) {
      setNext("");
      setRepeat("");
      setCurrent("");
      setPasswordMsg(t("account.saved"));
      if (forced) onClose();
      return;
    }
    setPasswordMsg(t(accountErrorKey(outcome.reason)));
  }

  async function submitEmail() {
    if (emailBusy) return;
    if (!isPlausibleEmail(newEmail)) {
      setEmailMsg(t("account.emailFormat"));
      return;
    }
    if (hasPassword && !emailPassword) {
      setEmailMsg(t("account.passwordRequired"));
      return;
    }
    setEmailBusy(true);
    setEmailMsg(null);
    const outcome = await onChangeEmail(emailPassword, newEmail);
    setEmailBusy(false);
    if (outcome.ok) {
      setEmailPassword("");
      setEmailMsg(t("account.saved"));
      return;
    }
    setEmailMsg(t(accountErrorKey(outcome.reason)));
  }

  async function submitResend() {
    if (resendBusy) return;
    setResendBusy(true);
    try {
      const sent = await onResendVerification();
      setEmailMsg(sent ? t("account.verifySent") : t("account.verifyManual"));
    } catch {
      setEmailMsg(t("account.error"));
    } finally {
      setResendBusy(false);
    }
  }

  async function submitUnenroll() {
    if (unenrollBusy) return;
    if (hasPassword && !unenrollPassword) {
      setUnenrollMsg(t("account.passwordRequired"));
      return;
    }
    setUnenrollBusy(true);
    setUnenrollMsg(null);
    const outcome = await onUnenroll(unenrollPassword);
    setUnenrollBusy(false);
    if (outcome.ok) return; // la app vuelve a la puerta: este diálogo se desmonta
    setUnenrollMsg(t(accountErrorKey(outcome.reason)));
  }

  return createPortal(
    <div className="dialog-backdrop" onClick={forced ? undefined : onClose}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={t("account.title")}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="dialog-header">
          <h2>{t("account.title")}</h2>
          {!forced && (
            <button
              type="button"
              className="dialog-close flex h-10 w-10 items-center justify-center"
              onClick={onClose}
              aria-label={t("common.close")}
            >
              ×
            </button>
          )}
        </header>

        <div className="dialog-body">
          <div className="profile-preview">
            <UserAvatar user={user} size={56} />
            <div className="flex flex-col items-center gap-1 text-center">
              <span className="text-sm font-medium text-foreground">
                {user.name}
              </span>
              {user.email ? (
                <span className="text-xs text-muted-foreground">{user.email}</span>
              ) : null}
              {user.email ? (
                <span
                  className={`rounded-full border px-2 py-0.5 text-xs ${
                    user.email_verified
                      ? "border-border text-muted-foreground"
                      : "border-amber-500/50 text-amber-600 dark:text-amber-400"
                  }`}
                >
                  {user.email_verified ? t("account.ok") : t("account.unverified")}
                </span>
              ) : null}
            </div>
          </div>

          {/* Cambiar contraseña. En modo forzado es lo único que se pide. */}
          <div className="field border-t border-border pt-3">
            <span className="field-label">
              {forced ? t("account.mustChangeTitle") : t("account.changePassword")}
            </span>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {forced ? t("account.mustChangeBody") : t("user.passwordHint")}
            </p>
            {hasPassword && (
              <input
                className="field-input"
                type="password"
                autoComplete="current-password"
                value={current}
                onChange={(e) => {
                  setCurrent(e.target.value);
                  setPasswordMsg(null);
                }}
                placeholder={t("account.currentPassword")}
                aria-label={t("account.currentPassword")}
                autoFocus={forced}
              />
            )}
            <input
              className="field-input"
              type="password"
              autoComplete="new-password"
              value={next}
              onChange={(e) => {
                setNext(e.target.value);
                setPasswordMsg(null);
              }}
              placeholder={t("account.newPassword")}
              aria-label={t("account.newPassword")}
              autoFocus={!forced}
            />
            <input
              className="field-input"
              type="password"
              autoComplete="new-password"
              value={repeat}
              onChange={(e) => {
                setRepeat(e.target.value);
                setPasswordMsg(null);
              }}
              placeholder={t("user.passwordRepeat")}
              aria-label={t("user.passwordRepeat")}
            />
            {passwordMsg && (
              <p
                className={
                  passwordMsg === t("account.saved")
                    ? "text-xs text-muted-foreground"
                    : "dialog-error"
                }
                role={passwordMsg === t("account.saved") ? undefined : "alert"}
              >
                {passwordMsg}
              </p>
            )}
            <button
              type="button"
              className="dialog-primary"
              onClick={() => void submitPassword()}
              disabled={passwordBusy}
            >
              {t("account.changePassword")}
            </button>
          </div>

          {/* Solo cuando el cambio no es forzado: con contraseña temporal, esto
              es lo último que se toca. */}
          {!forced && (
            <>
              <div className="field border-t border-border pt-3">
                <span className="field-label">{t("account.changeEmail")}</span>
                {hasPassword && (
                  <input
                    className="field-input"
                    type="password"
                    autoComplete="current-password"
                    value={emailPassword}
                    onChange={(e) => {
                      setEmailPassword(e.target.value);
                      setEmailMsg(null);
                    }}
                    placeholder={t("account.currentPassword")}
                    aria-label={t("account.currentPassword")}
                  />
                )}
                <input
                  className="field-input"
                  type="email"
                  autoComplete="email"
                  value={newEmail}
                  onChange={(e) => {
                    setNewEmail(e.target.value);
                    setEmailMsg(null);
                  }}
                  placeholder={t("account.newEmail")}
                  aria-label={t("account.newEmail")}
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="dialog-primary flex-1"
                    onClick={() => void submitEmail()}
                    disabled={emailBusy}
                  >
                    {t("account.save")}
                  </button>
                  {user.email && !user.email_verified && (
                    <button
                      type="button"
                      className="dialog-secondary"
                      onClick={() => void submitResend()}
                      disabled={resendBusy}
                    >
                      {t("account.verifyResend")}
                    </button>
                  )}
                </div>
                {emailMsg && (
                  <p
                    className={
                      emailMsg === t("account.saved")
                        ? "text-xs text-muted-foreground"
                        : "dialog-error"
                    }
                    role={emailMsg === t("account.saved") ? undefined : "alert"}
                  >
                    {emailMsg}
                  </p>
                )}
              </div>

              <div className="field border-t border-border pt-3">
                <span className="field-label">{t("account.deleteSection")}</span>
                <p className="text-xs leading-relaxed text-muted-foreground">
                  {t("account.deleteExplain")}
                </p>
                {unenrollOpen ? (
                  <>
                    {hasPassword && (
                      <input
                        className="field-input"
                        type="password"
                        autoComplete="current-password"
                        value={unenrollPassword}
                        onChange={(e) => {
                          setUnenrollPassword(e.target.value);
                          setUnenrollMsg(null);
                        }}
                        placeholder={t("account.deleteConfirm")}
                        aria-label={t("account.currentPassword")}
                        autoFocus
                      />
                    )}
                    {unenrollMsg && (
                      <p className="dialog-error" role="alert">
                        {unenrollMsg}
                      </p>
                    )}
                    <div className="flex gap-2">
                      <button
                        type="button"
                        className="dialog-secondary"
                        onClick={() => void submitUnenroll()}
                        disabled={unenrollBusy}
                      >
                        {t("account.deleteButton")}
                      </button>
                      <button
                        type="button"
                        className="dialog-link"
                        onClick={() => {
                          setUnenrollOpen(false);
                          setUnenrollMsg(null);
                        }}
                        disabled={unenrollBusy}
                      >
                        {t("common.cancel")}
                      </button>
                    </div>
                  </>
                ) : (
                  <button
                    type="button"
                    className="dialog-secondary"
                    onClick={() => setUnenrollOpen(true)}
                  >
                    {t("account.deleteButton")}
                  </button>
                )}
              </div>
            </>
          )}
        </div>

        <footer className="dialog-footer">
          {!forced && (
            <button type="button" className="dialog-secondary" onClick={onClose}>
              {t("common.close")}
            </button>
          )}
          {/* «Salir» existe desde V3.81 de verdad: `closeSession()` llevaba desde
              V3.75 escrita y sin llamar, así que en un equipo compartido no había
              forma de cerrar la sesión salvo borrar las cookies. */}
          <button type="button" className="dialog-primary" onClick={onSignOut}>
            {t("account.signOut")}
          </button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}

/** Desenlace de una acción de cuenta → clave de i18n (mismo criterio que la puerta). */
function accountErrorKey(
  reason: Extract<AccountActionOutcome, { ok: false }>["reason"],
): string {
  switch (reason) {
    case "password-invalid":
      return "account.passwordInvalid";
    case "password-required":
      return "account.passwordRequired";
    case "invalid":
      return "account.emailFormat";
    default:
      return "account.error";
  }
}
