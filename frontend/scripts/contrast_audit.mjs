/**
 * Auditoría de contraste WCAG del sistema de apariencia (cierre GUI pre-V4.0,
 * V3.73.1).
 *
 * Lee los tokens reales de `src/styles/legacy.css` y `src/index.css` (no una
 * copia a mano, que es como se desincronizan estas cosas), calcula la razón de
 * contraste de cada par texto/fondo del producto y escribe el informe en
 * `docs/audit/generated/contrast-report.{json,md}`.
 *
 * Pares ENFORCED (el script sale 1 si bajan de AA):
 *   - la tipografía base sobre las superficies del sistema, en los dos temas;
 *   - el TEXTO de acento (`--color-accent-soft`) sobre las superficies y sobre
 *     los fondos compuestos donde vive (anillo de acento y tinte al 15 %), en
 *     los 7 acentos y en los dos temas;
 *   - la RAMPA DE NIVELES (V3.75.4): la tinta de cada paso (Pre-A1…C2 y «sin
 *     dato») sobre su propio relleno compuesto, en los 3 esquemas
 *     (`data-levels`), los 2 temas y —en «Monocromo», que sale del acento— los
 *     7 acentos;
 *   - el COLOR DE DIRECCIÓN del diccionario (V3.75.8): la tinta de EN→ES y de
 *     ES→EN sobre su relleno compuesto, en los 2 temas. Esa pareja no sigue al
 *     acento (es una convención del diccionario: azul ↔ fucsia), así que se mide
 *     con un solo acento.
 *
 * Pares REPORTED (se miden y se publican, pero no bloquean): el relleno de
 * acento con su tinta encima (`--color-on-accent`) y el acento como borde/UI.
 * El acento es a la vez relleno (con tinta encima) y color de borde, y las dos
 * funciones piden luminosidades opuestas a la rampa actual: con la MEJOR tinta
 * posible el máximo alcanzable se queda entre 3.4:1 y 4.2:1, así que cumplir AA
 * exige re-rampar los 7 acentos (p. ej. 600/700 como relleno en tema claro), una
 * decisión de diseño con impacto visual que corresponde a V4.0.x. Aquí se mide,
 * se publica el máximo alcanzable con cada tinta y se deja la decisión con
 * números.
 *
 * GUARDA: el acento sólido no se usa como color de texto (para eso está
 * `--color-accent-soft`, que se deriva del acento y cumple AA). El script falla
 * si vuelve a aparecer un `color: var(--color-accent)`.
 *
 * Uso:
 *   node scripts/contrast_audit.mjs
 *   node scripts/contrast_audit.mjs --strict   # exit 1 si falla algo ENFORCED
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const LEGACY = path.join(ROOT, "frontend", "src", "styles", "legacy.css");
const INDEX = path.join(ROOT, "frontend", "src", "index.css");
const OUT = path.join(ROOT, "docs", "audit", "generated");

const AA_TEXT = 4.5;
const AA_UI = 3;

/* ------------------------------ color math ------------------------------ */

