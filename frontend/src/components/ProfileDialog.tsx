import { useEffect, useRef, useState } from "react";
import type { User } from "../types/api";
import type { UserPatch } from "../api/users";
import { AVATAR_COLORS, AVATAR_EMOJIS, avatarColor } from "../utils/avatar";
import { resizeImageToDataUrl } from "../utils/image";

interface ProfileDialogProps {
  user: User;
  onClose: () => void;
  onSave: (patch: UserPatch) => Promise<User | null>;
}

export function ProfileDialog({ user, onClose, onSave }: ProfileDialogProps) {
  const [name, setName] = useState(user.name);
  const [emoji, setEmoji] = useState(user.avatar_emoji ?? "");
  const [color, setColor] = useState(user.avatar_color ?? "");
  const [image, setImage] = useState(user.avatar_image ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function pickImage(file: File | undefined) {
    if (!file) return;
    try {
      setImage(await resizeImageToDataUrl(file));
    } catch {
      setError("No se pudo procesar la imagen.");
    }
  }

  async function submit() {
    const trimmed = name.trim();
    if (!trimmed) return;
    setSaving(true);
    setError(null);
    const updated = await onSave({
      name: trimmed,
      avatar_color: color,
      avatar_emoji: emoji,
      avatar_image: image,
    });
    setSaving(false);
    if (updated) onClose();
    else setError("No se pudo guardar el perfil.");
  }

  const preview = {
    ...user,
    name,
    avatar_color: color,
    avatar_emoji: emoji,
    avatar_image: image,
  };

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Editar perfil"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="dialog-header">
          <h2>Editar perfil</h2>
          <button
            type="button"
            className="dialog-close"
            onClick={onClose}
            aria-label="Cerrar"
          >
            ×
          </button>
        </header>

        <div className="dialog-body">
          <div className="profile-preview">
            <AvatarPreview user={preview} size={64} />
            <button
              type="button"
              className="dialog-secondary"
              onClick={() => fileRef.current?.click()}
            >
              Subir imagen
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              hidden
              onChange={(e) => void pickImage(e.target.files?.[0])}
            />
            {image && (
              <button
                type="button"
                className="dialog-link"
                onClick={() => setImage("")}
              >
                Quitar imagen
              </button>
            )}
          </div>

          <label className="field">
            <span className="field-label">Nombre</span>
            <input
              className="field-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              aria-label="Nombre del perfil"
            />
          </label>

          <div className="field">
            <span className="field-label">Icono</span>
            <div className="avatar-grid" role="group" aria-label="Elegir icono">
              <button
                type="button"
                className={`avatar-option${emoji === "" ? " active" : ""}`}
                onClick={() => setEmoji("")}
                title="Sin icono"
              >
                —
              </button>
              {AVATAR_EMOJIS.map((e) => (
                <button
                  key={e}
                  type="button"
                  className={`avatar-option${emoji === e ? " active" : ""}`}
                  onClick={() => setEmoji(e)}
                  title={e}
                >
                  {e}
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <span className="field-label">Color</span>
            <div className="avatar-grid" role="group" aria-label="Elegir color">
              <button
                type="button"
                className={`avatar-option avatar-option--auto${
                  color === "" ? " active" : ""
                }`}
                onClick={() => setColor("")}
                title="Automático"
              >
                A
              </button>
              {AVATAR_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  className={`avatar-option avatar-option--color${
                    color === c ? " active" : ""
                  }`}
                  style={{ background: c }}
                  onClick={() => setColor(c)}
                  title={c}
                  aria-label={`Color ${c}`}
                />
              ))}
            </div>
          </div>

          {error && <p className="dialog-error">{error}</p>}
        </div>

        <footer className="dialog-footer">
          <button
            type="button"
            className="dialog-secondary"
            onClick={onClose}
          >
            Cancelar
          </button>
          <button
            type="button"
            className="dialog-primary"
            onClick={submit}
            disabled={saving || !name.trim()}
          >
            {saving ? "Guardando…" : "Guardar"}
          </button>
        </footer>
      </div>
    </div>
  );
}

function AvatarPreview({
  user,
  size,
}: {
  user: User;
  size: number;
}) {
  if (user.avatar_image) {
    return (
      <img
        className="user-avatar user-avatar--image"
        src={user.avatar_image}
        alt=""
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <span
      className="user-avatar"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.44,
        background: avatarColor(user),
      }}
      aria-hidden="true"
    >
      {user.avatar_emoji || user.name.trim().charAt(0).toUpperCase() || "?"}
    </span>
  );
}
