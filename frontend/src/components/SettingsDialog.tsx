import { useEffect, useState } from "react";
import { useI18n } from "../hooks/useI18n";
import type { Lang } from "../utils/i18n";
import { LANGS } from "../utils/i18n";
import {
  ACCENTS,
  DENSITIES,
  FONT_SCALES,
  type AppearanceSettings,
} from "../utils/appearance";
import type { Theme } from "../utils/theme";
import { ModelSelect } from "./ModelSelect";
import { SystemStatus } from "./SystemStatus";
import { AudioLibrary } from "./AudioLibrary";
import { BackupPanel } from "./BackupPanel";

type Tab = "appearance" | "language" | "ai" | "audio" | "system";

const THEME_OPTIONS: { id: Theme; labelKey: string }[] = [
  { id: "light", labelKey: "settings.theme.light" },
  { id: "dark", labelKey: "settings.theme.dark" },
];

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
