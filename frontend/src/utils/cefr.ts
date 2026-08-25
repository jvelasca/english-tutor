export type CefrTone = "basic" | "intermediate" | "advanced";

export function cefrTone(level: string): CefrTone {
  if (level === "C1" || level === "C2") return "advanced";
  if (level === "B1" || level === "B2") return "intermediate";
  return "basic";
}

export function cefrLabel(level: string): string {
  switch (level) {
    case "A1":
      return "Principiante";
    case "A2":
      return "Básico";
    case "B1":
      return "Intermedio";
    case "B2":
      return "Intermedio alto";
    case "C1":
      return "Avanzado";
    case "C2":
      return "Maestría";
    default:
      return level;
  }
}

export function bandLabel(skill: string): string {
  switch (skill) {
    case "vocabulary":
      return "Vocabulario";
    case "grammar":
      return "Gramática";
    case "fluency":
      return "Fluidez";
    case "pronunciation":
      return "Pronunciación";
    case "listening":
      return "Listening";
    default:
      return skill;
  }
}
