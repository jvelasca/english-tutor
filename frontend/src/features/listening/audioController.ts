/**
 * AudioController 4.0 (V3.28/3.29, Listening Engine 4.0, Fase 2/3).
 *
 * Controlador de reproducción del audio de referencia de listening sobre un
 * único `HTMLMediaElement` (reutilizable, no un `new Audio()` por pulsación):
 * play/pause/seek, velocidad con preservación de tono cuando el navegador la
 * soporta, bucle de segmento, replay del segmento marcado y suscripción de
 * estado (playing/currentTime/duration/ended) para la UI.
 *
 * V3.29 (Fase 3, P5): el bucle de segmento pasa a un scheduler
 * `requestAnimationFrame` inyectable (`AudioFrameScheduler`) que rebobina en
 * cuanto `currentTime >= segment.end` en cada fotograma (menos deriva que el
 * `timeupdate`, ~4 Hz); `timeupdate` queda como respaldo sin rAF y la
 * duración se notifica también en `loadedmetadata` vía `onDuration`.
 *
 * El módulo es puro y testeable en Node: la clase recibe el elemento de medios
 * por constructor (un `HTMLAudioElement` real en la app, un doble en tests) y
 * las funciones de decisión (variante de velocidad más cercana, límites de
 * segmento) son puras.
 *
 * Contrato con el backend: la escalera de variantes (slow/normal/fast) sigue
 * siendo la fuente de audio (URLs pre-renderizadas con su `speech_rate`). El
 * controller elige la variante más cercana al `rate` pedido y solo usa
 * `playbackRate` fino cuando `preservesPitch` está disponible; si no, la
 * velocidad "extra" se sirve cambiando de variante (compatibilidad total con la
 * escalera actual de `getListeningAudioUrl(variant)`).
 */

export interface AudioElementLike {
  src: string;
  currentTime: number;
  duration: number;
  playbackRate: number;
  paused: boolean;
  preservesPitch: boolean;
  play(): Promise<void> | void;
  pause(): void;
  load(): void;
  addEventListener(type: string, listener: () => void): void;
  removeEventListener(type: string, listener: () => void): void;
}

export interface AudioControllerCallbacks {
  onPlayingChange?: (playing: boolean) => void;
  onCurrentTime?: (time: number) => void;
  /** Duración conocida del audio (notificada en `loadedmetadata`). V3.29. */
  onDuration?: (duration: number) => void;
  onEnded?: () => void;
  onError?: (message: string) => void;
}

export interface AudioSegment {
  start: number;
  end: number;
}

/**
 * Scheduler de fotogramas inyectable (V3.29, P5). En el navegador se usa
 * `requestAnimationFrame`; en tests de Node se inyecta un doble para controlar
 * el instante exacto del rebobinado del bucle sin depender de `timeupdate`.
 */
export interface AudioFrameScheduler {
  frame: (callback: () => void) => number;
  cancelFrame: (id: number) => void;
}

/** Factores de velocidad de la escalera del backend (`VARIANT_SPEED_FACTORS`). */
export const VARIANT_SPEED_FACTORS: Record<string, number> = {
  slow: 0.75,
  normal: 1.0,
  fast: 1.25,
};

export const VARIANT_ORDER = ["slow", "normal", "fast"];

/** Preservación de tono: el navegador expone el atributo `preservesPitch`
 * (estándar; Safari moderno también lo expone). El valor actual no importa:
 * si el atributo existe, puede fijarse a true para reproducir rápido sin
 * distorsionar el tono. */
export function supportsPreservesPitch(el: AudioElementLike): boolean {
  return "preservesPitch" in el;
}

/**
 * Variante más cercana a un `rate` pedido dentro de la escalera disponible.
 * El rate se interpreta como multiplicador sobre la velocidad "normal" del ítem.
 * Si no hay candidatas (lista vacía), devuelve "normal".
 */
export function nearestVariantForRate(
  requestedRate: number,
  available: string[] = VARIANT_ORDER,
): string {
  const candidates = available.filter((v) => v in VARIANT_SPEED_FACTORS);
  if (candidates.length === 0) return "normal";
  const rate = Number.isFinite(requestedRate) ? requestedRate : 1.0;
  let best = candidates[0];
  let bestDelta = Infinity;
  for (const v of candidates) {
    const delta = Math.abs(VARIANT_SPEED_FACTORS[v] - rate);
    if (delta < bestDelta) {
      bestDelta = delta;
      best = v;
    }
  }
  return best;
}

/**
 * Límites de un segmento de bucle/replay recortados a la duración del audio.
 * Devuelve `null` cuando el segmento no es reproducible (sin fin o sin inicio).
 */
export function clampSegment(
  start: number,
  end: number | null,
  duration: number,
): AudioSegment | null {
  if (end === null || end === undefined) return null;
  const safeStart = Math.max(0, Math.min(start, duration));
  const safeEnd = Math.max(safeStart, Math.min(end, duration));
  if (safeEnd - safeStart < 0.05) return null;
  return { start: safeStart, end: safeEnd };
}

