import { useEffect, useRef, useState } from "react";
import type { User } from "../types/api";
import type { UserPatch } from "../api/users";
import { ProfileDialog } from "./ProfileDialog";
import { UserAvatar } from "./UserAvatar";

interface UserMenuProps {
  users: User[];
  currentUserId: string | null;
  onSelect: (id: string) => void;
  onAdd: (name: string) => void;
  onEdit: (id: string, patch: UserPatch) => Promise<User | null>;
}

export function UserMenu({
  users,
  currentUserId,
  onSelect,
  onAdd,
  onEdit,
}: UserMenuProps) {
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
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

  function submit() {
    const trimmed = name.trim();
    if (!trimmed) return;
    onAdd(trimmed);
    setName("");
    setAdding(false);
  }

  return (
    <div className="user-menu" ref={rootRef}>
      <button
        type="button"
        className="user-menu-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        title="Perfil de usuario"
      >
        {current ? (
          <UserAvatar user={current} size={44} />
        ) : (
          <span className="user-avatar" style={{ width: 44, height: 44 }}>
            ?
          </span>
        )}
        <span className="user-menu-name">{current?.name ?? "Perfil"}</span>
        <ChevronIcon />
      </button>

      {open && (
        <div className="user-menu-pop" role="menu">
          <div className="user-menu-title">Perfiles</div>
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
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") submit();
                  if (e.key === "Escape") setAdding(false);
                }}
                placeholder="Nombre"
                autoFocus
                aria-label="Nombre del nuevo perfil"
              />
              <button
                type="button"
                className="dialog-primary"
                onClick={submit}
                disabled={!name.trim()}
              >
                Añadir
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="user-menu-action"
              onClick={() => setAdding(true)}
            >
              + Nuevo perfil
            </button>
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
            Editar perfil
          </button>
        </div>
      )}

      {editing && current && (
        <ProfileDialog
          user={current}
          onClose={() => setEditing(false)}
          onSave={(patch) => onEdit(current.id, patch)}
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
