import { useEffect, useRef, useState } from "react";
import { AudioController } from "./audioController";

/**
 * `useAudioController` — estado React sobre el AudioController 4.0 (V3.28).
 *
 * Crea (bajo demanda) un único `HTMLAudioElement` por montaje, lo envuelve en un
 * `AudioController` y expone el estado de reproducción a la UI (playing,
 * currentTime, duration). Es seguro en entornos sin DOM (SSR/tests de Node): el
 * elemento se crea solo en el cliente y, si `Audio` no existe, el hook queda
 * inerte (`controller === null`, playing=false).
 *
 * La UI usa `controller.play(url)/pause()/seek()/loop()/setRate()/...`; los
 * estados `playing`/`currentTime`/`duration` se refrescan solos vía callbacks.
 */
export interface AudioPlaybackState {
  controller: AudioController | null;
  playing: boolean;
  currentTime: number;
  duration: number;
}

export function useAudioController(): AudioPlaybackState {
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [controller, setController] = useState<AudioController | null>(null);
  const controllerRef = useRef<AudioController | null>(null);

  useEffect(() => {
    if (typeof Audio === "undefined") return undefined;
    const element = new Audio();
    const instance = new AudioController(element, {
      onPlayingChange: setPlaying,
      onCurrentTime: (time) => {
        setCurrentTime(time);
        if (Number.isFinite(element.duration) && element.duration > 0) {
          setDuration(element.duration);
        }
      },
      onError: () => setPlaying(false),
    });
    controllerRef.current = instance;
    setController(instance);
    return () => {
      // Solo se pausa al desmontar (libera el elemento de audio del navegador);
      // el resto de estados son de React y se descartan con el desmontaje.
      instance.dispose();
      if (controllerRef.current === instance) controllerRef.current = null;
    };
  }, []);

  return { controller, playing, currentTime, duration };
}
