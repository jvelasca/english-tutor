/**
 * Alineación palabra a palabra (puerto TS del `SequenceMatcher` de difflib,
 * Ratcliff-Obershelp sin junk) para reproducir en la UI exactamente la misma
 * clasificación que el backend (`services/phonetics.py::word_alignment`).
 *
 * Con esto los chips del modo Acento («palabra a palabra», mockup §6.3)
 * siempre coinciden con `word_accuracy` y el `breakdown` que el servidor
 * devuelve, incluso con palabras repetidas o frases sustituidas a medias.
 */

export type WordChipState = "ok" | "sub" | "miss";

export interface WordFeedback {
  /** Palabra tal y como aparece en la frase (con su puntuación original). */
  word: string;
  state: WordChipState;
  /** Solo en estado `sub`: lo que se dijo en su lugar. */
  heard?: string;
}

export interface WordFeedbackResult {
  /** Una entrada por palabra esperada, en orden. */
  expected: WordFeedback[];
  /** Palabras extra dichas de más (no estaban en la frase modelo). */
  extras: string[];
}

/** Normaliza igual que el backend: minúsculas y solo [a-z0-9']. */
function tokenize(text: string): string[] {
  return text.toLowerCase().match(/[a-z0-9']+/g) ?? [];
}

interface Block {
  i: number;
  j: number;
  size: number;
}

/** Port de `SequenceMatcher.find_longest_match` (sin juncks, `autojunk=False`). */
function findLongestMatch(
  a: string[],
  b: string[],
  alo: number,
  ahi: number,
  blo: number,
  bhi: number,
): Block {
  let bestI = alo;
  let bestJ = blo;
  let bestSize = 0;
  let j2len: Record<number, number> = {};
  for (let i = alo; i < ahi; i++) {
    const newj2len: Record<number, number> = {};
    for (let j = blo; j < bhi; j++) {
      if (a[i] === b[j]) {
        const k = (j2len[j - 1] ?? 0) + 1;
        newj2len[j] = k;
        if (k > bestSize) {
          bestSize = k;
          bestI = i - k + 1;
          bestJ = j - k + 1;
        }
      }
    }
    j2len = newj2len;
  }
  // Extiende el bloque hacia atrás y hacia delante sobre coincidencias exactas.
  while (
    bestI > alo &&
    bestJ > blo &&
    bestSize < ahi - alo &&
    a[bestI - 1] === b[bestJ - 1]
  ) {
    bestI--;
    bestJ--;
    bestSize++;
  }
  while (
    bestI + bestSize < ahi &&
    bestJ + bestSize < bhi &&
    a[bestI + bestSize] === b[bestJ + bestSize]
  ) {
    bestSize++;
  }
  return { i: bestI, j: bestJ, size: bestSize };
}

function matchingBlocks(a: string[], b: string[]): Block[] {
  const queue: Array<[number, number, number, number]> = [[0, a.length, 0, b.length]];
  const blocks: Block[] = [];
  while (queue.length > 0) {
    const [alo, ahi, blo, bhi] = queue.pop() as [number, number, number, number];
    const match = findLongestMatch(a, b, alo, ahi, blo, bhi);
    if (match.size > 0) {
      if (alo < match.i && blo < match.j) {
        queue.push([alo, match.i, blo, match.j]);
      }
      if (
        match.i + match.size < ahi &&
        match.j + match.size < bhi
      ) {
        queue.push([match.i + match.size, ahi, match.j + match.size, bhi]);
      }
      blocks.push(match);
    }
  }
  blocks.sort((x, y) => x.i - y.i || x.j - y.j || x.size - y.size);
  return blocks;
}

type Opcode = [tag: string, i1: number, i2: number, j1: number, j2: number];

function opcodes(a: string[], b: string[]): Opcode[] {
  const result: Opcode[] = [];
  let i = 0;
  let j = 0;
  // difflib siempre cierra con un bloque dummy (len(a), len(b), 0) para
  // emitir como delete/insert la cola sobrante de cualquiera de los dos lados.
  const blocks = [...matchingBlocks(a, b), { i: a.length, j: b.length, size: 0 }];
  for (const { i: ai, j: bj, size } of blocks) {
    let tag = "";
    if (i < ai && j < bj) tag = "replace";
    else if (i < ai) tag = "delete";
    else if (j < bj) tag = "insert";
    if (tag) result.push([tag, i, ai, j, bj]);
    i = ai + size;
    j = bj + size;
    if (size) result.push(["equal", ai, i, bj, j]);
  }
  return result;
}

/**
 * Alinea `script` (frase modelo) contra `heard` (transcripción) y clasifica
 * cada palabra esperada como ok / sub / miss, más las palabras extra.
 */
export function alignWords(script: string, heard: string): WordFeedbackResult {
  const expectedTokens = tokenize(script);
  const heardTokens = tokenize(heard);
  // Mostramos la frase tal cual (con puntuación); se alinea con los tokens
  // normalizados uno a uno (cada palabra separada por espacios = 1 token).
  const displayWords = script.trim().split(/\s+/).filter(Boolean);

  const stateByIndex = new Map<number, WordFeedback>();
  const extras: string[] = [];

  for (const [tag, i1, i2, j1, j2] of opcodes(expectedTokens, heardTokens)) {
    if (tag === "equal") {
      for (let idx = i1; idx < i2; idx++) {
        stateByIndex.set(idx, { word: displayWords[idx] ?? expectedTokens[idx], state: "ok" });
      }
    } else if (tag === "delete") {
      for (let idx = i1; idx < i2; idx++) {
        stateByIndex.set(idx, { word: displayWords[idx] ?? expectedTokens[idx], state: "miss" });
      }
    } else if (tag === "insert") {
      for (let idx = j1; idx < j2; idx++) {
        extras.push(heardTokens[idx]);
      }
    } else {
      // replace: empareja por orden; el sobrante esperado es miss y el de
      // más es extra (igual que `zip(strict=False)` del backend).
      const es = i2 - i1;
      const hs = j2 - j1;
      const pairs = Math.min(es, hs);
      for (let k = 0; k < es; k++) {
        const expectedIdx = i1 + k;
        const display = displayWords[expectedIdx] ?? expectedTokens[expectedIdx];
        if (k < pairs) {
          stateByIndex.set(expectedIdx, {
            word: display,
            state: "sub",
            heard: heardTokens[j1 + k],
          });
        } else {
          stateByIndex.set(expectedIdx, { word: display, state: "miss" });
        }
      }
      for (let k = pairs; k < hs; k++) {
        extras.push(heardTokens[j1 + k]);
      }
    }
  }

  const expected: WordFeedback[] = [];
  for (let idx = 0; idx < expectedTokens.length; idx++) {
    expected.push(
      stateByIndex.get(idx) ?? { word: displayWords[idx] ?? expectedTokens[idx], state: "ok" },
    );
  }
  return { expected, extras };
}
