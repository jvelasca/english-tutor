import { useEffect, useState } from "react";
import { useI18n } from "../hooks/useI18n";
import type { Lang } from "../utils/i18n";
import { LANGS } from "../utils/i18n";
import { isValidPin, sanitizePinInput, type SetPinOutcome } from "../utils/pin";
import {
  ACCENTS,
  DENSITIES,
  FONT_SCALES,
  LEVEL_SCHEMES,
  type AppearanceSettings,
  type LevelScheme,
} from "../utils/appearance";
import { levelClass } from "../utils/cefr";
import type { Theme } from "../utils/theme";
import { ModelSelect } from "./ModelSelect";
import { SystemStatus } from "./SystemStatus";
import { AudioLibrary } from "./AudioLibrary";
import { BackupPanel } from "./BackupPanel";
import { VoicesPanel } from "./VoicesPanel";

type Tab = "appearance" | "language" | "ai" | "audio" | "voices" | "pin" | "system";

const THEME_OPTIONS: { id: Theme; labelKey: string }[] = [
  { id: "light", labelKey: "settings.theme.light" },
  { id: "dark", labelKey: "settings.theme.dark" },
];

/** Pasos de la vista previa del esquema de niveles activo (Pre-A1 → C2). */
function levelPreviewOf(scheme: LevelScheme) {
  return (LEVEL_SCHEMES.find((s) => s.id === scheme) ?? LEVEL_SCHEMES[0]).preview;
}

interface SettingsDialogProps {
  appearance: AppearanceSettings;
  onUpdateAppearance: (patch: Partial<AppearanceSettings>) => void;
  onResetAppearance: () => void;
  lang: Lang;
  onSetLang: (lang: Lang) => void;
  model: string;
  models: string[];
  favoriteModel: string | null;
  onSelectModel: (model: string) => void;
  onFavoriteModel: (model: string) => void;
  userId: string | null;
  /** V3.76: ¿el perfil de la sesión tiene PIN? (solo el booleano, nunca el hash). */
  hasPin: boolean;
  /** Pone/cambia/retira el PIN del perfil de la sesión. */
  onSetPin: (currentPin: string | null, newPin: string) => Promise<SetPinOutcome>;
  onClose: () => void;
}

