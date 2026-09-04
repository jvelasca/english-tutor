/**
 * Etiquetas de listening que hoy eran cadenas en inglés pintadas tal cual
 * (V3.6.1): ahora devuelven la clave i18n y la pantalla traduce con `t()`.
 * Los temas del banco son datos (se muestran como vienen) y no entran aquí.
 */

/** Clave i18n de la etiqueta honesta del tipo de audio (P0-1). */
export function audioTypeKey(audioType: string): string {
  switch (audioType) {
    case "recorded":
      return "listening.audioType.recorded";
    case "mixed":
      return "listening.audioType.mixed";
    case "synthetic_multispeaker":
      return "listening.audioType.synthetic_multispeaker";
    case "real_world":
      return "listening.audioType.real_world";
    case "tts":
    default:
      return "listening.audioType.tts";
  }
}

/** Clave i18n de un bucket de retención retardada ("0-2" → "0–2 days"). */
export function retentionBucketKey(bucket: string): string {
  switch (bucket) {
    case "0-2":
      return "listening.retentionBucket.0-2";
    case "2-7":
      return "listening.retentionBucket.2-7";
    case "7-30":
      return "listening.retentionBucket.7-30";
    case "30+":
      return "listening.retentionBucket.30plus";
    default:
      return "";
  }
}
