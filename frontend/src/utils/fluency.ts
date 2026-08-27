export function wpmLabel(wpm: number | null): string {
  return wpm === null ? "—" : `${Math.round(wpm)} words/min`;
}

export function fluencyLevelLabel(level: string): string {
  switch (level) {
    case "fluent":
      return "Fluent";
    case "good":
      return "Good pace";
    case "slow":
      return "Slow";
    default:
      return "—";
  }
}