function parseHex(value) {
  const hex = value.trim().replace(/^#/, "");
  const full =
    hex.length === 3
      ? hex
          .split("")
          .map((c) => c + c)
          .join("")
      : hex;
  return {
    r: parseInt(full.slice(0, 2), 16),
    g: parseInt(full.slice(2, 4), 16),
    b: parseInt(full.slice(4, 6), 16),
  };
}

function channel(value) {
  const c = value / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function luminance(hex) {
  const { r, g, b } = parseHex(hex);
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

export function contrast(fg, bg) {
  const a = luminance(fg);
  const b = luminance(bg);
  const [hi, lo] = a >= b ? [a, b] : [b, a];
  return (hi + 0.05) / (lo + 0.05);
}

const ratio = (fg, bg) => Math.round(contrast(fg, bg) * 100) / 100;
const toHex = ({ r, g, b }) =>
  `#${[r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("")}`;

/** `color-mix(in srgb, a (100-share)%, b)`: mezcla por componentes en sRGB. */
function mix(a, b, shareOfA) {
  const A = parseHex(a);
  const B = parseHex(b);
  return toHex({
    r: (A.r * shareOfA + B.r * (100 - shareOfA)) / 100,
    g: (A.g * shareOfA + B.g * (100 - shareOfA)) / 100,
    b: (A.b * shareOfA + B.b * (100 - shareOfA)) / 100,
  });
}

/** Compone un `rgba(...)` sobre un fondo opaco. */
function over(rgba, bg) {
  const B = parseHex(bg);
  return toHex({
    r: rgba.r * rgba.a + B.r * (1 - rgba.a),
    g: rgba.g * rgba.a + B.g * (1 - rgba.a),
    b: rgba.b * rgba.a + B.b * (1 - rgba.a),
  });
}

function parseRgba(value) {
  const m = /rgba?\(([^)]+)\)/.exec(value);
  const parts = m[1].split(",").map((p) => Number(p.trim()));
  return { r: parts[0], g: parts[1], b: parts[2], a: parts[3] ?? 1 };
}

/* ------------------------------ CSS parsing ----------------------------- */

/** Extrae las declaraciones `--token: valor;` del bloque que empieza en `start`. */
function blockTokens(css, selector) {
  const at = css.indexOf(selector);
  if (at < 0) return {};
  const open = css.indexOf("{", at);
  const close = css.indexOf("}", open);
  const body = css.slice(open + 1, close);
  const tokens = {};
  for (const m of body.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/gi)) {
    tokens[m[1]] = m[2].trim();
  }
  return tokens;
}

const legacy = fs.readFileSync(LEGACY, "utf8");
const index = fs.readFileSync(INDEX, "utf8");

const THEMES = [
  {
    id: "dark",
    label: "Oscuro",
    tokens: { ...blockTokens(legacy, ":root {"), ...blockTokens(index, ":root {") },
  },
  {
    id: "light",
    label: "Claro",
    tokens: {
      ...blockTokens(legacy, ':root[data-theme="light"]'),
      ...blockTokens(index, ':root[data-theme="light"]'),
    },
  },
];

/** Los 7 acentos: el índigo vive en el bloque raíz (no tiene override). */
const ACCENTS = [
  { id: "indigo", tokens: {} },
  { id: "violet", tokens: blockTokens(legacy, ':root[data-accent="violet"]') },
  { id: "blue", tokens: blockTokens(legacy, ':root[data-accent="blue"]') },
  { id: "teal", tokens: blockTokens(legacy, ':root[data-accent="teal"]') },
  { id: "emerald", tokens: blockTokens(legacy, ':root[data-accent="emerald"]') },
  { id: "rose", tokens: blockTokens(legacy, ':root[data-accent="rose"]') },
  { id: "amber", tokens: blockTokens(legacy, ':root[data-accent="amber"]') },
];

function resolve(theme, accent, token) {
  // Precedencia real del navegador: bloque de acento > bloque de tema > raíz.
  return (
    accent.tokens[token] ??
    theme.tokens[token] ??
    blockTokens(legacy, ":root {")[token] ??
    null
  );
}

/**
 * `--color-accent-soft` NO es un hex fijo: `legacy.css` lo deriva del acento
 * elegido con `color-mix(in srgb, var(--color-accent) var(--accent-soft-share),
 * var(--accent-soft-target))`. El script reproduce esa mezcla (si allí cambia la
 * fórmula, aquí hay que cambiarla) para medir el color real que ve el alumno con
 * cada uno de los 7 acentos y en los dos temas.
 */
function accentSoft(theme, accent) {
  const accentHex = resolve(theme, accent, "--color-accent");
  const target = resolve(theme, accent, "--accent-soft-target");
  const share = Number(String(resolve(theme, accent, "--accent-soft-share")).replace("%", ""));
  if (!accentHex || !target || !Number.isFinite(share)) {
    throw new Error(
      `No se pudo derivar --color-accent-soft para ${theme.id}/${accent.id} ` +
        `(acento=${accentHex}, objetivo=${target}, share=${share})`,
    );
  }
  return mix(accentHex, target, share);
}

/** Fondos compuestos donde vive el texto de acento: anillo y tinte al 15 %. */
function composites(theme, accent) {
  const ring = parseRgba(resolve(theme, accent, "--color-accent-ring"));
  const accentHex = resolve(theme, accent, "--color-accent");
  const surfaces = ["--color-bg", "--color-surface", "--color-bg-soft"];
  const out = [];
  for (const token of surfaces) {
    const bg = resolve(theme, accent, token);
    out.push({ label: `anillo de acento sobre ${token}`, value: over(ring, bg) });
    out.push({
      label: `tinte de acento al 15 % sobre ${token}`,
      value: over({ ...parseHex(accentHex), a: 0.15 }, bg),
    });
  }
  return out;
}

/* ------------------------- rampa de niveles (V3.75.4) -------------------- */

/**
 * Los siete pasos del MCER más el cajón de «sin dato», en orden. Es el orden que
 * usan `utils/cefr.ts` (`LEVEL_KEYS`) y las tablas del informe.
 */
const LEVEL_STEPS = [
  ["pre-a1", "Pre-A1"],
  ["a1", "A1"],
  ["a2", "A2"],
  ["b1", "B1"],
  ["b2", "B2"],
  ["c1", "C1"],
  ["c2", "C2"],
  ["unknown", "s/d"],
];

const LEVEL_SCHEMES = [
  { id: "traffic", label: "Semáforo" },
  { id: "spectrum", label: "Espectro" },
  { id: "mono", label: "Monocromo" },
];

/** Relleno de la insignia: `color-mix(in srgb, <tinta> 15%, transparent)`. */
const LEVEL_FILL_SHARE = 15;

/** Superficies sobre las que se apoya una insignia o un chip teñido. */
const LEVEL_SURFACES = ["--color-bg", "--color-surface"];

/**
 * Bloque de tokens donde vive la tinta de un paso. «Semáforo» es el esquema por
 * defecto, así que sus siete hexes están en el bloque raíz / de tema; los otros
 * dos se declaran con `data-levels`.
 */function levelBlockTokens(scheme, theme) {
  if (scheme === "traffic") return theme.tokens;
  const themed = blockTokens(
    legacy,
    `:root[data-theme="${theme.id}"][data-levels="${scheme}"]`,
  );
  if (Object.keys(themed).length > 0) return themed;
  // Los esquemas que no necesitan hexes por tema (Monocromo se deriva del
  // acento, que ya es distinto en claro y oscuro) declaran un solo bloque.
  return blockTokens(legacy, `:root[data-levels="${scheme}"]`);
}

/** Resuelve `var(--token)` a su valor real; deja el resto tal cual. */
function deref(theme, accent, raw) {
  const ref = /^var\(\s*(--[a-z0-9-]+)\s*\)$/i.exec(raw);
  return ref ? resolve(theme, accent, ref[1]) : raw;
}

/**
 * Tinta de un paso. En «Monocromo» la rampa NO son hexes: `legacy.css` la
 * deriva del acento del usuario con `color-mix(in srgb, var(--color-accent-soft)
 * N%, var(--color-text-dim))`, así que aquí se reproduce esa mezcla leyendo el
 * porcentaje REAL del CSS (si allí cambia la fórmula, esto lanza en vez de medir
 * otro color).
 */
function levelFg(theme, accent, scheme, key) {
  const tokens = levelBlockTokens(scheme, theme);
  const raw = tokens[`--level-${key}-fg`];
  if (!raw) {
    throw new Error(
      `Falta --level-${key}-fg para el esquema «${scheme}» en tema ${theme.id}`,
    );
  }
  if (!/color-mix\(/i.test(raw)) return deref(theme, accent, raw);
  const m = /color-mix\(\s*in srgb\s*,\s*var\(\s*(--[a-z0-9-]+)\s*\)\s+([\d.]+)%\s*,\s*var\(\s*(--[a-z0-9-]+)\s*\)\s*\)/i.exec(
    raw,
  );
  if (!m) {
    throw new Error(
      `color-mix() de --level-${key}-fg con forma inesperada: ${raw}`,
    );
  }
  const [, fromToken, shareRaw, toToken] = m;
  const share = Number(shareRaw);
  const from =
    fromToken === "--color-accent-soft"
      ? accentSoft(theme, accent)
      : resolve(theme, accent, fromToken);
  const to = resolve(theme, accent, toToken);
  if (!from || !to) {
    throw new Error(`No se pudo resolver la mezcla de --level-${key}-fg`);
  }
  return mix(from, to, share);
}

/** Relleno compuesto real de la insignia sobre una superficie opaca. */
function levelFill(fgHex, surfaceHex) {
  return over({ ...parseHex(fgHex), a: LEVEL_FILL_SHARE / 100 }, surfaceHex);
}

/* ------------------------------- pairs ---------------------------------- */

// Superficies sobre las que se pinta texto, por tema.
const BASE_PAIRS = [
  ["--color-text", "--color-bg", "texto principal sobre el fondo"],
  ["--color-text", "--color-surface", "texto principal sobre tarjeta"],
  ["--color-text-dim", "--color-bg", "texto secundario sobre el fondo"],
  ["--color-text-dim", "--color-surface", "texto secundario sobre tarjeta"],
  ["--color-text-dim", "--color-bg-soft", "texto secundario sobre superficie suave"],
  ["--color-text-faint", "--color-bg", "texto terciario sobre el fondo"],
  ["--color-text-faint", "--color-surface", "texto terciario sobre tarjeta"],
  ["--color-text-faint", "--color-bg-soft", "texto terciario sobre superficie suave"],
];

// Superficies sobre las que vive el texto de acento.
const ACCENT_TEXT_SURFACES = ["--color-bg", "--color-surface", "--color-bg-soft"];

// Pares REPORTADOS: relleno + tinta y acento como borde. El script añade, para
// cada uno, la mejor tinta posible y el máximo alcanzable con la rampa actual.
const ACCENT_REPORTED_PAIRS = [
  ["--color-on-accent", "--color-accent", "relleno + tinta (botones, píldora activa)", AA_TEXT],
  ["--color-on-accent", "--color-accent-hover", "relleno en hover + tinta", AA_TEXT],
  ["--color-accent", "--color-surface", "acento como BORDE/UI sobre tarjeta", AA_UI],
];

const INKS = ["#ffffff", "#0b1220", "#1f2937", "#111827", "#f8fafc"];

const results = [];

for (const theme of THEMES) {
  for (const [fg, bg, label] of BASE_PAIRS) {
    const fgv = resolve(theme, ACCENTS[0], fg);
    const bgv = resolve(theme, ACCENTS[0], bg);
    results.push({
      scope: "base",
      theme: theme.id,
      accent: null,
      label: `${label} (${fg} / ${bg})`,
      fg: fgv,
      bg: bgv,
      ratio: ratio(fgv, bgv),
      min: AA_TEXT,
      enforced: true,
    });
  }

  for (const accent of ACCENTS) {
    const soft = accentSoft(theme, accent);
    const surfaces = ACCENT_TEXT_SURFACES.map((token) => ({
      label: token,
      value: resolve(theme, accent, token),
    }));
    for (const { label, value } of [...surfaces, ...composites(theme, accent)]) {
      results.push({
        scope: "accent-text",
        theme: theme.id,
        accent: accent.id,
        label: `texto de acento (--color-accent-soft) sobre ${label}`,
        fg: soft,
        bg: value,
        ratio: ratio(soft, value),
        min: AA_TEXT,
        enforced: true,
      });
    }

    for (const [fg, bg, label, min] of ACCENT_REPORTED_PAIRS) {
      const fgv = resolve(theme, accent, fg);
      const bgv = resolve(theme, accent, bg);
      if (!fgv || !bgv) continue;
      // Máximo alcanzable con la mejor tinta posible (relleno + hover).
      const fills = [
        resolve(theme, accent, "--color-accent"),
        resolve(theme, accent, "--color-accent-hover"),
      ].filter(Boolean);
      const bestInk = INKS.map((ink) => ({
        ink,
        best: Math.min(...fills.map((fill) => ratio(ink, fill))),
      })).sort((a, b) => b.best - a.best)[0];
      results.push({
        scope: "accent",
        theme: theme.id,
        accent: accent.id,
        label: `${label} (${fg} / ${bg})`,
        fg: fgv,
        bg: bgv,
        ratio: ratio(fgv, bgv),
        min,
        enforced: false,
        best_ink: bestInk.ink,
        best_possible: bestInk.best,
      });
    }
  }
}

/* --------------------- rampa de niveles: medición ----------------------- */

// La rampa de niveles se mide por esquema y por tema: cada paso declara su
// tinta y de ella se DERIVA el relleno (`color-mix(..., 15%, transparent)`), así
// que medir la tinta sobre el relleno compuesto es medir lo que ve el alumno.
// «Monocromo» se mide en los 7 acentos porque su rampa entera sale del acento.
for (const scheme of LEVEL_SCHEMES) {
  const accents = scheme.id === "mono" ? ACCENTS : [ACCENTS[0]];
  for (const theme of THEMES) {
    for (const accent of accents) {
      for (const [key, label] of LEVEL_STEPS) {
        const fg = levelFg(theme, accent, scheme.id, key);
        for (const surfaceToken of LEVEL_SURFACES) {
          const surface = resolve(theme, accent, surfaceToken);
          const bg = levelFill(fg, surface);
          results.push({
            scope: "level-ramp",
            scheme: scheme.id,
            step: key,
            step_label: label,
            theme: theme.id,
            accent: scheme.id === "mono" ? accent.id : null,
            surface: surfaceToken,
            label:
              `tinta del nivel ${label} (--level-${key}-fg) sobre su relleno ` +
              `al ${LEVEL_FILL_SHARE} % sobre ${surfaceToken}`,
            fg,
            bg,
            ratio: ratio(fg, bg),
            min: AA_TEXT,
            enforced: true,
          });
        }
      }
    }
  }
}

/* ------------------ color de dirección del diccionario (V3.75.8) --------- */

/**
 * Las dos direcciones del diccionario de consulta, en el orden en que se
 * ofrecen. Espejo de `frontend/src/utils/dictionaryDirection.ts`.
 */
const DIRECTION_STEPS = [
  ["en-es", "EN→ES"],
  ["es-en", "ES→EN"],
];

/**
 * Reparto del relleno de dirección, leído del CSS
 * (`--dir-en-es-bg: color-mix(in srgb, var(--dir-en-es-fg) N%, transparent)`).
 * A diferencia de la rampa de niveles, aquí SÍ se lee el porcentaje real: si
 * cambia la fórmula, la medición sigue midiendo lo que se pinta en vez de otro
 * color. Devuelve `null` si el token no está declarado (lo denuncia la guarda
 * `direccion-clases-y-derivados`).
 */
function dirFillShare() {
  const m =
    /--dir-en-es-bg:\s*color-mix\(\s*in srgb\s*,\s*var\(\s*--dir-en-es-fg\s*\)\s+([\d.]+)%\s*,\s*transparent\s*\)/i.exec(
      legacy,
    );
  return m ? Number(m[1]) : null;
}

const DIR_FILL_SHARE = dirFillShare();

// Las tintas de dirección no dependen del acento del usuario (son una
// convención del diccionario), así que se miden una sola vez por tema.
if (DIR_FILL_SHARE !== null) {
  for (const theme of THEMES) {
    for (const [key, label] of DIRECTION_STEPS) {
      const fg = resolve(theme, ACCENTS[0], `--dir-${key}-fg`);
      if (!fg) continue; // la guarda de completitud lo denuncia
      for (const surfaceToken of LEVEL_SURFACES) {
        const surface = resolve(theme, ACCENTS[0], surfaceToken);
        const bg = over({ ...parseHex(fg), a: DIR_FILL_SHARE / 100 }, surface);
        results.push({
          scope: "dir-tint",
          theme: theme.id,
          accent: null,
          direction: key,
          direction_label: label,
          surface: surfaceToken,
          label:
            `tinta de la dirección ${label} (--dir-${key}-fg) sobre su relleno ` +
            `al ${DIR_FILL_SHARE} % sobre ${surfaceToken}`,
          fg,
          bg,
          ratio: ratio(fg, bg),
          min: AA_TEXT,
          enforced: true,
        });
      }
    }
  }
}

// El acento sólido no puede usarse como color de texto: para eso está
// `--color-accent-soft`, que se deriva del acento y sí cumple AA.
const solidAsText = [...legacy.matchAll(/^\s+color:\s*var\(--color-accent\);/gm)].length;

// La derivación de `--color-accent-soft` es un contrato: si desaparece, la
// medición deja de corresponderse con lo que se pinta.
const derivedSoft = /--color-accent-soft:\s*color-mix\(/s.test(legacy);
// La rampa es un contrato de tres piezas: el token de cada paso en los tres
// esquemas, el relleno/borde derivados y la clase estática que los consume. Si
// alguna se cae, `levelClass()` devuelve una clase que no pinta nada y la app se
// queda sin color de nivel sin que ningún test unitario se entere.
const rampMissing = [];
for (const scheme of LEVEL_SCHEMES) {
  for (const theme of THEMES) {
    const tokens = levelBlockTokens(scheme.id, theme);
    for (const [key] of LEVEL_STEPS) {
      if (!tokens[`--level-${key}-fg`]) {
        rampMissing.push(`${scheme.id}/${theme.id}/--level-${key}-fg`);
      }
    }
  }
}
const rampDerivedMissing = [];
const baseTokens = blockTokens(legacy, ":root {");
for (const [key] of LEVEL_STEPS) {
  for (const suffix of ["bg", "border"]) {
    if (!baseTokens[`--level-${key}-${suffix}`]) {
      rampDerivedMissing.push(`--level-${key}-${suffix}`);
    }
  }
}
for (const key of [...LEVEL_STEPS.map(([k]) => k), "outline", "ink", "quiet"]) {
  if (!new RegExp(`\\.lv-${key}\\s*\\{`).test(legacy)) {
    rampDerivedMissing.push(`.lv-${key}`);
  }
}
// La dirección es el mismo contrato de tres piezas que la rampa: la tinta en
// cada tema, el relleno/borde derivados y la clase estática que los consume.
// `directionClass()` devuelve una clase: si esa clase no existe, el buscador se
// queda sin color de dirección sin que ningún test unitario se entere.
const dirMissing = [];
for (const theme of THEMES) {
  for (const [key] of DIRECTION_STEPS) {
    if (!resolve(theme, ACCENTS[0], `--dir-${key}-fg`)) {
      dirMissing.push(`${theme.id}/--dir-${key}-fg`);
    }
  }
}
const dirDerivedMissing = [];
for (const [key] of DIRECTION_STEPS) {
  for (const suffix of ["bg", "border"]) {
    if (!baseTokens[`--dir-${key}-${suffix}`]) {
      dirDerivedMissing.push(`--dir-${key}-${suffix}`);
    }
  }
}
// Clases consumidoras de `styles/legacy.css`: el paso (tinta/relleno/borde en
// variables locales) y los modificadores que pintan.
for (const cls of [
  ...DIRECTION_STEPS.map(([key]) => `dir-${key}`),
  "dir-chip",
  "dir-ink",
  "dir-line",
  "dir-wash",
  "dir-bar",
  "dir-field",
]) {
  if (!new RegExp(`^\\.${cls}(\\s*[,{:])`, "m").test(legacy)) {
    dirDerivedMissing.push(`.${cls}`);
  }
}
const guards = [
  {
    id: "acento-solido-no-es-texto",
    ok: solidAsText === 0,
    detail:
      solidAsText === 0
        ? "ningún `color: var(--color-accent)` (el texto de acento usa --color-accent-soft)"
        : `${solidAsText} regla(s) usan el acento sólido como color de texto`,
  },
  {
    id: "accent-soft-derivado",
    ok: derivedSoft,
    detail: derivedSoft
      ? "--color-accent-soft se deriva del acento con color-mix()"
      : "falta la derivación `--color-accent-soft: color-mix(...)` en legacy.css",
  },
  {
    id: "rampa-niveles-completa",
    ok: rampMissing.length === 0,
    detail:
      rampMissing.length === 0
        ? "los 7 pasos (+ sin dato) declaran su tinta en los 3 esquemas y los 2 temas"
        : `faltan tokens de la rampa: ${rampMissing.join(", ")}`,
  },
  {
    id: "rampa-clases-y-derivados",
    ok: rampDerivedMissing.length === 0,
    detail:
      rampDerivedMissing.length === 0
        ? "cada paso tiene relleno y borde derivados y su clase .lv-*, más los modificadores .lv-outline/.lv-ink/.lv-quiet"
        : `faltan piezas de la rampa: ${rampDerivedMissing.join(", ")}`,
  },
  {
    id: "direccion-completa",
    ok: dirMissing.length === 0,
    detail:
      dirMissing.length === 0
        ? "las dos direcciones (EN→ES, ES→EN) declaran su tinta en los 2 temas"
        : `faltan tintas de dirección: ${dirMissing.join(", ")}`,
  },
  {
    id: "direccion-clases-y-derivados",
    ok: dirDerivedMissing.length === 0 && DIR_FILL_SHARE !== null,
    detail:
      dirDerivedMissing.length === 0 && DIR_FILL_SHARE !== null
        ? `cada dirección tiene relleno (${DIR_FILL_SHARE} %) y borde derivados, su clase .dir-*, los modificadores .dir-chip/.dir-ink/.dir-line/.dir-wash/.dir-bar y el marco .dir-field`
        : `faltan piezas de la dirección: ${[
            ...dirDerivedMissing,
            ...(DIR_FILL_SHARE === null ? ["--dir-en-es-bg (reparto ilegible)"] : []),
          ].join(", ")}`,
  },
];

/* ------------------------------- report --------------------------------- */

const enforced = results.filter((r) => r.enforced);
const reported = results.filter((r) => !r.enforced);
const enforcedFails = enforced.filter((r) => r.ratio < r.min);
const reportedFails = reported.filter((r) => r.ratio < r.min);
const guardFails = guards.filter((g) => !g.ok);

const payload = {
  audit: "V3.75.8-rampa-niveles-direccion",
  standard: "WCAG 2.2 AA (1.4.3 texto 4.5:1 · 1.4.11 UI 3:1)",
  enforced_failures: enforcedFails.length + guardFails.length,
  reported_failures: reportedFails.length,
  guards,
  results,
};

const md = [];
md.push("# Informe de contraste WCAG (cierre GUI pre-V4.0 · rampa de niveles V3.75.4 · dirección del diccionario V3.75.8)");
md.push("");
md.push("> Generado por `node frontend/scripts/contrast_audit.mjs`.");
md.push("");
md.push(
  `- Pares que BLOQUEAN (tipografía base + texto de acento + rampa de niveles + dirección + guardas): **${enforcedFails.length + guardFails.length} fallos** de ${enforced.length + guards.length}.`,
);
md.push(
  `- Pares de acento reportados (relleno + tinta y borde): **${reportedFails.length} fallos** de ${reported.length}.`,
);
md.push("");
md.push("## Tipografía base sobre superficies (bloqueante)");
md.push("");
md.push("| Tema | Par | Razón | Mínimo | Estado |");
md.push("| --- | --- | ---: | ---: | --- |");
for (const r of enforced.filter((x) => x.scope === "base")) {
  md.push(
    `| ${r.theme} | ${r.label} | ${r.ratio} | ${r.min} | ${r.ratio >= r.min ? "OK" : "FALLA"} |`,
  );
}
md.push("");
md.push("## Texto de acento derivado del acento elegido (bloqueante)");
md.push("");
md.push(
  "`--color-accent-soft` se mezcla desde el acento del usuario " +
    "(`--accent-soft-share` hacia blanco en oscuro y hacia negro en claro). Se mide " +
    "sobre las superficies y sobre los fondos compuestos donde vive ese texto.",
);
md.push("");
md.push("| Tema | Acento | Fondo | Razón | Mínimo | Estado |");
md.push("| --- | --- | --- | ---: | ---: | --- |");
for (const r of enforced.filter((x) => x.scope === "accent-text")) {
  md.push(
    `| ${r.theme} | ${r.accent} | ${r.label.replace("texto de acento (--color-accent-soft) sobre ", "")} | ${r.ratio} | ${r.min} | ${r.ratio >= r.min ? "OK" : "FALLA"} |`,
  );
}
md.push("");
md.push("## Rampa de niveles por esquema y tema (bloqueante)");
md.push("");
md.push(
  "Cada paso (Pre-A1 → C2, más el cajón «sin dato») declara su tinta y el " +
    `relleno se DERIVA de ella al ${LEVEL_FILL_SHARE} %; se mide la tinta sobre ese ` +
    "relleno compuesto sobre las dos superficies donde viven insignias, bandas y " +
    "chips. «Monocromo» sale del acento del usuario, así que se mide en los 7. " +
    "El relleno es translúcido: sobre otro fondo (p. ej. `--color-surface-2`, más " +
    "cercano a la tinta) el margen se estrecha, y por eso las tintas de la rampa " +
    "se eligen con holgura y no al filo del 4.5:1.",
);
md.push("");
md.push(
  `| Esquema | Tema | Acento | Fondo | ${LEVEL_STEPS.map(([, l]) => l).join(" | ")} |`,
);
md.push(`| --- | --- | --- | --- | ${LEVEL_STEPS.map(() => "---:").join(" | ")} |`);
{
  const levelRows = enforced.filter((r) => r.scope === "level-ramp");
  const order = [];
  const byRow = new Map();
  for (const r of levelRows) {
    const id = `${r.scheme}|${r.theme}|${r.accent ?? ""}|${r.surface}`;
    if (!byRow.has(id)) {
      byRow.set(id, new Map());
      order.push(id);
    }
    byRow.get(id).set(r.step, r);
  }
  for (const id of order) {
    const cells = byRow.get(id);
    const [schemeId, themeId, accentId, surface] = id.split("|");
    const schemeLabel = LEVEL_SCHEMES.find((s) => s.id === schemeId).label;
    const themeLabel = THEMES.find((t) => t.id === themeId).label;
    const values = LEVEL_STEPS.map(([key]) => {
      const r = cells.get(key);
      return r.ratio >= r.min ? `${r.ratio}` : `**${r.ratio} FALLA**`;
    });
    md.push(
      `| ${schemeLabel} | ${themeLabel} | ${accentId || "—"} | ${surface} | ${values.join(" | ")} |`,
    );
  }
}
md.push("");
md.push("## Dirección de la consulta del diccionario (bloqueante)");
md.push("");
md.push(
  "El sentido de la consulta se ve por su color —azul EN→ES, fucsia ES→EN— y ese " +
    "color se mide igual que la rampa: cada dirección declara su tinta y el " +
    `relleno se DERIVA de ella al ${DIR_FILL_SHARE} %. La pareja no sigue al acento ` +
    "del usuario (es una convención del diccionario, no del perfil), así que se mide " +
    "con un solo acento y en los dos temas.",
);
md.push("");
md.push("| Tema | Dirección | Fondo | Razón | Mínimo | Estado |");
md.push("| --- | --- | --- | ---: | ---: | --- |");
for (const r of enforced.filter((x) => x.scope === "dir-tint")) {
  md.push(
    `| ${r.theme} | ${r.direction_label} | ${r.label.replace(/^.* % sobre /, "")} | ${r.ratio} | ${r.min} | ${r.ratio >= r.min ? "OK" : "FALLA"} |`,
  );
}
md.push("");
md.push("## Guardas");
md.push("");
md.push("| Guarda | Estado | Detalle |");
md.push("| --- | --- | --- |");
for (const g of guards) {
  md.push(`| ${g.id} | ${g.ok ? "OK" : "FALLA"} | ${g.detail} |`);
}
md.push("");
md.push("## Acento como relleno y como borde (reportado; decisión para V4.0.x)");
md.push("");
md.push(
  "Con la mejor tinta posible, el máximo alcanzable sobre el relleno se queda por " +
    "debajo de AA: cumplirlo exige re-rampar los acentos (relleno más oscuro en tema " +
    "claro). La última columna da el techo real de la rampa actual.",
);
md.push("");
md.push("| Tema | Acento | Par | Razón | Mínimo | Mejor tinta | Máx. alcanzable | Estado |");
md.push("| --- | --- | --- | ---: | ---: | --- | ---: | --- |");
for (const r of reported) {
  md.push(
    `| ${r.theme} | ${r.accent} | ${r.label} | ${r.ratio} | ${r.min} | ` +
      `${r.best_ink ?? "—"} | ${r.best_possible ?? "—"} | ${r.ratio >= r.min ? "OK" : "FALLA"} |`,
  );
}
md.push("");

fs.mkdirSync(OUT, { recursive: true });
fs.writeFileSync(path.join(OUT, "contrast-report.json"), `${JSON.stringify(payload, null, 1)}\n`, "utf8");
fs.writeFileSync(path.join(OUT, "contrast-report.md"), md.join("\n"), "utf8");

console.log(`Pares medidos: ${results.length} (+ ${guards.length} guardas)`);
console.log(`  bloqueantes con fallo: ${enforcedFails.length + guardFails.length}`);
console.log(`  acentos con fallo (reportado): ${reportedFails.length}`);
for (const r of enforcedFails) {
  console.log(`  FALLA ${r.theme} · ${r.label}: ${r.ratio} < ${r.min}`);
}
for (const g of guardFails) {
  console.log(`  FALLA guarda ${g.id}: ${g.detail}`);
}
console.log(`  -> ${path.relative(ROOT, path.join(OUT, "contrast-report.json"))}`);

if (process.argv.includes("--strict") && (enforcedFails.length > 0 || guardFails.length > 0)) {
  process.exit(1);
}
