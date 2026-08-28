import { rms } from "./vad";

/**
 * Convierte una señal PCM (dominio del tiempo, `Uint8Array` o `Float32Array`)
 * en un porcentaje de nivel de entrada 0–100, apto para una barra de medidor.
 *
 * La curva aplica un suelo de ruido (valores por debajo de `noiseFloor` se
 * mapean a 0) y una compresión suave para que la barra sea legible en voz baja
 * y no se sature con un susurro.
 */
export function levelPercent(
  samples: Uint8Array | Float32Array,
  noiseFloor = 0.01,
): number {
  const energy = rms(samples);
  if (energy <= noiseFloor) return 0;
  const normalized = Math.min(1, (energy - noiseFloor) / (0.5 - noiseFloor));
  return Math.round(Math.sqrt(normalized) * 100);
}

/** Barra de nivel en texto (bloques llenos/vacíos) para feedback accesible. */
export function levelBar(percent: number, total = 10): string {
  const filled = Math.round((percent / 100) * total);
  return "█".repeat(filled) + "░".repeat(total - filled);
}
