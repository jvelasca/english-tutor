export type Translate = (key: string) => string;

export function wpmLabel(wpm: number | null, t: Translate): string {
  return wpm === null
    ? "—"
    : t("pron.wpm").replace("{count}", String(Math.round(wpm)));
}

export function fluencyLevelLabel(level: string, t: Translate): string {
  switch (level) {
    case "fluent":
      return t("pron.fluencyLevel.fluent");
    case "good":
      return t("pron.fluencyLevel.good");
    case "slow":
      return t("pron.fluencyLevel.slow");
    default:
      return "—";
  }
}
