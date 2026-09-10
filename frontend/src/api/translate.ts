import { postJson, withTimeout } from "./client";

/** Dirección de traducción soportada por POST /api/translate (V3.39). */
export type TranslateDirection = "en-es" | "es-en";

/** Respuesta de POST /api/translate (traducción de apoyo). */
interface TranslateResponse {
  translation: string;
}

// Caché en memoria por (dirección, frase): los textos de práctica se repiten
// mucho (repaso, rutas, dictados) y el Traductor repite frases de viaje. La
// primera vez que se traduce una frase se paga la latencia del modelo local;
// las siguientes son instantáneas. La dirección forma parte de la clave para
// que "hola" EN→ES y ES→EN no colisionen (V3.39, Fase 2).
const translationCache = new Map<string, string>();

function cacheKey(direction: TranslateDirection, text: string): string {
  return `${direction}:${text}`;
}

/**
 * Traduce una frase corta con el modelo local (apoyo a demanda, no cuenta como
 * intento). `direction` (`"en-es"` por defecto) elige el sentido: `"es-en"` es
 * el que usa el Traductor. Lanza un Error si el modelo no está disponible o la
 * llamada excede el timeout.
 */
export async function translateText(
  text: string,
  direction: TranslateDirection = "en-es",
): Promise<string> {
  const trimmed = text.trim();
  if (!trimmed) throw new Error("Empty text");

  const key = cacheKey(direction, trimmed);
  const cached = translationCache.get(key);
  if (cached !== undefined) return cached;

  const data = await withTimeout(
    postJson<TranslateResponse>("/api/translate", {
      text: trimmed,
      direction,
    }),
    // La primera traducción de una frase carga el modelo local en CPU (puede
    // tardar ~5–15 s); las siguientes salen de la caché y son instantáneas.
    60_000,
    "translate",
  );
  const translation = data?.translation?.trim();
  if (!translation) throw new Error("Empty translation");

  translationCache.set(key, translation);
  return translation;
}

/** Vacía la caché de traducciones (p. ej. al cambiar de idioma o en tests). */
export function clearTranslationCache(): void {
  translationCache.clear();
}