/**
 * Controlador de reproducción sobre un elemento de medios.
 *
 * La clase no crea ni posee el elemento: recibe el `HTMLAudioElement` (o doble)
 * para poder operar en cualquier entorno. Registra sus listeners al construirse
 * y los elimina en `dispose()`.
 */
export class AudioController {
  private readonly el: AudioElementLike;
  private readonly callbacks: AudioControllerCallbacks;
  private readonly frame: ((callback: () => void) => number) | null;
  private readonly cancelFrame: ((id: number) => void) | null;
  private segment: AudioSegment | null = null;
  private disposed = false;
  private rafId: number | null = null;
  /** URL cargada actualmente: permite que `play(url)` no recargue si es la
   * misma (V3.52.1: al reanudar no se pierde el bucle A/B activo). */
  private loadedUrl: string | null = null;

  private onTimeupdate = (): void => {
    if (!this.el.paused) this.callbacks.onCurrentTime?.(this.el.currentTime);
    // Respaldo del bucle de segmento si no hay `requestAnimationFrame`
    // (entornos sin rAF o pestañas en segundo plano, donde rAF se congela).
    this.rewindIfPastSegmentEnd();
  };

  private onLoadedMetadata = (): void => {
    const duration = Number.isFinite(this.el.duration) ? this.el.duration : 0;
    if (duration > 0) this.callbacks.onDuration?.(duration);
  };

  private onPlay = (): void => {
    this.callbacks.onPlayingChange?.(true);
    this.startFrameLoop();
  };

  private onPause = (): void => {
    this.callbacks.onPlayingChange?.(false);
    this.stopFrameLoop();
  };

  private onEnded = (): void => {
    this.callbacks.onPlayingChange?.(false);
    this.stopFrameLoop();
    this.callbacks.onEnded?.();
  };

  private onError = (): void => {
    this.callbacks.onError?.("audio.playbackError");
  };

  /** Rebobina al inicio del segmento si la reproducción superó su fin. */
  private rewindIfPastSegmentEnd(): void {
    if (this.segment && !this.el.paused && this.el.currentTime >= this.segment.end) {
      this.el.currentTime = this.segment.start;
      // V3.52.1: notifica el salto para que el slider/contador no se quede
      // mostrando el instante B (el `onCurrentTime` previo de `timeupdate`
      // llegaba antes del rebobinado).
      this.callbacks.onCurrentTime?.(this.segment.start);
    }
  }

  /**
   * Bucle preciso con `requestAnimationFrame` (V3.29, P5): mientras hay
   * segmento y se reproduce, comprueba el fin en cada fotograma y rebobina en
   * cuanto `currentTime >= segment.end` (mucho menos deriva que `timeupdate`,
   * que el navegador dispara ~4 Hz). Sin segmento no corre: el estado de
   * `currentTime` para la UI sigue llegando por `timeupdate`.
   */
  private startFrameLoop(): void {
    if (!this.frame || !this.segment || this.rafId !== null || this.disposed) {
      return;
    }
    const tick = (): void => {
      this.rafId = null;
      if (this.disposed) return;
      if (!this.segment || this.el.paused) return;
      this.rewindIfPastSegmentEnd();
      if (this.segment && !this.el.paused) {
        this.rafId = this.frame ? this.frame(tick) : null;
      }
    };
    this.rafId = this.frame(tick);
  }

  private stopFrameLoop(): void {
    if (this.rafId !== null) {
      if (this.cancelFrame) this.cancelFrame(this.rafId);
      this.rafId = null;
    }
  }

  constructor(
    el: AudioElementLike,
    callbacks: AudioControllerCallbacks = {},
    scheduler?: AudioFrameScheduler,
  ) {
    this.el = el;
    this.callbacks = callbacks;
    // Scheduler por defecto: requestAnimationFrame del navegador si existe; si
    // no (Node/SSR o tests sin inyección), el bucle usa `timeupdate` como
    // respaldo (comportamiento V3.28).
    const hasRaf =
      typeof scheduler?.frame === "function" ||
      typeof globalThis.requestAnimationFrame === "function";
    this.frame =
      scheduler?.frame ??
      (hasRaf
        ? (callback) => globalThis.requestAnimationFrame(callback)
        : null);
    this.cancelFrame =
      scheduler?.cancelFrame ??
      (hasRaf ? (id) => globalThis.cancelAnimationFrame(id) : null);
    el.addEventListener("timeupdate", this.onTimeupdate);
    el.addEventListener("loadedmetadata", this.onLoadedMetadata);
    el.addEventListener("play", this.onPlay);
    el.addEventListener("pause", this.onPause);
    el.addEventListener("ended", this.onEnded);
    el.addEventListener("error", this.onError);
  }

  get currentTime(): number {
    return this.el.currentTime;
  }

  get duration(): number {
    return Number.isFinite(this.el.duration) ? this.el.duration : 0;
  }

