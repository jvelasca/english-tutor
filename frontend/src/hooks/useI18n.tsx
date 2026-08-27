import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import type { ReactNode } from "react";
import { getSettings, saveSettings } from "../api/settings";
import { isLang, translate, type Lang } from "../utils/i18n";

const LANG_STORAGE_KEY = "english-tutor.lang";

interface I18nValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nValue>({
  lang: "en",
  setLang: () => {},
  t: (key) => key,
});

export function I18nProvider({
  lang,
  setLang,
  children,
}: {
  lang: Lang;
  setLang: (l: Lang) => void;
  children: ReactNode;
}) {
  const t = useCallback((key: string) => translate(lang, key), [lang]);
  return (
    <I18nContext.Provider value={{ lang, setLang, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nValue {
  return useContext(I18nContext);
}

function readStoredLang(): Lang {
  if (typeof window === "undefined") return "en";
  try {
    const v = window.localStorage.getItem(LANG_STORAGE_KEY);
    return isLang(v) ? v : "en";
  } catch {
    return "en";
  }
}

/**
 * Idioma de interfaz persistido por usuario (localStorage + backend settings).
 * Por defecto "en" (el contenido pedagógico se mantiene en inglés).
 */
export function useLanguage(userId: string | null) {
  const [lang, setLangState] = useState<Lang>(readStoredLang);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await getSettings(userId);
        if (cancelled) return;
        const v = res.settings?.interface_language;
        if (isLang(v)) {
          setLangState(v);
          try {
            window.localStorage.setItem(LANG_STORAGE_KEY, v);
          } catch {
            /* almacenamiento no disponible */
          }
        }
      } catch {
        /* sin preferencias guardadas todavía */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const setLang = useCallback(
    (l: Lang) => {
      setLangState(l);
      try {
        window.localStorage.setItem(LANG_STORAGE_KEY, l);
      } catch {
        /* almacenamiento no disponible */
      }
      if (userId) {
        void saveSettings(userId, { interface_language: l }).catch(() => {});
      }
    },
    [userId],
  );

  return { lang, setLang };
}
