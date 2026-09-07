import { describe, expect, it } from "vitest";
import {
  GRAMMAR_ACTIVITY,
  LEARN_ACTIVITY_IDS,
  LISTENING_ACTIVITY,
  SPEAKING_ACTIVITY,
  VOCABULARY_ACTIVITY,
  isLearnActivity,
  learnActivityFromPath,
  legacySpeakingRedirect,
  speakingModeFromPath,
  speakingModePath,
  type SpeakingMode,
} from "./learnHub";

describe("LEARN_ACTIVITY_IDS", () => {
  it("expone exactamente las 4 actividades del hub (DISENO-SPEAKING-UNICO F1)", () => {
    expect(LEARN_ACTIVITY_IDS).toEqual([
      "listening",
      "speaking",
      "vocabulario",
      "gramatica",
    ]);
  });

  it("mantiene el alias legado de vocabulary con su URL existente", () => {
    expect(VOCABULARY_ACTIVITY).toBe("vocabulario");
  });

  it("las antiguas tarjetas orales ya no son actividades del hub", () => {
    // DISENO-SPEAKING-UNICO F1: pronunciación y conversación son modos
    // internos de Speaking, no sub-rutas propias.
    expect(isLearnActivity("pronunciacion")).toBe(false);
    expect(isLearnActivity("conversar")).toBe(false);
  });
});

describe("isLearnActivity", () => {
  it("reconoce los identificadores canónicos", () => {
    for (const id of LEARN_ACTIVITY_IDS) {
      expect(isLearnActivity(id)).toBe(true);
    }
  });

  it("rechaza lecturas aparcadas y cadenas desconocidas", () => {
    expect(isLearnActivity("reading")).toBe(false);
    expect(isLearnActivity("writing")).toBe(false);
    expect(isLearnActivity("pronunciacion")).toBe(false);
    expect(isLearnActivity("conversar")).toBe(false);
    expect(isLearnActivity("listeningx")).toBe(false);
    expect(isLearnActivity("")).toBe(false);
    expect(isLearnActivity(null)).toBe(false);
    expect(isLearnActivity(undefined)).toBe(false);
  });
});

describe("learnActivityFromPath", () => {
  it("resuelve cada sub-ruta canónica a su actividad", () => {
    expect(learnActivityFromPath("/aprender/listening")).toBe("listening");
    expect(learnActivityFromPath("/aprender/speaking")).toBe("speaking");
    expect(learnActivityFromPath("/aprender/vocabulario")).toBe("vocabulario");
    expect(learnActivityFromPath("/aprender/gramatica")).toBe("gramatica");
  });

  it("resuelve las sub-rutas de modo de Speaking a speaking (F4)", () => {
    expect(learnActivityFromPath("/aprender/speaking/acento")).toBe(
      SPEAKING_ACTIVITY,
    );
    expect(learnActivityFromPath("/aprender/speaking/dialogo")).toBe(
      SPEAKING_ACTIVITY,
    );
    expect(learnActivityFromPath("/aprender/speaking/micro")).toBe(
      SPEAKING_ACTIVITY,
    );
    expect(learnActivityFromPath("/aprender/speaking/accent")).toBe(
      SPEAKING_ACTIVITY,
    );
  });

  it("resuelve las hojas legadas orales a la superficie Speaking (F4)", () => {
    expect(learnActivityFromPath("/aprender/pronunciacion")).toBe(
      SPEAKING_ACTIVITY,
    );
    expect(learnActivityFromPath("/aprender/conversar")).toBe(
      SPEAKING_ACTIVITY,
    );
  });

  it("normaliza trailing slashes y valores con hash", () => {
    expect(learnActivityFromPath("/aprender/listening/")).toBe("listening");
    expect(learnActivityFromPath("#/aprender/gramatica/")).toBe("gramatica");
    expect(learnActivityFromPath("#/aprender/speaking/acento/")).toBe(
      SPEAKING_ACTIVITY,
    );
  });

  it("devuelve null para el hub y para otras raíces", () => {
    expect(learnActivityFromPath("/aprender")).toBe(null);
    expect(learnActivityFromPath("/aprender/")).toBe(null);
    expect(learnActivityFromPath("/")).toBe(null);
    expect(learnActivityFromPath("/formacion/b1")).toBe(null);
  });

  it("degrada a null las sub-rutas desconocidas bajo /aprender", () => {
    expect(learnActivityFromPath("/aprender/otra")).toBe(null);
    expect(learnActivityFromPath("/aprender/leccion")).toBe(null);
    expect(learnActivityFromPath("/aprender/otra/cosa")).toBe(null);
    expect(learnActivityFromPath("/aprender/reading")).toBe(null);
    expect(learnActivityFromPath("/aprender/speaking/desconocido")).toBe(null);
  });

  it("respeta la frontera de segmento", () => {
    expect(learnActivityFromPath("/aprenderx/listening")).toBe(null);
    expect(learnActivityFromPath("/aprender-listening")).toBe(null);
  });
});