  get playing(): boolean {
    return !this.el.paused;
  }

  get loopSegment(): AudioSegment | null {
    return this.segment;
  }

  /** Carga una URL (sin reproducir) y restablece velocidad y segmento. */
  load(url: string, playbackRate = 1): void {
    this.el.src = url;
    this.loadedUrl = url;
    this.el.load();
    this.el.playbackRate = this.safeRate(playbackRate);
    this.clearLoop();
  }

  /**
   * Reproduce la URL cargada (o `load`+`play` si es una URL NUEVA).
   *
   * V3.52.1: si la URL es la misma que la ya cargada NO se recarga, para no
   * perder el segmento A/B activo ni reiniciar la posición al reanudar tras una
   * pausa (antes `play(url)` recargaba siempre y `load` limpiaba el bucle).
   * La única excepción es que la reproducción haya TERMINADO: entonces se
   * vuelve al principio (o al inicio del segmento) para poder repetir.
   */
  async play(url?: string, playbackRate?: number): Promise<void> {
    if (url) {
      const finished =
        this.duration > 0 && this.el.currentTime >= this.duration - 0.05;
      if (url !== this.loadedUrl) {
        this.load(url, playbackRate ?? this.el.playbackRate);
      } else if (finished) {
        // Misma URL ya cargada: si terminó, se repite (desde el inicio del
        // segmento activo si lo hay; si no, desde el principio) sin recargar.
        if (this.segment) {
          this.el.currentTime = this.segment.start;
          this.callbacks.onCurrentTime?.(this.segment.start);
        } else {
          this.load(url, playbackRate ?? this.el.playbackRate);
        }
      }
    }
    await this.el.play();
  }

  pause(): void {
    this.el.pause();
  }

  /** Detiene (pausa y vuelve al inicio del audio o del segmento activo). */
  stop(): void {
    this.el.pause();
    this.el.currentTime = this.segment ? this.segment.start : 0;
  }

  /**
   * Salta a un instante (recortado a la duración).
   *
   * V3.28.1 (P2-01): además de fijar `currentTime`, notifica a los suscriptores.
   * Sin reproducción, `timeupdate` no se dispara y el estado React del hook
   * quedaría obsoleto al mover un slider con el audio pausado; la notificación
   * explícita mantiene `currentTime` consistente en cualquier estado.
   */
  seek(time: number): void {
    const duration = this.duration;
    const target = Math.max(0, Math.min(time, duration > 0 ? duration : time));
    this.el.currentTime = target;
    this.callbacks.onCurrentTime?.(target);
  }

  /**
   * Fija la velocidad de reproducción. Cuando el navegador preserva el tono
   * (`preservesPitch`), se usa `playbackRate` fino sobre la URL actual; si no,
   * el rate se redondea a la variante de la escalera más cercana (y se devuelve
   * la variante elegida para que el llamador sirva la URL correspondiente).
   */
  setRate(rate: number): string | null {
    const el = this.el;
    if (supportsPreservesPitch(el)) {
      el.playbackRate = this.safeRate(rate);
      return null; // la URL actual sigue valiendo (playbackRate fino)
    }
    const variant = nearestVariantForRate(rate);
    el.playbackRate = 1;
    return variant;
  }

  /** Reproduce el segmento marcado (o desde el inicio si no hay segmento). */
  async replaySegment(): Promise<void> {
    this.seek(this.segment ? this.segment.start : 0);
    await this.el.play();
  }

  /** Reproduce en bucle el segmento [start, end] (recortado a la duración). */
  loop(start: number, end: number): void {
    this.segment = clampSegment(start, end, this.duration);
    if (!this.segment) return;
    // Si la reproducción ya alcanzó el fin del segmento, se reinicia dentro.
    if (this.el.currentTime >= this.segment.end) {
      this.el.currentTime = this.segment.start;
      this.callbacks.onCurrentTime?.(this.segment.start);
    }
    if (!this.el.paused) this.startFrameLoop();
  }

  /** Marca el instante actual como inicio del segmento (para replay/loop). */
  markSegmentStart(): void {
    this.segment = clampSegment(
      this.el.currentTime,
      this.duration || null,
      this.duration,
    );
    if (!this.el.paused) this.startFrameLoop();
  }

  clearLoop(): void {
    this.segment = null;
    this.stopFrameLoop();
  }

  private safeRate(rate: number): number {
    if (!Number.isFinite(rate) || rate <= 0) return 1;
    return Math.min(4, Math.max(0.25, rate));
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.stopFrameLoop();
    this.el.pause();
    this.el.removeEventListener("timeupdate", this.onTimeupdate);
    this.el.removeEventListener("loadedmetadata", this.onLoadedMetadata);
    this.el.removeEventListener("play", this.onPlay);
    this.el.removeEventListener("pause", this.onPause);
    this.el.removeEventListener("ended", this.onEnded);
    this.el.removeEventListener("error", this.onError);
  }
}
