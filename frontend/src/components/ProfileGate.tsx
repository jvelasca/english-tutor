import { useState } from "react";
import type { User } from "../types/api";
import type {
  ProfileRequestFailure,
  ProfileRequestOutcome,
} from "../api/profileRequests";
import { UserAvatar } from "./UserAvatar";
import { useI18n } from "../hooks/useI18n";
import {
  isPlausibleEmail,
  isPlausiblePassword,
} from "../utils/credentials";
import type { CreateAccountOutcome } from "../hooks/useChat";

interface ProfileGateProps {
  users: User[];
  onSelect: (id: string) => void;
  /**
   * V3.77: **pide** una cuenta nueva (no la crea). Devuelve el desenlace para que
   * la puerta pueda decir qué pasó: quien pide una cuenta puede no tener ninguna
   * todavía, así que la pantalla es su único canal. Sigue existiendo en V3.81
   * porque es la vía de la **LAN**, donde el registro abierto está cerrado a
   * propósito.
   */
  onRequest: (name: string) => Promise<ProfileRequestOutcome>;
  /**
   * V3.81: **registro** de una cuenta nueva desde el propio equipo (nombre, email
   * y contraseña). Sustituye al «pide un perfil» como camino principal: en el
   * equipo de casa cualquiera puede crear su cuenta y empezar.
   */
  onCreateAccount?: (
    name: string,
    email: string,
    password: string,
  ) => Promise<CreateAccountOutcome>;
  /**
   * ¿Este navegador está en el propio equipo? Lo decide el host de la página, no
   * una suposición: el backend cierra el registro fuera de loopback, así que
   * ofrecer el formulario desde la LAN sería ofrecer un botón que da 403.
   */
  canCreateAccount?: boolean;
  /**
   * V3.81: cuenta que está esperando su contraseña. Si viene, la puerta muestra el
   * paso de contraseña en lugar de la lista. `null`/ausente = puerta normal.
   */
  passwordUser?: User | null;
  /** Qué decir cuando la contraseña no cuadra o el freno está activo. */
  passwordFeedback?: "password-invalid" | "password-throttled" | null;
  /** Abre sesión con la contraseña tecleada. `false` = sigue en la puerta. */
  onSubmitPassword?: (userId: string, password: string) => Promise<boolean>;
  /** Vuelve a la lista de cuentas (o cierra la puerta si ya hay cuenta activa). */
  onCancelPassword?: () => void;
  /**
   * V3.80.2: la lista de usuarios no se pudo leer (servidor caído, arrancando o
   * a medio responder). Se distingue de «no hay usuarios» a propósito: sin esa
   * diferencia, la puerta ofrecía pedir una cuenta como única acción y no había
   * forma de salir cuando lo que fallaba era la lectura.
   */
  loadFailed?: boolean;
  /** Vuelve a pedir la lista (y la sesión) sin recargar la página. */
  onRetry?: () => void;
}

/**
 * Puerta de entrada al arrancar la app en un navegador sin sesión abierta (varias
 * cuentas y ninguna elegida, o ninguna todavía). No se puede cerrar: el alumno
 * elige una cuenta, entra en la suya o crea una nueva; hasta entonces no tiene
 * sentido abrir el resto de la app (todo cuelga de la cuenta activa).
 *
 * V3.81: la puerta deja de ser «elige un nombre». Tres pasos posibles, y los tres
 * conviven porque las tres situaciones son reales:
 *
 * - **Elegir** una cuenta existente (y demostrar la contraseña si la tiene).
 * - **Crear** una cuenta desde este equipo (nombre, email, contraseña).
 * - **Pedir** una cuenta, que es la vía de la LAN: desde otro dispositivo no se
 *   crea nada, se deja una solicitud que el webmaster aprueba.
 *
 * Quién pide la contraseña es el **servidor** (401 `PASSWORD_REQUIRED`), no una
 * suposición del cliente: la lista puede estar desactualizada y `has_password` solo
 * se usa para no lanzar un `POST` condenado en el arranque automático.
 */
