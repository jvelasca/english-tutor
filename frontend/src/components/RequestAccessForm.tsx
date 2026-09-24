import { useRef, useState } from "react";
import type {
  ProfileRequestFailure,
  ProfileRequestOutcome,
  RequestedAvatar,
} from "../api/profileRequests";
import { AVATAR_COLORS, AVATAR_EMOJIS } from "../utils/avatar";
import { isPlausibleEmail } from "../utils/credentials";
import { resizeImageToDataUrl } from "../utils/image";
import { useI18n } from "../hooks/useI18n";
import { UserAvatar } from "./UserAvatar";
import type { User } from "../types/api";

interface RequestAccessFormProps {
  /**
   * Envía la solicitud. **No** crea nada: devuelve el desenlace para que la
   * pantalla pueda contar qué pasó, porque quien pide una cuenta puede no tener
   * ninguna todavía y esta pantalla es su único canal.
   */
  onRequest: (
    name: string,
    email: string,
    avatar: RequestedAvatar,
    note: string,
  ) => Promise<ProfileRequestOutcome>;
  /** Volver a la entrada (login). */
  onBack: () => void;
}

/**
 * Formulario de **solicitud de acceso** (V3.82).
 *
 * Es el alta entera: nombre o apodo, email y avatar. Antes solo se pedía un
 * nombre, y con un nombre no se puede hacer nada —ni autorizar por correo ni
 * identificar una cuenta—, así que el webmaster tenía que completar a mano lo
 * que la solicitud no traía. Ahora pide **exactamente** lo que la cuenta
 * necesitará, y al aprobar no hay que teclear ni elegir nada.
 *
 * No crea la cuenta ni fija la contraseña: eso llega por correo, en la
 * invitación. Aquí solo se pide.
 */
export function RequestAccessForm({ onRequest, onBack }: RequestAccessFormProps) {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");
  const [color, setColor] = useState("");
  const [emoji, setEmoji] = useState("");
  const [image, setImage] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<ProfileRequestFailure | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function pickImage(file: File | undefined) {
    if (!file) return;
    try {
      setImage(await resizeImageToDataUrl(file));
      setMessage(null);
    } catch {
      setMessage(t("profile.imageError"));
    }
  }

  async function submit() {
    if (busy || sent) return;
    setFailure(null);
    setMessage(null);
    // El nombre es obligatorio: el backend lo acota y colapsa espacios, pero
    // pedirlo en blanco para que se rellene solo dejaría una fila que el
    // webmaster no puede atribuir a nadie.
    if (!name.trim()) {
      setMessage(t("user.requestInvalid"));
      return;
    }
    // Dos averías distintas y dos salidas distintas: sin email **no hay**
    // invitación que mandar (y esta pantalla es el único canal de quien la pide),
    // mientras que un email con mala forma es un dedazo que se corrige aquí
    // mismo. Un solo mensaje para las dos haría repetir el paso que no era.
    if (!email.trim()) {
      setMessage(t("request.emailRequired"));
      return;
    }
    if (!isPlausibleEmail(email)) {
      setMessage(t("account.emailFormat"));
      return;
    }
    setBusy(true);
    const outcome = await onRequest(
      name,
      email,
      {
        ...(color ? { avatar_color: color } : {}),
        ...(emoji ? { avatar_emoji: emoji } : {}),
        ...(image ? { avatar_image: image } : {}),
      },
      note,
    );
    setBusy(false);
    if (outcome.ok) {
      setSent(true);
      return;
    }
    setFailure(outcome.reason);
  }

  const preview: User = {
    id: "preview",
    name,
    avatar_color: color,
    avatar_emoji: emoji,
    avatar_image: image,
    created_at: "",
  };

  if (sent) {
    return (
      <div className="flex flex-col gap-3">
        <p
          className="rounded-md border border-border bg-muted px-3 py-2 text-sm leading-relaxed text-muted-foreground"
          role="status"
        >
          {t("user.requestSent")}
        </p>
        <button type="button" className="dialog-secondary" onClick={onBack}>
          {t("request.back")}
        </button>
      </div>
    );
  }

  return (
    <form
      className="flex flex-col gap-3"
      // `noValidate` deliberado (mismo criterio que la antigua alta): la
      // validación de forma se hace aquí, en un solo sitio y en el idioma de la
      // app, en vez de dejar que el globito nativo cancele el envío.
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      {/* V3.82: la solicitud es **todo** el alta, así que la pantalla dice de
          antemano qué pasa después (lo autoriza el webmaster y llega un correo
          para elegir la contraseña). Sin esto, quien rellena no sabe si esto
          crea una cuenta, la pide o la publica. */}
      <p className="text-sm leading-relaxed text-muted-foreground">
        {t("request.prompt")}
      </p>

      <div className="profile-preview">
        <UserAvatar user={preview} size={56} />
        <button
          type="button"
          className="dialog-secondary"
          onClick={() => fileRef.current?.click()}
        >
          {t("request.uploadImage")}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => void pickImage(e.target.files?.[0])}
        />
        {image && (
          <button type="button" className="dialog-link" onClick={() => setImage("")}>
            {t("request.removeImage")}
          </button>
        )}
      </div>

      <label className="field">
        <span className="field-label">{t("request.name")}</span>
        <input
          className="field-input"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setMessage(null);
          }}
          autoFocus
          aria-label={t("request.name")}
          disabled={busy}
        />
      </label>

      <label className="field">
        <span className="field-label">{t("user.email")}</span>
        <input
          className="field-input"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            setMessage(null);
            setFailure(null);
          }}
          aria-label={t("user.email")}
          disabled={busy}
        />
      </label>

      <div className="field">
        <span className="field-label">{t("request.avatar")}</span>
        <div
          className="avatar-grid"
          role="group"
          aria-label={t("request.avatar")}
        >
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
        <div
          className="avatar-grid"
          role="group"
          aria-label={t("profile.chooseColor")}
        >
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

      <label className="field">
        <span className="field-label">{t("request.note")}</span>
        <input
          className="field-input"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          aria-label={t("request.note")}
          disabled={busy}
        />
      </label>

      {failure && (
        <p className="dialog-error" role="alert">
          {t(requestErrorKey(failure))}
        </p>
      )}
      {message && (
        <p className="dialog-error" role="alert">
          {message}
        </p>
      )}

      <div className="flex gap-2">
        <button type="submit" className="dialog-primary flex-1" disabled={busy}>
          {t("request.submit")}
        </button>
        <button
          type="button"
          className="dialog-secondary"
          onClick={onBack}
          disabled={busy}
        >
          {t("request.back")}
        </button>
      </div>

      <p className="text-xs leading-relaxed text-muted-foreground">
        {t("user.requestHint")}
      </p>
    </form>
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
    case "email-taken":
      return "request.emailTaken";
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
