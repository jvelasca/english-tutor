import { useEffect, useRef } from "react";
import { getSettings, saveSettings } from "../api/settings";
import { navigateTo } from "../router/hash";
import {
  LAST_PATH_SETTING,
  canonicalPath,
  isRememberablePath,
  pathToRestore,
  readLastPath,
  writeLastPath,
} from "../utils/lastPlace";

function livePath(): string {
  if (typeof window === "undefined") return "/";
  return canonicalPath(window.location.hash);
}

/**
 * Recuerda la ruta del alumno y, al abrir la raíz, vuelve a ella.
 *
 * Un enlace que ya trae camino no se sustituye. Pulsar Inicio después de
 * haber entrado deja la raíz como último sitio.
 */
export function useLastPath(userId: string | null, path: string, paused: boolean) {
  const anchor = useRef(canonicalPath(path));
  const moved = useRef(false);
  const restoredTo = useRef<string | null>(null);
  const restoredFor = useRef<string | null>(null);

  useEffect(() => {
    const canon = canonicalPath(path);
    if (canon === anchor.current) return;
    if (restoredTo.current && canon === restoredTo.current) return;
    moved.current = true;
  }, [path]);

  useEffect(() => {
    if (!userId || paused) return;
    const canon = canonicalPath(path);
    if (!isRememberablePath(canon)) return;
    if (canon === "/" && !moved.current && anchor.current === "/") return;
    writeLastPath(userId, canon);
    void saveSettings(userId, { [LAST_PATH_SETTING]: canon }).catch(() => {});
  }, [userId, path, paused]);

  useEffect(() => {
    if (!userId || paused || restoredFor.current === userId) return;
    restoredFor.current = userId;
    if (anchor.current !== "/") return;
    const local = readLastPath(userId);
    const jump = pathToRestore(anchor.current, local);
    if (jump) {
      restoredTo.current = jump;
      navigateTo(jump);
    }
    let cancel = false;
    void getSettings(userId)
      .then((res) => {
        if (cancel || moved.current) return;
        const remote = res.settings?.[LAST_PATH_SETTING];
        if (typeof remote !== "string" || !isRememberablePath(remote)) return;
        const viewing = livePath();
        const stillThere = viewing === "/" || (local != null && viewing === local);
        if (!stillThere) return;
        writeLastPath(userId, remote);
        const next = pathToRestore("/", remote);
        if (next && next !== viewing) navigateTo(next);
      })
      .catch(() => {});
    return () => {
      cancel = true;
    };
  }, [userId, paused]);
}
