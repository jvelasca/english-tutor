// @vitest-environment jsdom
/**
 * Tests de V3.21 (V20-03/V20-04): semántica de la superficie Speaking.
 *
 * La página Speaking unifica tres modos (micro / acento / diálogo guiado) que
 * reutilizan motores distintos. Cada modo debe exponer SU título de superficie
 * (la competencia real que se practica, nunca un "Speaking" genérico) y su
 * etiqueta de competencia para el bloque de stats.
 */
import { describe, expect, it } from "vitest";
import type { SpeakingMode } from "../../router/learnHub";
import { translate, type Lang } from "../../utils/i18n";
import { speakingConfigFor } from "./SpeakingRoutesPractice";

const CASES: {
  mode: SpeakingMode;
  titleKey: string;
  competenceKey: string;
  ns: string;
}[] = [
  {
    mode: "micro",
    titleKey: "speaking.surfaceTitleMicro",
    competenceKey: "speaking.competenceMicro",
    ns: "speaking",
  },
  {
    mode: "accent",
    titleKey: "speaking.surfaceTitleAccent",
    competenceKey: "speaking.competenceAccent",
    ns: "pronRoutes",
  },
  {
    mode: "dialogue",
    titleKey: "speaking.surfaceTitleDialogue",
    competenceKey: "speaking.competenceDialogue",
    ns: "convRoutes",
  },
];

describe("speakingConfigFor (V20-03/04)", () => {
  it("asigna a cada modo un título de superficie y una competencia propios", () => {
    for (const c of CASES) {
      const cfg = speakingConfigFor(c.mode);
      expect(cfg.skillTitleKey, `título de ${c.mode}`).toBe(c.titleKey);
      // El h1 nunca es el "Speaking" genérico.
      expect(cfg.skillTitleKey).not.toBe("skill.speaking");
      expect(cfg.statsCompetenceKey, `competencia de ${c.mode}`).toBe(
        c.competenceKey,
      );
    }
  });

  it("cada modo mantiene el motor y el namespace que le corresponde", () => {
    for (const c of CASES) {
      const cfg = speakingConfigFor(c.mode);
      expect(cfg.ns).toBe(c.ns);
      expect(cfg.api.getStats).toBeTypeOf("function");
      expect(cfg.LevelPanel).toBeTypeOf("function");
    }
  });
});

describe("etiquetas i18n por modo (V20-03/04)", () => {
  const LANGS: Lang[] = ["en", "es"];

  it("existe título y competencia por modo en ambos idiomas", () => {
    for (const lang of LANGS) {
      for (const c of CASES) {
        const title = translate(lang, c.titleKey);
        expect(title.length).toBeGreaterThan(0);
        expect(title).toContain("Speaking");
        expect(translate(lang, c.competenceKey).length).toBeGreaterThan(0);
      }
    }
  });

  it("el título de acento y diálogo nombra su competencia real", () => {
    const esAccent = translate("es", "speaking.surfaceTitleAccent");
    expect(esAccent).toContain("Pronunciación");
    const esDialogue = translate("es", "speaking.surfaceTitleDialogue");
    expect(esDialogue).toContain("Conversación");
    const enMicro = translate("en", "speaking.surfaceTitleMicro");
    expect(enMicro).toContain("Micro");
  });
});
