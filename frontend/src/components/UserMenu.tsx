import { useEffect, useRef, useState } from "react";
import type { User } from "../types/api";
import type { UserPatch } from "../api/users";
import { ProfileDialog } from "./ProfileDialog";
import { UserAvatar } from "./UserAvatar";
import { useI18n } from "../hooks/useI18n";

interface UserMenuProps {
  /**
   * La cuenta de la sesión, o `null` mientras no hay ninguna (el armazón se
   * pinta detrás de la puerta de entrada).
   */
  user: User | null;
  onEdit: (id: string, patch: UserPatch) => Promise<User | null>;
  /** Pedir la baja de la cuenta de la sesión (el webmaster la resuelve). */
  onRequestDelete?: (note: string) => Promise<import("../api/profileRequests").ProfileRequestOutcome>;
  /** V3.81: abre el diálogo de cuenta (contraseña, email, baja y Salir). */
  onOpenAccount?: () => void;
}

/**
 * Menú de la cuenta (V3.75; recortado en V3.82).
 *
 * Hasta V3.81 esto era un **selector de usuarios**: desplegaba la lista de
 * cuentas, dejaba cambiar de una a otra y pedir una nueva. V3.82 retira esa idea
 * entera —cambiar de cuenta es cerrar sesión y entrar con otra credencial—, así
 * que aquí queda una sola cuenta (la de la sesión) y sus acciones: ver la ficha,
 * editarla y salir.
 *
 * No hay «pedir una cuenta» en el menú a propósito: pedirla es la pantalla de
 * entrada, y ofrecerlo aquí —dentro de una sesión ya abierta— era pedir una
 * cuenta a nombre de nadie.
 */
export function UserMenu({
  user,
  onEdit,
  onRequestDelete,
  onOpenAccount,
}: UserMenuProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

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
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="user-menu" ref={rootRef}>
      <button
        type="button"
        className="user-menu-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        title={t("user.profileTitle")}
        disabled={!user}
      >
        {user ? (
          <UserAvatar user={user} size={44} />
        ) : (
          <span
            className="user-avatar user-avatar--placeholder"
            style={{ width: 44, height: 44 }}
            aria-label={t("user.profile")}
          >
            ?
          </span>
        )}
        <span className="user-menu-name">{user?.name ?? t("user.profile")}</span>
        <ChevronIcon />
      </button>

      {open && user && (
        <div className="user-menu-pop" role="menu">
          <div className="user-menu-title">{t("user.profile")}</div>

          {/* V3.81: la cuenta. Sustituye a la pestaña «PIN» de Ajustes, que
              desaparece: contraseña, email, verificación, baja y Salir son cosas
              de identidad y viven donde vive la identidad (el propio usuario). */}
          {onOpenAccount && (
            <button
              type="button"
              className="user-menu-action"
              onClick={() => {
                onOpenAccount();
                setOpen(false);
              }}
            >
              {t("account.title")}
            </button>
          )}

          <button
            type="button"
            className="user-menu-action"
            onClick={() => {
              setEditing(true);
              setOpen(false);
            }}
          >
            {t("user.editProfile")}
          </button>
        </div>
      )}

      {editing && user && (
        <ProfileDialog
          user={user}
          onClose={() => setEditing(false)}
          onSave={(patch) => onEdit(user.id, patch)}
          {...(onRequestDelete ? { onRequestDelete } : {})}
        />
      )}
    </div>
  );
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
