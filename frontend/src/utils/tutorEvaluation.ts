// Evaluación objetiva y determinista del tutor (espejo de services/evaluation.py).
// Puntúa señales libres de contexto: inglés, concisión y engagement (0..100).

const SPANISH_WORDS = new Set<string>([
  "porque", "cuando", "donde", "usted", "nosotros", "ellos", "ellas",
  "también", "tiene", "tienen", "hace", "hacer", "puede", "pueden", "pero",
  "muy", "bien", "hay", "ser", "estar", "tener", "más", "está", "están",
  "sí", "cómo", "qué", "cuál", "quién", "dónde", "cuándo", "después",
  "antes", "ahora", "aquí", "allí", "gracias", "hola", "adiós", "buenos",
  "buenas", "días", "noches", "mañana", "noche", "día", "año", "años",
]);

const FRIENDLY_MARKERS = [
  "great", "good", "nice", "well done", "excellent", "perfect", "correct",
  "almost", "try again", "let's", "keep going", "awesome", "fantastic",
];

export interface TutorReplyEvaluation {
  english: number;
  conciseness: number;
  engagement: number;
  total: number;
}

export interface TutorEvaluationAverage {
  english: number | null;
  conciseness: number | null;
  engagement: number | null;
  total: number | null;
}

export function normalize(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9áéíóúñü ]/g, " ");
}

export function words(text: string): string[] {
  return text.toLowerCase().match(/[a-záéíóúñü]+/g) ?? [];
}

export function spanishWordRatio(text: string): number {
  const ws = words(text);
  if (ws.length === 0) return 0;
  const spanish = ws.filter((w) => SPANISH_WORDS.has(w)).length;
  return Math.round((spanish / ws.length) * 100) / 100;
}

export function englishWordRatio(text: string): number {
  return Math.round((1 - spanishWordRatio(text)) * 100) / 100;
}

export function concisenessScore(wordCount: number): number {
  if (wordCount <= 0) return 0;
  if (wordCount < 10) return 50;
  if (wordCount <= 180) return 100;
  if (wordCount <= 400) return 70;
  return 40;
}

export function engagementScore(reply: string): number {
  if (reply.includes("?")) return 100;
  const n = normalize(reply);
  if (FRIENDLY_MARKERS.some((m) => n.includes(m))) return 70;
  return 0;
}

export function evaluateTutorReply(reply: string): TutorReplyEvaluation {
  const english = Math.round(englishWordRatio(reply) * 100);
  const conciseness = concisenessScore(words(reply).length);
  const engagement = engagementScore(reply);
  const total = Math.round(
    0.5 * english + 0.25 * conciseness + 0.25 * engagement,
  );
  return { english, conciseness, engagement, total };
}

export function averageEvaluations(
  evals: TutorReplyEvaluation[],
): TutorEvaluationAverage {
  if (evals.length === 0) {
    return { english: null, conciseness: null, engagement: null, total: null };
  }
  const avg = (key: keyof TutorReplyEvaluation): number =>
    Math.round(evals.reduce((acc, e) => acc + e[key], 0) / evals.length);
  return {
    english: avg("english"),
    conciseness: avg("conciseness"),
    engagement: avg("engagement"),
    total: avg("total"),
  };
}
