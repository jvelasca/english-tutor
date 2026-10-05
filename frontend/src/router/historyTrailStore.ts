import { useEffect, useSyncExternalStore } from "react";
import { readHashPath, subscribeHash } from "./hash";
import {
  canGoBack,
  canGoForward,
  followTrail,
  pushTrail,
  startTrail,
  type HistoryTrail,
} from "./historyTrail";

export interface HistoryControls {
  canBack: boolean;
  canForward: boolean;
}

let trail: HistoryTrail | null = null;
let snapshot: HistoryControls = { canBack: false, canForward: false };
const listeners = new Set<() => void>();

function publish(next: HistoryTrail) {
  trail = next;
  const controls = { canBack: canGoBack(next), canForward: canGoForward(next) };
  if (controls.canBack === snapshot.canBack && controls.canForward === snapshot.canForward) {
    return;
  }
  snapshot = controls;
  for (const listener of listeners) listener();
}

export function ensureHistorySeed(path: string): void {
  if (trail) return;
  publish(startTrail(path));
}

/** La app abre una pantalla. Hay que llamarlo antes de cambiar el hash. */
export function noteHistoryPush(path: string): void {
  publish(pushTrail(trail ?? startTrail(path), path));
}

/** El hash cambió por atrás o adelante. */
export function noteHistoryFollow(path: string): void {
  if (!trail) {
    publish(startTrail(path));
    return;
  }
  publish(followTrail(trail, path));
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useHistoryControls(): HistoryControls {
  const controls = useSyncExternalStore(subscribe, () => snapshot, () => snapshot);
  useEffect(() => {
    ensureHistorySeed(readHashPath());
    return subscribeHash(() => noteHistoryFollow(readHashPath()));
  }, []);
  return controls;
}
