export interface StreamEvent {
  content?: string;
  done?: boolean;
  error?: string;
}

/** Parsea una línea de un stream SSE ("data: {...}") a un evento. */
export function parseSseLine(line: string): StreamEvent | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data:")) return null;
  const payload = trimmed.slice("data:".length).trim();
  try {
    return JSON.parse(payload) as StreamEvent;
  } catch {
    return null;
  }
}
