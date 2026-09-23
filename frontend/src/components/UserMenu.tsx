import { useEffect, useRef, useState } from "react";
import type { User } from "../types/api";
import type { UserPatch } from "../api/users";
import type {
  ProfileRequestFailure,
  ProfileRequestOutcome,
} from "../api/profileRequests";
import { ProfileDialog } from "./ProfileDialog";
import { UserAvatar } from "./UserAvatar";
import { useI18n } from "../hooks/useI18n";

interface UserMenuProps {
  users: User[];
  currentUserId: string | null;
  onSelect: (id: string) => void;
  /**
   * V3.77: **pide** una cuenta (ya no la crea). El menú cuenta el desenlace en el
   * propio desplegable porque no hay otra pantalla donde contarlo.
   */
  onRequest: (name: string) => Promise<ProfileRequestOutcome>;
  onEdit: (id: string, patch: UserPatch) => Promise<User | null>;
  /** Pedir la baja de la cuenta de la sesión (el webmaster la resuelve). */
  onRequestDelete?: (note: string) => Promise<ProfileRequestOutcome>;
  /** V3.81: abre el diálogo de cuenta (contraseña, email, baja y Salir). */
  onOpenAccount?: () => void;
}
export function UserMenu({
  users,
  currentUserId,
  onSelect,
  onRequest,
  onEdit,
  onRequestDelete,
  onOpenAccount,
}: UserMenuProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [requested, setRequested] = useState(false);
  const [failure, setFailure] = useState<ProfileRequestFailure | null>(null);
  const [editing, setEditing] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const current = users.find((u) => u.id === currentUserId) ?? null;

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [open]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        setAdding(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function submit() {
    const trimmed = name.trim();
    if (!trimmed) return;
    setFailure(null);
    const outcome = await onRequest(trimmed);
    if (outcome.ok) {
      // Pedido, no creado: se dice a quién le toca ahora, en vez de dejar el
      // desplegable como si el perfil ya existiera.
      setRequested(true);
      setName("");
      return;
    }
    setFailure(outcome.reason);
  }

  return (
    <div className="user-menu" ref={rootRef}>
      <button
        type="button"
        className="user-menu-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        title={t("user.profileTitle")}
      >
        {current ? (
          <UserAvatar user={current} size={44} />
        ) : (
          <span
            className="user-avatar user-avatar--placeholder"
            style={{ width: 44, height: 44 }}
            aria-label={t("user.profile")}
          >
            ?
          </span>
        )}
        <span className="user-menu-name">{current?.name ?? t("user.profile")}</span>
        <ChevronIcon />
      </button>

      {open && (
        <div className="user-menu-pop" role="menu">
          <div className="user-menu-title">{t("user.profiles")}</div>
          <div className="user-menu-list">
            {users.map((u) => (
              <button
                key={u.id}
                type="button"
                role="menuitem"
                className={`user-menu-item${u.id === currentUserId ? " active" : ""}`}
                onClick={() => {
                  onSelect(u.id);
                  setOpen(false);
                }}
              >
                <UserAvatar user={u} size={26} />
                <span>{u.name}</span>
              </button>
            ))}
          </div>

          {adding ? (
            <div className="user-menu-add">
              <input
                className="field-input"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setFailure(null);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void submit();
                  if (e.key === "Escape") setAdding(false);
                }}
                placeholder={t("user.name")}
                autoFocus
                disabled={requested}
                aria-label={t("user.name")}
              />
              <button
                type="button"
                className="dialog-primary"
                onClick={() => void submit()}
                disabled={!name.trim() || requested}
              >
                {t("user.requestProfile")}
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="user-menu-action"
              onClick={() => {
                setAdding(true);
                setRequested(false);
                setFailure(null);
              }}
            >
              + {t("user.requestProfile")}
            </button>
          )}

          {failure && (
            <p className="user-menu-note user-menu-note--error">
              {t(requestErrorKey(failure))}
            </p>
          )}
          {requested && (
            <p className="user-menu-note">{t("user.requestSent")}</p>
          )}

          <button
            type="button"
            className="user-menu-action"
            disabled={!current}
            onClick={() => {
              setEditing(true);
              setOpen(false);
            }}
          >
            {t("user.editProfile")}
          </button>

          {/* V3.81: la cuenta. Sustituye a la pestaña «PIN» de Ajustes, que
              desaparece: contraseña, email, verificación, baja y Salir son cosas
              de identidad y viven donde vive la identidad (el propio usuario). */}
          {onOpenAccount && (
            <button
              type="button"
              className="user-menu-action"
              disabled={!current}
              onClick={() => {
                onOpenAccount();
                setOpen(false);
              }}
            >
              {t("account.title")}
            </button>
          )}
        </div>
      )}

      {editing && current && (
        <ProfileDialog
          user={current}
          onClose={() => setEditing(false)}
          onSave={(patch) => onEdit(current.id, patch)}
          {...(onRequestDelete ? { onRequestDelete } : {})}
        />
      )}
    </div>
  );
}

/** Qué decir ante cada desenlace fallido de la petición (mismo criterio que la puerta). */
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

function ChevronIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}
