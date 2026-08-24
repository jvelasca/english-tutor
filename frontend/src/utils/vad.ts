/** Umbral de energía (RMS) por encima del cual se considera que hay voz. */
export const SILENCE_THRESHOLD = 0.02;

/** Milisegundos de silencio consecutivo tras los cuales se cierra un turno. */
export const SILENCE_MS = 1200;

/** Duración mínima de un turno de voz para que se considere válido. */
export const MIN_SPEECH_MS = 300;

/** Tope máximo de un chunk de grabación antes de forzar su procesado. */
export const MAX_CHUNK_MS = 15000;

/**
 * Raíz cuadrática media (RMS) de una señal PCM en el dominio del tiempo.
 *
 * - `Float32Array`: valores en [-1, 1]; el resultado queda en [0, 1].
 * - `Uint8Array`: valores en [0, 255] (centrados en 128); se normalizan
 *   restando 128 y dividiendo entre 128 para devolver también [0, 1].
 */
export function rms(samples: Float32Array | Uint8Array): number {
  if (samples.length === 0) return 0;

  let sum = 0;
  if (samples instanceof Float32Array) {
    for (let i = 0; i < samples.length; i++) {
      const v = samples[i];
      sum += v * v;
    }
    return Math.sqrt(sum / samples.length);
  }

  for (let i = 0; i < samples.length; i++) {
    const v = (samples[i] - 128) / 128;
    sum += v * v;
  }
  return Math.sqrt(sum / samples.length);
}

/**
 * Decide si un turno de voz debe darse por terminado.
 *
 * Devuelve `true` solo cuando se ha detectado voz y el silencio posterior
 * lleva al menos `SILENCE_MS` milisegundos.
 */
export function shouldEndUtterance(
  speechDetected: boolean,
  silenceStartMs: number | null,
  nowMs: number,
): boolean {
  if (!speechDetected || silenceStartMs === null) return false;
  return nowMs - silenceStartMs >= SILENCE_MS;
}
