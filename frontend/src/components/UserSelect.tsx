import { useState } from "react";
import type { User } from "../types/api";

interface UserSelectProps {
  users: User[];
  currentUserId: string | null;
  onSelect: (userId: string) => void;
  onAdd: (name: string) => void;
}

export function UserSelect({
  users,
  currentUserId,
  onSelect,
  onAdd,
}: UserSelectProps) {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");

  const submit = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    onAdd(trimmed);
    setName("");
    setAdding(false);
  };

  const cancel = () => {
    setName("");
    setAdding(false);
  };

  return (
    <div className="user-select">
      <select
        className="user-select-dropdown"
        value={currentUserId ?? ""}
        onChange={(e) => onSelect(e.target.value)}
        title="Perfil de usuario"
        aria-label="Perfil de usuario"
      >
        {users.map((u) => (
          <option key={u.id} value={u.id}>
            {u.name}
          </option>
        ))}
      </select>

      {adding ? (
        <div className="user-select-form">
          <input
            className="user-select-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submit();
              if (e.key === "Escape") cancel();
            }}
            placeholder="Nombre"
            autoFocus
            aria-label="Nombre del nuevo usuario"
          />
          <button
            className="user-select-ok"
            onClick={submit}
            disabled={!name.trim()}
            title="Añadir usuario"
            aria-label="Confirmar"
          >
            ✓
          </button>
          <button
            className="user-select-cancel"
            onClick={cancel}
            title="Cancelar"
            aria-label="Cancelar"
          >
            ×
          </button>
        </div>
      ) : (
        <button
          className="user-select-add-btn"
          onClick={() => setAdding(true)}
          title="Añadir usuario"
          aria-label="Añadir usuario"
        >
          +
        </button>
      )}
    </div>
  );
}
