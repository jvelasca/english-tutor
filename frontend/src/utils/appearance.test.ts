import { describe, expect, it } from "vitest";
import {
  ACCENTS,
  DEFAULT_APPEARANCE,
  LEVEL_SCHEMES,
  appearanceFromSettings,
  appearanceToSettings,
  parseAppearance,
  resolveAppearance,
  serializeAppearance,
} from "./appearance";

describe("appearance", () => {
  it("resuelve apariencia por defecto cuando no hay nada persistido", () => {
    const a = resolveAppearance(null, "light");
    expect(a.theme).toBe("light");
    expect(a.accent).toBe(DEFAULT_APPEARANCE.accent);
    expect(a.fontScale).toBe("medium");
    expect(a.density).toBe("comfortable");
    expect(a.levelScheme).toBe("traffic");
  });

  it("prioriza el tema persistido sobre el del sistema", () => {
    const a = resolveAppearance(
      JSON.stringify({ ...DEFAULT_APPEARANCE, theme: "dark" }),
      "light",
    );
    expect(a.theme).toBe("dark");
  });

  it("tolera JSON corrupto", () => {
    const a = parseAppearance("not-json{{{");
    expect(a).toEqual(DEFAULT_APPEARANCE);
  });

  it("tolera campos inválidos cayendo a los por defecto", () => {
    const a = parseAppearance(
      JSON.stringify({ theme: "neon", accent: "bogus", fontScale: 99 }),
    );
    expect(a.accent).toBe(DEFAULT_APPEARANCE.accent);
    expect(a.fontScale).toBe(DEFAULT_APPEARANCE.fontScale);
    expect(a.theme).toBe(DEFAULT_APPEARANCE.theme);
    expect(a.levelScheme).toBe(DEFAULT_APPEARANCE.levelScheme);
  });

  it("serializa y parsea de vuelta la misma apariencia", () => {
    const original = {
      theme: "light" as const,
      accent: "rose" as const,
      fontScale: "large" as const,
      density: "compact" as const,
      levelScheme: "spectrum" as const,
    };
    expect(parseAppearance(serializeAppearance(original))).toEqual(original);
  });

  it("convierte a claves de settings del backend", () => {
    expect(
      appearanceToSettings({
        theme: "dark",
        accent: "teal",
        fontScale: "small",
        density: "compact",
        levelScheme: "mono",
      }),
    ).toEqual({
      theme: "dark",
      accent: "teal",
      font_scale: "small",
      density: "compact",
      level_scheme: "mono",
    });
  });

  it("lee solo campos de apariencia válidos desde settings", () => {
    expect(
      appearanceFromSettings({
        theme: "light",
        accent: "emerald",
        font_scale: "large",
        density: "compact",
        level_scheme: "spectrum",
        model: "qwen3.5:9b",
        otra_clave: "ignorada",
      }),
    ).toEqual({
      theme: "light",
      accent: "emerald",
      fontScale: "large",
      density: "compact",
      levelScheme: "spectrum",
    });
  });

  it("ignora valores de settings de apariencia no válidos", () => {
    expect(
      appearanceFromSettings({ theme: "nope", accent: "nope" }),
    ).toEqual({});
  });

  it("ignora un esquema de niveles desconocido en vez de inventarlo", () => {
    expect(appearanceFromSettings({ level_scheme: "arcoiris" })).toEqual({});
    expect(parseAppearance(JSON.stringify({ levelScheme: "arcoiris" })).levelScheme)
      .toBe(DEFAULT_APPEARANCE.levelScheme);
  });

  it("expone un conjunto razonable de acentos", () => {
    expect(ACCENTS.length).toBeGreaterThanOrEqual(5);
    expect(new Set(ACCENTS.map((a) => a.id)).size).toBe(ACCENTS.length);
  });

  it("expone los tres esquemas de niveles con sus siete pasos de vista previa", () => {
    expect(LEVEL_SCHEMES.map((s) => s.id)).toEqual([
      "traffic",
      "spectrum",
      "mono",
    ]);
    for (const scheme of LEVEL_SCHEMES) {
      expect(scheme.preview.map((step) => step.key)).toEqual([
        "pre-a1",
        "a1",
        "a2",
        "b1",
        "b2",
        "c1",
        "c2",
      ]);
    }
  });
});
