export function wpmLabel(wpm: number | null): string {
  return wpm === null ? "—" : `${Math.round(wpm)} palabras/min`;
}

export function fluencyLevelLabel(level: string): string {
  switch (level) {
    case "fluent":
      return "Fluido";
    case "good":
      return "Buen ritmo";
    case "slow":
      return "Lento";
    default:
      return "—";
  }
}
