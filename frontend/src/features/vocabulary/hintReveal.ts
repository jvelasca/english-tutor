/** Trozo del recordatorio que enseña el paso de «Pista».

 * El paso 0 no enseña nada. 1 y 2 descubren un tercio y dos tercios de las
 * palabras (redondeando hacia arriba, al menos una). A partir de 3, la frase
 * entera. Nunca es la respuesta de la tarjeta: solo el recordatorio.
 */
export function mnemonicSlice(phrase: string, step: number): string {
  const words = phrase.trim().split(/\s+/).filter(Boolean);
  if (step <= 0 || words.length === 0) return "";
  if (step >= 3) return words.join(" ");
  const count = Math.max(1, Math.ceil((words.length * step) / 3));
  return words.slice(0, count).join(" ");
}
