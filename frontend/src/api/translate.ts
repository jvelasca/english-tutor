import { postJson, withTimeout } from "./client";

/** Respuesta de POST /api/translate (traducción de apoyo EN→ES). */
interface TranslateResponse {
  translation: string;
}

// Caché en memoria por frase: los textos de práctica se repiten mucho (repaso,
// rutas, dictados). La primera vez que se traduce una frase se paga la latencia
// del modelo local; las siguientes son instantáneas.
const translationCache = new Map<string, string>();

/**
 * Traduce una frase corta EN→ES con el modelo local (apoyo a demanda, no cuenta
 * como intento). Lanza un Error si el modelo no está disponible o la llamada
 * excede el timeout.
 */
export async function translateText(text: string): Promise<string> {
  const key = text.trim();
  if (!key) throw new Error("Empty text");

  const cached = translationCache.get(key);
  if (cached !== undefined) return cached;

  const data = await withTimeout(
    postJson<TranslateResponse>("/api/translate", { text: key }),
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
