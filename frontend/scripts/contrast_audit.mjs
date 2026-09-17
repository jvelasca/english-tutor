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
 *     los 7 acentos y en los dos temas.
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

/* ------------------------------ guardas --------------------------------- */

// El acento sólido no puede usarse como color de texto: para eso está
// `--color-accent-soft`, que se deriva del acento y sí cumple AA.
const solidAsText = [...legacy.matchAll(/^\s+color:\s*var\(--color-accent\);/gm)].length;
// La derivación de `--color-accent-soft` es un contrato: si desaparece, la
// medición deja de corresponderse con lo que se pinta.
const derivedSoft = /--color-accent-soft:\s*color-mix\(/s.test(legacy);
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
];

/* ------------------------------- report --------------------------------- */

const enforced = results.filter((r) => r.enforced);
const reported = results.filter((r) => !r.enforced);
const enforcedFails = enforced.filter((r) => r.ratio < r.min);
const reportedFails = reported.filter((r) => r.ratio < r.min);
const guardFails = guards.filter((g) => !g.ok);

const payload = {
  audit: "V3.73.1-cierre-gui",
  standard: "WCAG 2.2 AA (1.4.3 texto 4.5:1 · 1.4.11 UI 3:1)",
  enforced_failures: enforcedFails.length + guardFails.length,
  reported_failures: reportedFails.length,
  guards,
  results,
};

const md = [];
md.push("# Informe de contraste WCAG (cierre GUI pre-V4.0, V3.73.1)");
md.push("");
md.push("> Generado por `node frontend/scripts/contrast_audit.mjs`.");
md.push("");
md.push(
  `- Pares que BLOQUEAN (tipografía base + texto de acento + guardas): **${enforcedFails.length + guardFails.length} fallos** de ${enforced.length + guards.length}.`,
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
