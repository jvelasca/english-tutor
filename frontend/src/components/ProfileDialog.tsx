import { useEffect, useRef, useState } from "react";
import type { User } from "../types/api";
import type { UserPatch } from "../api/users";
import { AVATAR_COLORS, AVATAR_EMOJIS, avatarColor } from "../utils/avatar";
import { resizeImageToDataUrl } from "../utils/image";
import { useI18n } from "../hooks/useI18n";

interface ProfileDialogProps {
  user: User;
  onClose: () => void;
  onSave: (patch: UserPatch) => Promise<User | null>;
}

export function ProfileDialog({ user, onClose, onSave }: ProfileDialogProps) {
  const { t } = useI18n();
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
      setError(t("profile.imageError"));
    }
  }

  async function submit() {
    const trimmed = name.trim();
    if (!trimmed) return;
    setSaving(true);
    setError(null);
    // Solo reenvía la imagen si cambió, para no reenviar data URLs ya guardados
    // (que podrían superar el límite del backend) al editar solo el nombre.
    const patch: UserPatch = {
      name: trimmed,
      avatar_color: color,
      avatar_emoji: emoji,
    };
    if (image !== user.avatar_image) patch.avatar_image = image;
    try {
      const updated = await onSave(patch);
      setSaving(false);
      if (updated) onClose();
      else setError(t("profile.saveError"));
    } catch (e) {
      setSaving(false);
      setError(e instanceof Error ? e.message : t("profile.saveError"));
    }
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
        aria-label={t("profile.editTitle")}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="dialog-header">
          <h2>{t("profile.editTitle")}</h2>
          <button
            type="button"
            className="dialog-close flex h-10 w-10 items-center justify-center"
            onClick={onClose}
            aria-label={t("common.close")}
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
              {t("profile.uploadImage")}
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
                {t("profile.removeImage")}
              </button>
            )}
          </div>

          <label className="field">
            <span className="field-label">{t("profile.name")}</span>
            <input
              className="field-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              aria-label={t("profile.name")}
            />
          </label>

          <div className="field">
            <span className="field-label">{t("profile.icon")}</span>
            <div className="avatar-grid" role="group" aria-label={t("profile.chooseIcon")}>
              <button
                type="button"
                className={`avatar-option${emoji === "" ? " active" : ""}`}
                onClick={() => setEmoji("")}
                title={t("profile.noIcon")}
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
            <span className="field-label">{t("profile.color")}</span>
            <div className="avatar-grid" role="group" aria-label={t("profile.chooseColor")}>
              <button
                type="button"
                className={`avatar-option avatar-option--auto${
                  color === "" ? " active" : ""
                }`}
                onClick={() => setColor("")}
                title={t("profile.auto")}
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
                  aria-label={`${t("profile.color")} ${c}`}
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
            {t("common.cancel")}
          </button>
          <button
            type="button"
            className="dialog-primary"
            onClick={submit}
            disabled={saving || !name.trim()}
          >
            {saving ? t("common.saving") : t("common.save")}
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
