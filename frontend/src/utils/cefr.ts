export type CefrTone = "basic" | "intermediate" | "advanced";

export function cefrTone(level: string): CefrTone {
  if (level === "C1" || level === "C2") return "advanced";
  if (level === "B1" || level === "B2") return "intermediate";
  return "basic";
}

export function cefrLabel(level: string): string {
  switch (level) {
    case "Pre-A1":
      return "Pre-beginner";
    case "A1":
      return "Beginner";
    case "A2":
      return "Elementary";
    case "B1":
      return "Intermediate";
    case "B2":
      return "Upper-intermediate";
    case "C1":
      return "Advanced";
    case "C2":
      return "Mastery";
    default:
      return level;
  }
}

export function bandLabel(skill: string): string {
  switch (skill) {
    case "vocabulary":
      return "Vocabulary";
    case "grammar":
      return "Grammar";
    case "pronunciation":
      return "Pronunciation";
    case "listening":
      return "Listening";
    case "speaking":
      return "Speaking";
    case "reading":
      return "Reading";
    case "writing":
      return "Writing";
    default:
      return skill;
  }
}
