import { useState } from "react";
import type { User } from "../types/api";
import { UserAvatar } from "./UserAvatar";
import { useI18n } from "../hooks/useI18n";

interface ProfileGateProps {
  users: User[];
  onSelect: (id: string) => void;
  /** Crea un perfil nuevo; devuelve `false` si el backend no responde. */
  onCreate: (name: string) => Promise<boolean>;
}

/**
 * Puerta de perfil al arrancar la app en un navegador donde no hay ningún
 * usuario definido (sin cookie recordada y varios perfiles, o ningún perfil
 * todavía). No se puede cerrar: el alumno elige un perfil existente o crea uno
 * nuevo; hasta entonces no tiene sentido abrir el resto de la app (todo cuelga
 * de `userId`).
 */
export function ProfileGate({ users, onSelect, onCreate }: ProfileGateProps) {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  async function submit() {
    const trimmed = name.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(false);
    const ok = await onCreate(trimmed);
    setBusy(false);
    if (!ok) setError(true); // si ok, el perfil se crea y auto-selecciona
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
