/**
 * Paridad i18n automática (V3.13, P2.2).
 *
 * Verifica tres invariantes sobre el diccionario `frontend/src/utils/i18n.ts`:
 *
 * 1. Toda clave declarada tiene `en` y `es` no vacíos.
 * 2. No hay claves duplicadas en el diccionario (que una redefinición pise a la
 *    anterior silenciosamente).
 * 3. Cada uso estático de `t("clave")` / `translate(..., "clave")` en el código
 *    (componentes y utilidades, excluidos tests y el propio diccionario)
 *    resuelve a una clave declarada.
 *
 * Los usos dinámicos (clave construida con interpolación o variable, p. ej.
 * `t(\`prefix.${x}\`)` o `t(groupKey(state))`) NO son analizables de forma
 * estática: se documentan en `DYNAMIC_KEY_PREFIXES` (allow-list) para que el
 * cambio que los introduce sea explícito y conozca el prefijo que usa.
 */
import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { I18N_ENTRIES } from "./i18n";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const SRC_DIR = join(__dirname, "..");
const DICT_FILE = join(__dirname, "i18n.ts");

/** Usos dinámicos documentados: claves NO literales que el escáner no puede
 *  resolver (construidas por interpolación o a través de un helper). Si una
 *  nueva clave dinámica aparece, se añade aquí con su motivo. */
const DYNAMIC_KEY_PREFIXES: string[] = [
  "crossSkill.channel.", // t(`crossSkill.channel.${key}`)
  "gramRoutes.levelStates.", // helper groupKey(state)
  "vocabRoutes.levelStates.", // helper groupKey(state)
  // V3.17 (M3): prefijos dinámicos del Review/SRS y del curso que el escáner
  // estático no puede resolver porque la clave se construye con interpolación.
  "unitReview.window.", // UnitReviewPanel: t(`unitReview.window.${window_days}`)
  "unitReview.state.", // UnitReviewPanel: t(`unitReview.state.${state}`)
  "skill.", // CourseScreen/UnitReviewPanel: t(`skill.${section|skill}`)
  "fsrs.whyReason.", // FsrsReviewPanel: t(`fsrs.whyReason.${explain.why}`)
];

function walkTsFiles(dir: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      found.push(...walkTsFiles(full));
    } else if (
      /\.(ts|tsx)$/.test(entry.name) &&
      !/\.(test|spec)\.(ts|tsx)$/.test(entry.name)
    ) {
      found.push(full);
    }
  }
  return found;
}

function literalKeysIn(code: string): Set<string> {
  const keys = new Set<string>();
  // t("clave") / t('clave') / t(`clave`) sin interpolación `${…}`.
  const tPattern = /\bt\(\s*["'`]([^"'`$]+)["'`]/g;
  // translate(lang, "clave") — captura el segundo argumento literal.
  const translatePattern = /\btranslate\([^,)]*,\s*["'`]([^"'`$]+)["'`]/g;
  for (const pattern of [tPattern, translatePattern]) {
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(code)) !== null) {
      keys.add(match[1]);
    }
  }
  return keys;
}

describe("i18n parity (V3.13, P2.2)", () => {
  it("todas las claves declaran `en` y `es` no vacíos", () => {
    const keys = Object.keys(I18N_ENTRIES);
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) {
      const entry = I18N_ENTRIES[key];
      expect(typeof entry, `key ${key}`).toBe("object");
      expect(String(entry.en ?? "").trim().length, `key ${key} .en`).toBeGreaterThan(0);
      expect(String(entry.es ?? "").trim().length, `key ${key} .es`).toBeGreaterThan(0);
    }
  });

  it("no hay claves duplicadas en el diccionario", () => {
    const source = readFileSync(DICT_FILE, "utf8");
    const seen = new Map<string, number>();
    const keyPattern = /^\s*"([^"]+)"\s*:\s*\{/gm;
    let match: RegExpExecArray | null;
    while ((match = keyPattern.exec(source)) !== null) {
      seen.set(match[1], (seen.get(match[1]) ?? 0) + 1);
    }
    const duplicated = [...seen.entries()]
      .filter(([, count]) => count > 1)
      .map(([key]) => key);
    expect(duplicated, "claves definidas más de una vez").toEqual([]);
    // Todas las claves usadas por el runtime están en el objeto exportado.
    expect(seen.size).toBe(keysOfEntries());
  });

  it("toda clave usada de forma estática resuelve a una clave declarada", () => {
    const declared = new Set(Object.keys(I18N_ENTRIES));
    const used = new Set<string>();
    const skipped = new Set([
      join(__dirname, "i18n.ts"),
      join(__dirname, "useI18n.tsx"),
    ]);
    for (const file of walkTsFiles(SRC_DIR)) {
      if (skipped.has(file)) continue;
      const code = readFileSync(file, "utf8");
      for (const key of literalKeysIn(code)) used.add(key);
    }
    // Filtra el prefijo dinámico documentado (allow-list).
    const unresolved = [...used].filter(
      (key) =>
        !declared.has(key) &&
        !DYNAMIC_KEY_PREFIXES.some((prefix) => key.startsWith(prefix)),
    );
    expect(unresolved, "claves usadas sin declarar").toEqual([]);
  });
});

function keysOfEntries(): number {
  return Object.keys(I18N_ENTRIES).length;
}
