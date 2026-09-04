import { describe, expect, it } from "vitest";
import {
  CONVERSATION_ACTIVITY,
  GRAMMAR_ACTIVITY,
  LEARN_ACTIVITY_IDS,
  LISTENING_ACTIVITY,
  PRONUNCIATION_ACTIVITY,
  SPEAKING_ACTIVITY,
  VOCABULARY_ACTIVITY,
  isLearnActivity,
  learnActivityFromPath,
} from "./learnHub";

describe("LEARN_ACTIVITY_IDS", () => {
  it("expone exactamente las 6 actividades del hub (decisión D3)", () => {
    expect(LEARN_ACTIVITY_IDS).toEqual([
      "listening",
      "speaking",
      "pronunciacion",
      "conversar",
      "vocabulario",
      "gramatica",
    ]);
  });

  it("mantiene los aliados legados de chat y vocabulary con su URL existente", () => {
    expect(CONVERSATION_ACTIVITY).toBe("conversar");
    expect(VOCABULARY_ACTIVITY).toBe("vocabulario");
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
    expect(learnActivityFromPath("/aprender/pronunciacion")).toBe(
      "pronunciacion",
    );
    expect(learnActivityFromPath("/aprender/conversar")).toBe("conversar");
    expect(learnActivityFromPath("/aprender/vocabulario")).toBe("vocabulario");
    expect(learnActivityFromPath("/aprender/gramatica")).toBe("gramatica");
  });

  it("normaliza trailing slashes y valores con hash", () => {
    expect(learnActivityFromPath("/aprender/listening/")).toBe("listening");
    expect(learnActivityFromPath("#/aprender/gramatica/")).toBe("gramatica");
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
  });

  it("respeta la frontera de segmento", () => {
    expect(learnActivityFromPath("/aprenderx/listening")).toBe(null);
    expect(learnActivityFromPath("/aprender-listening")).toBe(null);
  });
});

describe("coherencia con routeToPath/pathToRoute del mapa actual", () => {
  it("conversar es una sub-ruta de aprender y el chat libre tiene raíz /chat", async () => {
    // V3.10: /aprender/conversar son rutas guiadas (sub-ruta "learn"); el chat
    // libre con el tutor es la Route "chat" con raíz propia /chat.
    const { pathToRoute } = await import("./routeMap");
    expect(pathToRoute("/aprender/conversar")).toBe("learn");
    expect(pathToRoute("/chat")).toBe("chat");
    expect(pathToRoute("/aprender/vocabulario")).toBe("vocabulary");
    expect(
      learnActivityFromPath("/aprender/conversar"),
    ).toBe(CONVERSATION_ACTIVITY);
    expect(
      learnActivityFromPath("/aprender/vocabulario"),
    ).toBe(VOCABULARY_ACTIVITY);
    expect(LISTENING_ACTIVITY).toBe("listening");
    expect(SPEAKING_ACTIVITY).toBe("speaking");
    expect(PRONUNCIATION_ACTIVITY).toBe("pronunciacion");
    expect(GRAMMAR_ACTIVITY).toBe("gramatica");
  });
});
