import { expect, test } from "@playwright/test";

/**
 * Guarda de contraste del TEXTO de acento (GUI-06, V3.73.1).
 *
 * `--color-accent-soft` no es un hex fijo: `legacy.css` lo deriva del acento
 * elegido con `color-mix(in srgb, var(--color-accent) var(--accent-soft-share),
 * var(--accent-soft-target))`. Eso significa que el token puede fallar de una
 * forma que ningún test de Node puede ver: si el `var()` dentro del porcentaje
 * no sustituye, el token queda **inválido en tiempo de valor computado** y el
 * texto de acento cae a un color heredado (o transparente).
 *
 * Este test corre en el navegador real: para los 7 acentos y los 2 temas,
 * resuelve el color computado de verdad y comprueba AA (4.5:1) contra las tres
 * superficies del sistema. Es la contrapartida en runtime de
 * `scripts/contrast_audit.mjs` (que mide los tokens sobre el CSS).
 */

const ACCENTS = ["indigo", "violet", "blue", "teal", "emerald", "rose", "amber"];
const THEMES = ["dark", "light"];

/** `#rgb` · `#rrggbb` · `rgb(1, 2, 3)` · `color(srgb 0.1 0.2 0.3)` → [r, g, b]. */
function parseColor(value) {
  const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(value.trim());
  if (hex) {
    const digits =
      hex[1].length === 3
        ? hex[1]
            .split("")
            .map((c) => c + c)
            .join("")
        : hex[1];
    return [0, 2, 4].map((i) => parseInt(digits.slice(i, i + 2), 16));
  }
  const rgb = /rgba?\(([^)]+)\)/.exec(value);
  if (rgb) {
    const parts = rgb[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    return parts.slice(0, 3);
  }
  const srgb = /color\(srgb\s+([^)]+)\)/.exec(value);
  if (srgb) {
    return srgb[1]
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 3)
      .map((v) => Number(v) * 255);
  }
  throw new Error(`color no reconocido: ${value}`);
}

function luminance([r, g, b]) {
  const channel = (v) => {
    const c = v / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrast(fg, bg) {
  const a = luminance(fg);
  const b = luminance(bg);
  const [hi, lo] = a >= b ? [a, b] : [b, a];
  return (hi + 0.05) / (lo + 0.05);
}

test.describe("texto de acento derivado del acento elegido", () => {
  test("los 7 acentos cumplen AA en los dos temas (color computado real)", async ({ page }) => {
    test.skip(test.info().project.name !== "desktop", "guarda de token: basta una vez");
    await page.goto("/#/aprender");

    const results = await page.evaluate(
      ({ accents, themes }) => {
        const root = document.documentElement;
        const probe = document.createElement("span");
        probe.textContent = "Aa";
        probe.style.position = "absolute";
        probe.style.color = "var(--color-accent-soft)";
        root.appendChild(probe);
        const read = (token) => getComputedStyle(root).getPropertyValue(token).trim();
        const out = [];
        for (const theme of themes) {
          for (const accent of accents) {
            root.setAttribute("data-theme", theme);
            root.setAttribute("data-accent", accent);
            out.push({
              theme,
              accent,
              soft: getComputedStyle(probe).color,
              surfaces: {
                "--color-bg": read("--color-bg"),
                "--color-surface": read("--color-surface"),
                "--color-bg-soft": read("--color-bg-soft"),
              },
              accentValue: read("--color-accent"),
            });
          }
        }
        probe.remove();
        return out;
      },
      { accents: ACCENTS, themes: THEMES },
    );

    expect(results).toHaveLength(ACCENTS.length * THEMES.length);

    for (const row of results) {
      const soft = parseColor(row.soft);
      const where = `${row.theme}/${row.accent}`;
      // El token se deriva: nunca puede ser exactamente el acento sólido.
      expect(row.soft, `${where}: sin derivar (¿color-mix inválido?)`).not.toBe(
        row.accentValue.toLowerCase(),
      );
      for (const [token, value] of Object.entries(row.surfaces)) {
        const min = 4.5;
        const got = contrast(soft, parseColor(value));
        expect(
          got,
          `${where}: texto de acento sobre ${token} = ${got.toFixed(2)}:1 (mínimo ${min})`,
        ).toBeGreaterThanOrEqual(min);
      }
    }
  });
});