export function ProfileGate({
  users,
  onSelect,
  onRequest,
  onCreateAccount,
  canCreateAccount = false,
  passwordUser = null,
  passwordFeedback = null,
  onSubmitPassword,
  onCancelPassword,
  loadFailed = false,
  onRetry,
}: ProfileGateProps) {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<ProfileRequestFailure | null>(null);
  const [requested, setRequested] = useState(false);
  const [password, setPassword] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);
  // V3.81: el alta es un paso aparte de la lista, no un formulario permanente: en
  // una casa con cuentas ya hechas, «crear cuenta» es la excepción y no debe
  // competir visualmente con elegir la tuya.
  const [creating, setCreating] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPassword2, setNewPassword2] = useState("");
  const [createFeedback, setCreateFeedback] = useState<string | null>(null);
  const [forgot, setForgot] = useState(false);

  async function submitRequest() {
    const trimmed = name.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setFailure(null);
    const outcome = await onRequest(trimmed);
    setBusy(false);
    if (outcome.ok) {
      // Pedido, no creado: no hay cuenta a la que abrir sesión, así que la puerta
      // se queda y cuenta lo que falta (que el webmaster lo autorice).
      setRequested(true);
      return;
    }
    setFailure(outcome.reason);
  }

  async function submitPassword() {
    if (!passwordUser || passwordBusy || !password) return;
    setPasswordBusy(true);
    await onSubmitPassword?.(passwordUser.id, password);
    // Si la contraseña es correcta, la puerta se desmonta y este estado no vuelve
    // a pintarse; si no, el feedback llega por `passwordFeedback`.
    setPasswordBusy(false);
    setPassword("");
  }

  async function submitCreate() {
    if (!onCreateAccount || busy) return;
    const trimmedName = name.trim();
    if (!trimmedName) {
      setCreateFeedback(t("user.requestInvalid"));
      return;
    }
    if (!isPlausibleEmail(newEmail)) {
      setCreateFeedback(t("account.emailFormat"));
      return;
    }
    if (!isPlausiblePassword(newPassword)) {
      setCreateFeedback(t("user.passwordHint"));
      return;
    }
    if (newPassword !== newPassword2) {
      setCreateFeedback(t("user.passwordMismatch"));
      return;
    }
    setBusy(true);
    setCreateFeedback(null);
    const outcome = await onCreateAccount(trimmedName, newEmail, newPassword);
    setBusy(false);
    if (outcome.ok) return; // la app entra: la puerta se desmonta
    setCreateFeedback(t(createAccountErrorKey(outcome.reason)));
  }

  if (passwordUser) {
    const passwordError =
      passwordFeedback === "password-invalid"
        ? t("password.invalid")
        : passwordFeedback === "password-throttled"
          ? t("password.throttled")
          : null;
    return (
      <div className="dialog-backdrop" role="presentation">
        <div
          className="dialog dialog--profile-gate"
          role="dialog"
          aria-modal="true"
          aria-label={t("password.title")}
        >
          <div className="dialog-body">
            <div className="flex flex-col items-center gap-2 text-center">
              <UserAvatar user={passwordUser} size={56} />
              <h2 className="mt-2 text-xl font-bold tracking-tight text-foreground">
                {t("password.title")}
              </h2>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {t("password.prompt")}
              </p>
              <p className="text-sm font-medium text-foreground">
                {passwordUser.name}
              </p>
            </div>

            <form
              className="flex flex-col gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                void submitPassword();
              }}
            >
              <label htmlFor="profile-gate-password" className="field-label">
                {t("password.label")}
              </label>
              <div className="flex gap-2">
                <input
                  id="profile-gate-password"
                  className="field-input min-w-0 flex-1"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  aria-label={t("password.label")}
                  autoFocus
                  disabled={passwordBusy}
                />
                <button
                  type="submit"
                  className="dialog-primary"
                  disabled={!password || passwordBusy}
                >
                  {t("password.submit")}
                </button>
              </div>
            </form>

            {passwordError && <p className="dialog-error">{passwordError}</p>}

            <p className="text-xs leading-relaxed text-muted-foreground">
              {t("user.forgotPasswordHint")}
            </p>

            <button
              type="button"
              className="dialog-secondary"
              onClick={onCancelPassword}
            >
              {t("password.back")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="dialog-backdrop" role="presentation">
      <div
        className="dialog dialog--profile-gate"
        role="dialog"
        aria-modal="true"
        aria-label={t("user.chooseTitle")}
      >
        <div className="dialog-body">
          <div className="flex flex-col items-center gap-2 text-center">
            <span className="grid size-16 place-items-center rounded-2xl bg-gradient-to-br from-primary to-[var(--color-accent-2)] text-2xl font-bold text-primary-foreground shadow-sm">
              EN
            </span>
            <h2 className="mt-2 text-xl font-bold tracking-tight text-foreground">
              {t("user.chooseTitle")}
            </h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              {t("user.choosePrompt")}
            </p>
          </div>

          {loadFailed ? (
            // V3.80.2: no es lo mismo «no hay usuarios» que «no se pudieron
            // leer». Con la lista ilegible, pedir una cuenta es un camino pero no
            // una salida, así que la puerta ofrece volver a intentarlo en el
            // sitio (el arranque de la app se lo merece: un servidor que tarda
            // dos segundos de más no debe dejar al alumno atrapado).
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
          ) : users.length > 0 ? (
            <div className="user-menu-list" role="listbox" aria-label={t("user.profiles")}>
              {users.map((u) => (
                <button
                  key={u.id}
                  type="button"
                  role="option"
                  className="user-menu-item"
                  onClick={() => onSelect(u.id)}
                >
                  <UserAvatar user={u} size={34} />
                  <span className="text-sm font-medium text-foreground">
                    {u.name}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p className="rounded-md border border-border bg-muted px-3 py-2 text-center text-sm text-muted-foreground">
              {t("user.noProfilesYet")}
            </p>
          )}

          {creating ? (
            // Alta en el propio equipo (V3.81). Aquí sí se pide contraseña: es el
            // único momento en que la app la elige, y el email sirve para
            // verificar la cuenta después.
            //
            // `noValidate` es deliberado: con el `type="email"` puesto, el
            // navegador aplica su validación nativa y **cancela el envío** antes
            // de que se ejecute nuestro `onSubmit`, así que un email con mala pinta
            // no se validaría con el mensaje de la app sino con el globito del
            // navegador (y en jsdom, que también valida, el formulario ni
            // enviaría). La validación de forma se hace aquí, en un solo sitio y en
            // el idioma de la app; el `type` se queda por el teclado del móvil.
            <form
              className="flex flex-col gap-2"
              noValidate
              onSubmit={(e) => {
                e.preventDefault();
                void submitCreate();
              }}
            >
              <label htmlFor="profile-gate-new-name" className="field-label">
                {t("user.createAccount")}
              </label>
              <input
                id="profile-gate-new-name"
                className="field-input"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setCreateFeedback(null);
                }}
                placeholder={t("user.name")}
                aria-label={t("user.name")}
                autoFocus
                disabled={busy}
              />
              <input
                className="field-input"
                type="email"
                autoComplete="email"
                value={newEmail}
                onChange={(e) => {
                  setNewEmail(e.target.value);
                  setCreateFeedback(null);
                }}
                placeholder={t("user.email")}
                aria-label={t("user.email")}
                disabled={busy}
              />
              <input
                className="field-input"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => {
                  setNewPassword(e.target.value);
                  setCreateFeedback(null);
                }}
                placeholder={t("user.password")}
                aria-label={t("user.password")}
                disabled={busy}
              />
              <input
                className="field-input"
                type="password"
                autoComplete="new-password"
                value={newPassword2}
                onChange={(e) => {
                  setNewPassword2(e.target.value);
                  setCreateFeedback(null);
                }}
                placeholder={t("user.passwordRepeat")}
                aria-label={t("user.passwordRepeat")}
                disabled={busy}
              />
              <div className="flex gap-2">
                <button
                  type="submit"
                  className="dialog-primary flex-1"
                  disabled={busy}
                >
                  {t("user.createAccount")}
                </button>
                <button
                  type="button"
                  className="dialog-secondary"
                  onClick={() => {
                    setCreating(false);
                    setCreateFeedback(null);
                  }}
                  disabled={busy}
                >
                  {t("user.backToUsers")}
                </button>
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {t("user.passwordHint")} {t("user.emailHint")}
              </p>
            </form>
          ) : (
            <>
              {canCreateAccount && onCreateAccount && (
                <button
                  type="button"
                  className="dialog-primary"
                  onClick={() => {
                    setCreating(true);
                    setForgot(false);
                  }}
                >
                  {t("user.createAccount")}
                </button>
              )}

              {/* La vía de la LAN: desde otro dispositivo no se crea nada, se
                  pide. En el equipo se ofrece igual porque sigue siendo la forma
                  de pedir una cuenta a nombre de otra persona. */}
              <form
                className="flex flex-col gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  void submitRequest();
                }}
              >
                <label htmlFor="profile-gate-name" className="field-label">
                  {t("user.requestProfile")}
                </label>
                <div className="flex gap-2">
                  <input
                    id="profile-gate-name"
                    className="field-input min-w-0 flex-1"
                    value={name}
                    onChange={(e) => {
                      setName(e.target.value);
                      setFailure(null);
                    }}
                    placeholder={t("user.name")}
                    disabled={busy || requested}
                    aria-label={t("user.name")}
                  />
                  <button
                    type="submit"
                    className="dialog-primary"
                    disabled={!name.trim() || busy || requested}
                  >
                    {t("user.requestProfile")}
                  </button>
                </div>
              </form>

              {failure && <p className="dialog-error">{t(requestErrorKey(failure))}</p>}

              {requested && (
                <p className="rounded-md border border-border bg-muted px-3 py-2 text-sm leading-relaxed text-muted-foreground">
                  {t("user.requestSent")}
                </p>
              )}

              {!requested && (
                <p className="text-xs leading-relaxed text-muted-foreground">
                  {t("user.requestHint")}
                </p>
              )}

              <button
                type="button"
                className="dialog-secondary"
                onClick={() => setForgot((v) => !v)}
                aria-expanded={forgot}
              >
                {t("user.forgotPassword")}
              </button>
              {forgot && (
                <p className="text-xs leading-relaxed text-muted-foreground">
                  {t("user.forgotPasswordHint")}
                </p>
              )}
            </>
          )}

          {createFeedback && <p className="dialog-error">{createFeedback}</p>}
        </div>
      </div>
    </div>
  );
}

/**
 * Qué decir ante cada desenlace fallido. Se traduce a una clave de i18n y no a
 * texto aquí dentro: las frases viven todas en `utils/i18n.ts`, que es donde se
 * revisan juntas y donde el test de paridad las vigila.
 */
function requestErrorKey(failure: ProfileRequestFailure): string {
  switch (failure) {
    case "duplicate":
      return "user.requestDuplicate";
    case "full":
      return "user.requestFull";
    case "throttled":
      return "errors.rateLimited";
    case "invalid":
      return "user.requestInvalid";
    default:
      return "user.requestError";
  }
}

/** Lo mismo para el alta de una cuenta nueva. */
function createAccountErrorKey(
  reason: Extract<CreateAccountOutcome, { ok: false }>["reason"],
): string {
  switch (reason) {
    case "name-taken":
      return "account.nameTaken";
    case "email-taken":
      return "account.emailTaken";
    case "email-format":
      return "account.emailFormat";
    case "password-format":
      return "account.passwordFormat";
    case "not-local":
      return "user.requestHint";
    default:
      return "account.error";
  }
}