describe("speakingModePath", () => {
  it("construye la sub-ruta canónica de cada modo (micro sin hoja)", () => {
    expect(speakingModePath("micro")).toBe("/aprender/speaking");
    expect(speakingModePath("accent")).toBe("/aprender/speaking/acento");
    expect(speakingModePath("dialogue")).toBe("/aprender/speaking/dialogo");
  });
});

describe("speakingModeFromPath", () => {
  it("lee el modo de la página Speaking y sus sub-rutas", () => {
    expect(speakingModeFromPath("/aprender/speaking")).toBe("micro");
    expect(speakingModeFromPath("/aprender/speaking/")).toBe("micro");
    expect(speakingModeFromPath("/aprender/speaking/micro")).toBe("micro");
    expect(speakingModeFromPath("/aprender/speaking/acento")).toBe("accent");
    expect(speakingModeFromPath("/aprender/speaking/dialogo")).toBe(
      "dialogue",
    );
  });

  it("acepta los alias en inglés de los modos", () => {
    expect(speakingModeFromPath("/aprender/speaking/accent")).toBe("accent");
    expect(speakingModeFromPath("/aprender/speaking/dialogue")).toBe(
      "dialogue",
    );
  });

  it("lee el modo de las hojas legadas orales (F4)", () => {
    expect(speakingModeFromPath("/aprender/pronunciacion")).toBe("accent");
    expect(speakingModeFromPath("/aprender/conversar")).toBe("dialogue");
  });

  it("devuelve null para rutas que no abren Speaking", () => {
    expect(speakingModeFromPath("/")).toBe(null);
    expect(speakingModeFromPath("/aprender")).toBe(null);
    expect(speakingModeFromPath("/aprender/listening")).toBe(null);
    expect(speakingModeFromPath("/aprender/vocabulario")).toBe(null);
    expect(speakingModeFromPath("/aprender/speaking/desconocido")).toBe(null);
    expect(speakingModeFromPath("/formacion/b1")).toBe(null);
    expect(speakingModeFromPath("/aprender/speaking/acento/otra")).toBe(null);
  });
});

describe("legacySpeakingRedirect", () => {
  it("canonicaliza las hojas legadas orales a la sub-ruta de modo", () => {
    expect(legacySpeakingRedirect("/aprender/pronunciacion")).toBe(
      "/aprender/speaking/acento",
    );
    expect(legacySpeakingRedirect("/aprender/conversar")).toBe(
      "/aprender/speaking/dialogo",
    );
    expect(legacySpeakingRedirect("#/aprender/pronunciacion/")).toBe(
      "/aprender/speaking/acento",
    );
  });

  it("devuelve null para rutas no legadas", () => {
    expect(legacySpeakingRedirect("/aprender/speaking")).toBe(null);
    expect(legacySpeakingRedirect("/aprender/speaking/acento")).toBe(null);
    expect(legacySpeakingRedirect("/aprender/listening")).toBe(null);
    expect(legacySpeakingRedirect("/")).toBe(null);
    expect(legacySpeakingRedirect("/aprender")).toBe(null);
  });
});

describe("coherencia con routeToPath/pathToRoute del mapa actual", () => {
  it("el chat libre tiene raíz /chat y vocabulario sigue siendo sub-ruta", async () => {
    const { pathToRoute } = await import("./routeMap");
    expect(pathToRoute("/aprender/conversar")).toBe("learn");
    expect(pathToRoute("/aprender/speaking/acento")).toBe("learn");
    expect(pathToRoute("/chat")).toBe("chat");
    expect(pathToRoute("/aprender/vocabulario")).toBe("vocabulary");
    expect(learnActivityFromPath("/aprender/conversar")).toBe(
      SPEAKING_ACTIVITY,
    );
    expect(learnActivityFromPath("/aprender/vocabulario")).toBe(
      VOCABULARY_ACTIVITY,
    );
    expect(LISTENING_ACTIVITY).toBe("listening");
    expect(SPEAKING_ACTIVITY).toBe("speaking");
    expect(GRAMMAR_ACTIVITY).toBe("gramatica");
  });

  it("la ruta canónica de un modo parsea en el modo y la actividad", () => {
    for (const mode of ["micro", "accent", "dialogue"] as SpeakingMode[]) {
      const p = speakingModePath(mode);
      expect(learnActivityFromPath(p)).toBe(SPEAKING_ACTIVITY);
      expect(speakingModeFromPath(p)).toBe(mode);
    }
  });
});