export function SettingsDialog({
  appearance,
  onUpdateAppearance,
  onResetAppearance,
  lang,
  onSetLang,
  model,
  models,
  favoriteModel,
  onSelectModel,
  onFavoriteModel,
  userId,
  hasPin,
  onSetPin,
  onClose,
}: SettingsDialogProps) {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("appearance");

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const TABS: { id: Tab; label: string }[] = [
    { id: "appearance", label: t("settings.appearance") },
    { id: "language", label: t("settings.interfaceLanguage") },
    { id: "ai", label: t("settings.ai") },
    { id: "audio", label: t("settings.audio") },
    { id: "voices", label: t("settings.voices") },
    { id: "pin", label: t("settings.pin.title") },
    { id: "system", label: t("settings.system") },
  ];

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div
        className="dialog dialog--settings"
        role="dialog"
        aria-modal="true"
        aria-label={t("settings.title")}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="dialog-header">
          <h2>{t("settings.title")}</h2>
          <button
            type="button"
            className="dialog-close flex h-10 w-10 items-center justify-center"
            onClick={onClose}
            aria-label={t("common.close")}
          >
            ×
          </button>
        </header>

        <div className="settings-tabs overflow-x-auto" role="tablist" aria-label={t("settings.title")}>
          {TABS.map((tb) => (
            <button
              key={tb.id}
              type="button"
              role="tab"
              aria-selected={tab === tb.id}
              className={`settings-tab shrink-0 whitespace-nowrap${tab === tb.id ? " active" : ""}`}
              onClick={() => setTab(tb.id)}
            >
              {tb.label}
            </button>
          ))}
        </div>

        <div className="dialog-body">
          {tab === "appearance" && (
            <>
              <div className="field">
                <span className="field-label">{t("settings.theme")}</span>
                <div className="seg" role="group" aria-label={t("settings.theme")}>
                  {THEME_OPTIONS.map((o) => (
                    <button
                      key={o.id}
                      type="button"
                      className={`seg-option${appearance.theme === o.id ? " active" : ""}`}
                      onClick={() => onUpdateAppearance({ theme: o.id })}
                      aria-pressed={appearance.theme === o.id}
                    >
                      {t(o.labelKey)}
                    </button>
                  ))}
                </div>
              </div>

              <div className="field">
                <span className="field-label">{t("settings.accentColor")}</span>
                <div className="accent-grid" role="group" aria-label={t("settings.accentColor")}>
                  {ACCENTS.map((a) => (
                    <button
                      key={a.id}
                      type="button"
                      className={`accent-swatch${
                        appearance.accent === a.id ? " active" : ""
                      }`}
                      style={{ background: a.swatch }}
                      onClick={() => onUpdateAppearance({ accent: a.id })}
                      title={t(`appearance.accent.${a.id}`)}
                      aria-label={t(`appearance.accent.${a.id}`)}
                      aria-pressed={appearance.accent === a.id}
                    />
                  ))}
                </div>
              </div>

              <div className="field">
                <span className="field-label">{t("settings.fontSize")}</span>
                <div className="seg" role="group" aria-label={t("settings.fontSize")}>
                  {FONT_SCALES.map((o) => (
                    <button
                      key={o.id}
                      type="button"
                      className={`seg-option${
                        appearance.fontScale === o.id ? " active" : ""
                      }`}
                      onClick={() => onUpdateAppearance({ fontScale: o.id })}
                      aria-pressed={appearance.fontScale === o.id}
                    >
                      {t(`appearance.font.${o.id}`)}
                    </button>
                  ))}
                </div>
              </div>

              <div className="field">
                <span className="field-label">{t("settings.density")}</span>
                <div className="seg" role="group" aria-label={t("settings.density")}>
                  {DENSITIES.map((o) => (
                    <button
                      key={o.id}
                      type="button"
                      className={`seg-option${
                        appearance.density === o.id ? " active" : ""
                      }`}
                      onClick={() => onUpdateAppearance({ density: o.id })}
                      aria-pressed={appearance.density === o.id}
                    >
                      {t(`appearance.density.${o.id}`)}
                    </button>
                  ))}
                </div>
              </div>

              <div className="field">
                <span className="field-label">{t("settings.levelColors")}</span>
                <div className="seg" role="group" aria-label={t("settings.levelColors")}>
                  {LEVEL_SCHEMES.map((o) => (
                    <button
                      key={o.id}
                      type="button"
                      className={`seg-option${
                        appearance.levelScheme === o.id ? " active" : ""
                      }`}
                      onClick={() => onUpdateAppearance({ levelScheme: o.id })}
                      aria-pressed={appearance.levelScheme === o.id}
                    >
                      {t(`appearance.levels.${o.id}`)}
                    </button>
                  ))}
                </div>
                {/* Vista previa VIVA: lee los tokens del esquema aplicado
                    (`--level-*-fg`), así que no puede prometer un color que
                    luego no aparezca en la app. Al pulsar otra opción se
                    repinta al instante porque el mecanismo es un atributo del
                    `<html>`. Decorativa: el nombre de cada esquema ya está en
                    el `seg` de arriba. */}
                <div className="level-preview" aria-hidden="true">
                  {levelPreviewOf(appearance.levelScheme).map((step) => (
                    <span
                      key={step.key}
                      className={`level-preview__step ${levelClass(step.key)}`}
                    >
                      {step.label}
                    </span>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  {t("appearance.levelsHint")}
                </p>
              </div>
            </>
          )}

          {tab === "language" && (
            <div className="field">
              <span className="field-label">{t("settings.interfaceLanguage")}</span>
              <div className="seg" role="group" aria-label={t("settings.interfaceLanguage")}>
                {LANGS.map((l) => (
                  <button
                    key={l.id}
                    type="button"
                    className={`seg-option${lang === l.id ? " active" : ""}`}
                    onClick={() => onSetLang(l.id)}
                    aria-pressed={lang === l.id}
                  >
                    {l.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {tab === "ai" && (
            <div className="field">
              <span className="field-label">{t("settings.model")}</span>
              <ModelSelect
                model={model}
                models={models}
                favoriteModel={favoriteModel}
                onSelect={onSelectModel}
                onFavorite={onFavoriteModel}
              />
            </div>
          )}

          {tab === "system" && (
            <>
              <SystemStatus />
              <BackupPanel />
            </>
          )}
          {tab === "audio" && <AudioLibrary />}
          {tab === "voices" && <VoicesPanel userId={userId} />}
          {tab === "pin" && (
            <PinSettings hasPin={hasPin} onSetPin={onSetPin} />
          )}
        </div>

        <footer className="dialog-footer">
          {tab === "appearance" && (
            <button
              type="button"
              className="dialog-secondary"
              onClick={onResetAppearance}
            >
              {t("settings.reset")}
            </button>
          )}
          <button type="button" className="dialog-primary" onClick={onClose}>
            {t("common.done")}
          </button>
        </footer>
      </div>
    </div>
  );
}

interface PinSettingsProps {
  hasPin: boolean;
  onSetPin: (currentPin: string | null, newPin: string) => Promise<SetPinOutcome>;
}

/**
 * PIN del perfil activo (V3.76, Fase 3 del P0 de identidad).
 *
 * Solo llama a la API: la regla de forma la comparte con el backend
 * (`utils/pin.ts` ↔ `services/pins.py`) y el hash, la verificación y el freno de
 * intentos viven **solo** en el servidor. Esta pantalla no puede debilitar nada
 * aunque se manipule: como mucho, manda un PIN que el backend rechazará.
 */
function PinSettings({ hasPin, onSetPin }: PinSettingsProps) {
  const { t } = useI18n();
  const [currentPin, setCurrentPin] = useState("");
  const [newPin, setNewPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  const newPinInvalid = newPin !== "" && !isValidPin(newPin);
  // Retirar el PIN (nuevo vacío) con uno ya puesto exige el actual; ponerlo por
  // primera vez, no. Es la misma regla que aplica el backend.
  const needsCurrent = hasPin;
  const canSave =
    !busy && !newPinInvalid && (!needsCurrent || currentPin.length > 0);

  async function save() {
    if (!canSave) return;
    setBusy(true);
    setMessage(null);
    setIsError(false);
    const outcome = await onSetPin(
      needsCurrent ? currentPin : null,
      newPin,
    );
    setBusy(false);
    if (outcome === "ok") {
      setMessage(newPin === "" ? t("settings.pin.removed") : t("settings.pin.saved"));
      setCurrentPin("");
      setNewPin("");
      return;
    }
    setIsError(true);
    if (outcome === "pin-invalid") setMessage(t("pin.invalid"));
    else if (outcome === "pin-throttled") setMessage(t("pin.throttled"));
    else setMessage(t("settings.pin.error"));
  }

  return (
    <div className="field">
      <span className="field-label">{t("settings.pin.title")}</span>
      <p className="text-xs text-muted-foreground">
        {t("settings.pin.explain")}
      </p>
      <p className="text-sm font-medium text-foreground">
        {hasPin ? t("settings.pin.active") : t("settings.pin.inactive")}
      </p>

      <form
        className="flex flex-col gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        {needsCurrent && (
          <label className="flex flex-col gap-1">
            <span className="field-label">{t("settings.pin.current")}</span>
            <input
              className="field-input"
              type="password"
              inputMode="numeric"
              autoComplete="off"
              value={currentPin}
              onChange={(e) => {
                setCurrentPin(sanitizePinInput(e.target.value));
                setMessage(null);
              }}
              aria-label={t("settings.pin.current")}
              disabled={busy}
            />
          </label>
        )}

        <label className="flex flex-col gap-1">
          <span className="field-label">{t("settings.pin.new")}</span>
          <input
            className="field-input"
            type="password"
            inputMode="numeric"
            autoComplete="off"
            value={newPin}
            onChange={(e) => {
              setNewPin(sanitizePinInput(e.target.value));
              setMessage(null);
            }}
            aria-label={t("settings.pin.new")}
            disabled={busy}
          />
        </label>

        {newPinInvalid && <p className="text-xs text-destructive">{t("pin.format")}</p>}
        {message && (
          <p className={isError ? "dialog-error" : "text-sm text-foreground"}>
            {message}
          </p>
        )}

        <div>
          <button type="submit" className="dialog-primary" disabled={!canSave}>
            {t("settings.pin.save")}
          </button>
        </div>
      </form>
    </div>
  );
}
