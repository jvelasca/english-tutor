import { useState } from "react";
import type { User } from "../types/api";
import { UserAvatar } from "./UserAvatar";
import { useI18n } from "../hooks/useI18n";
import { isValidPin, sanitizePinInput } from "../utils/pin";

interface ProfileGateProps {
  users: User[];
  onSelect: (id: string) => void;
  /** Crea un perfil nuevo; devuelve `false` si el backend no responde. */
  onCreate: (name: string) => Promise<boolean>;
  /**
   * V3.76: perfil que está esperando su PIN. Si viene, la puerta muestra el paso
   * de PIN en lugar de la lista. `null`/ausente = puerta normal.
   */
  pinUser?: User | null;
  /** Qué decir cuando el PIN no cuadra o el freno está activo. */
  pinFeedback?: "pin-invalid" | "pin-throttled" | null;
  /** Abre sesión con el PIN tecleado. `false` = sigue en la puerta. */
  onSubmitPin?: (userId: string, pin: string) => Promise<boolean>;
  /** Vuelve a la lista de perfiles (o cierra la puerta si ya hay perfil activo). */
  onCancelPin?: () => void;
}

/**
 * Puerta de perfil al arrancar la app en un navegador donde no hay ningún
 * usuario definido (sin sesión abierta y varios perfiles, o ningún perfil
 * todavía). No se puede cerrar: el alumno elige un perfil existente o crea uno
 * nuevo —y con ello se abre la sesión en el servidor—; hasta entonces no tiene
 * sentido abrir el resto de la app (todo cuelga del perfil activo).
 *
 * V3.76: si el perfil elegido tiene PIN, la puerta se queda en el **paso de
 * PIN**. Quién lo pide es el **servidor** (401 `PIN_REQUIRED`), no una
 * suposición del cliente: la lista puede estar desactualizada y `has_pin` solo
 * se usa para no lanzar un `POST` condenado en el arranque automático.
 */
export function ProfileGate({
  users,
  onSelect,
  onCreate,
  pinUser = null,
  pinFeedback = null,
  onSubmitPin,
  onCancelPin,
}: ProfileGateProps) {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [pin, setPin] = useState("");
  const [pinBusy, setPinBusy] = useState(false);

  async function submit() {
    const trimmed = name.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(false);
    const ok = await onCreate(trimmed);
    setBusy(false);
    if (!ok) setError(true); // si ok, el perfil se crea y auto-selecciona
  }

  async function submitPin() {
    if (!pinUser || pinBusy || !isValidPin(pin)) return;
    setPinBusy(true);
    await onSubmitPin?.(pinUser.id, pin);
    // Si el PIN es correcto, la puerta se desmonta y este estado no vuelve a
    // pintarse; si no, el feedback llega por `pinFeedback` y aquí se puede
    // volver a intentar.
    setPinBusy(false);
    setPin("");
  }

  if (pinUser) {
    const pinError =
      pinFeedback === "pin-invalid"
        ? t("pin.invalid")
        : pinFeedback === "pin-throttled"
          ? t("pin.throttled")
          : null;
    return (
      <div className="dialog-backdrop" role="presentation">
        <div
          className="dialog dialog--profile-gate"
          role="dialog"
          aria-modal="true"
          aria-label={t("pin.title")}
        >
          <div className="dialog-body">
            <div className="flex flex-col items-center gap-2 text-center">
              <UserAvatar user={pinUser} size={56} />
              <h2 className="mt-2 text-xl font-bold tracking-tight text-foreground">
                {t("pin.title")}
              </h2>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {t("pin.prompt")}
              </p>
              <p className="text-sm font-medium text-foreground">{pinUser.name}</p>
            </div>

            <form
              className="flex flex-col gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                void submitPin();
              }}
            >
              <label htmlFor="profile-gate-pin" className="field-label">
                {t("pin.label")}
              </label>
              <div className="flex gap-2">
                <input
                  id="profile-gate-pin"
                  className="field-input min-w-0 flex-1"
                  type="password"
                  inputMode="numeric"
                  autoComplete="off"
                  value={pin}
                  onChange={(e) => setPin(sanitizePinInput(e.target.value))}
                  aria-label={t("pin.label")}
                  autoFocus
                  disabled={pinBusy}
                />
                <button
                  type="submit"
                  className="dialog-primary"
                  disabled={!isValidPin(pin) || pinBusy}
                >
                  {t("pin.submit")}
                </button>
              </div>
            </form>

            {pinError && <p className="dialog-error">{pinError}</p>}

            <button type="button" className="dialog-secondary" onClick={onCancelPin}>
              {t("pin.back")}
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

          {users.length > 0 ? (
            <div
              className="user-menu-list"
              role="listbox"
              aria-label={t("user.profiles")}
            >
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

          <form
            className="flex flex-col gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
          >
            <label htmlFor="profile-gate-name" className="field-label">
              {t("user.newProfile")}
            </label>
            <div className="flex gap-2">
              <input
                id="profile-gate-name"
                className="field-input min-w-0 flex-1"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setError(false);
                }}
                placeholder={t("user.name")}
                autoFocus
                disabled={busy}
                aria-label={t("user.name")}
              />
              <button
                type="submit"
                className="dialog-primary"
                disabled={!name.trim() || busy}
              >
                {t("user.createProfile")}
              </button>
            </div>
          </form>

          {error && <p className="dialog-error">{t("user.createError")}</p>}
        </div>
      </div>
    </div>
  );
}
