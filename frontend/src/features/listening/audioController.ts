/**
 * AudioController 4.0 (V3.28, Listening Engine 4.0, Fase 2, Bloque B).
 *
 * Controlador de reproducción del audio de referencia de listening sobre un
 * único `HTMLMediaElement` (reutilizable, no un `new Audio()` por pulsación):
 * play/pause/seek, velocidad con preservación de tono cuando el navegador la
 * soporta, bucle de segmento, replay del segmento marcado y suscripción de
 * estado (playing/currentTime/ended) para la UI.
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
  onEnded?: () => void;
  onError?: (message: string) => void;
}

export interface AudioSegment {
  start: number;
  end: number;
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
  private segment: AudioSegment | null = null;
  private disposed = false;

  private onTimeupdate = (): void => {
    if (!this.el.paused) this.callbacks.onCurrentTime?.(this.el.currentTime);
    // Bucle de segmento: al alcanzar el fin, vuelve al inicio sin detenerse.
    if (this.segment && this.el.currentTime >= this.segment.end) {
      this.el.currentTime = this.segment.start;
    }
  };

  private onPlay = (): void => {
    this.callbacks.onPlayingChange?.(true);
  };

  private onPause = (): void => {
    this.callbacks.onPlayingChange?.(false);
  };

  private onEnded = (): void => {
    this.callbacks.onPlayingChange?.(false);
    this.callbacks.onEnded?.();
  };

  private onError = (): void => {
    this.callbacks.onError?.("audio.playbackError");
  };

  constructor(el: AudioElementLike, callbacks: AudioControllerCallbacks = {}) {
    this.el = el;
    this.callbacks = callbacks;
    el.addEventListener("timeupdate", this.onTimeupdate);
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
    this.el.load();
    this.el.playbackRate = this.safeRate(playbackRate);
    this.segment = null;
  }

  /** Reproduce la URL cargada (o `load`+`play` si se pasa una URL nueva). */
  async play(url?: string, playbackRate?: number): Promise<void> {
    if (url) this.load(url, playbackRate ?? this.el.playbackRate);
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

  /** Salta a un instante (recortado a la duración). */
  seek(time: number): void {
    const duration = this.duration;
    const target = Math.max(0, Math.min(time, duration > 0 ? duration : time));
    this.el.currentTime = target;
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
    // Si la reproducción ya pasó el fin del segmento, se reinicia dentro.
    if (this.el.currentTime > this.segment.end) {
      this.el.currentTime = this.segment.start;
    }
  }

  /** Marca el instante actual como inicio del segmento (para replay/loop). */
  markSegmentStart(): void {
    this.segment = clampSegment(this.el.currentTime, this.duration || null, this.duration);
  }

  clearLoop(): void {
    this.segment = null;
  }

  private safeRate(rate: number): number {
    if (!Number.isFinite(rate) || rate <= 0) return 1;
    return Math.min(4, Math.max(0.25, rate));
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.el.pause();
    this.el.removeEventListener("timeupdate", this.onTimeupdate);
    this.el.removeEventListener("play", this.onPlay);
    this.el.removeEventListener("pause", this.onPause);
    this.el.removeEventListener("ended", this.onEnded);
    this.el.removeEventListener("error", this.onError);
  }
}
