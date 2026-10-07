/** Cómo se lee un significado de la consulta.

 * En ES→EN el alumno buscó en español: el título es la glosa y la línea de
 * debajo es la palabra inglesa. En el otro sentido el título sigue siendo el
 * término y la glosa va debajo. Sin glosa, el título es el término.
 */
export function meaningLines(
  meaning: { term: string; gloss: string },
  isReverse: boolean,
): {
  title: string;
  titleLang: "es" | "en";
  subtitle: string;
  subtitleLang: "es" | "en";
} {
  const term = meaning.term.trim();
  const gloss = meaning.gloss.trim();
  if (isReverse && gloss) {
    return {
      title: gloss,
      titleLang: "es",
      subtitle: term,
      subtitleLang: "en",
    };
  }
  return {
    title: term,
    titleLang: isReverse ? "en" : "es",
    subtitle: gloss,
    subtitleLang: isReverse ? "es" : "en",
  };
}
