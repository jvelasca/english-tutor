/** Entradas de telemetría de un turno del alumno (todos en `performance.now()` ms). */
export interface TurnTelemetryInput {
  sentAt: number;
  composeStartedAt: number | null;
  lastAssistantAt: number | null;
}

/** Telemetría calculada de un turno del alumno (ms, o `null` si no observable). */
export interface TurnTelemetry {
  duration_ms: number | null;
  latency_ms: number | null;
}

/** Redondea a entero, clampa a >= 0 y rechaza valores no finitos (NaN/Infinity). */
function toFiniteInt(value: number): number | null {
  if (!Number.isFinite(value)) return null;
  const rounded = Math.round(value);
  return rounded < 0 ? 0 : rounded;
}

/**
 * Calcula la telemetría del turno del alumno de forma pura y determinista.
 *
 * - `duration_ms` = `sentAt - composeStartedAt` (tiempo que el alumno estuvo
 *   componiendo el mensaje), o `null` si no hay `composeStartedAt`.
 * - `latency_ms` = `(composeStartedAt ?? sentAt) - lastAssistantAt` (tiempo desde
 *   que terminó la última respuesta del asistente hasta que el alumno empezó a
 *   componer/enviar), o `null` si no hay `lastAssistantAt`.
 *
 * Ambos valores se redondean a entero, se limitan a >= 0 y devuelven `null` si el
 * resultado no es finito (p. ej. entradas `NaN`).
 */
export function turnTelemetry(input: TurnTelemetryInput): TurnTelemetry {
  const { sentAt, composeStartedAt, lastAssistantAt } = input;

  let duration_ms: number | null = null;
  if (composeStartedAt != null) {
    duration_ms = toFiniteInt(sentAt - composeStartedAt);
  }

  let latency_ms: number | null = null;
  if (lastAssistantAt != null) {
    const start = composeStartedAt ?? sentAt;
    latency_ms = toFiniteInt(start - lastAssistantAt);
  }

  return { duration_ms, latency_ms };
}
