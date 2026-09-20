import { describe, expect, it } from "vitest";
import {
  buildReplayText,
  replayScope,
  suggestAltVoice,
  voiceAccentKey,
  voiceDisplayName,
  voiceLanguage,
  voiceLocale,
  voiceShortLabel,
} from "./voices";

describe("voiceLanguage / voiceLocale / voiceAccentKey", () => {
  it("deriva idioma, locale y acento del id de Piper", () => {
    expect(voiceLanguage("en_GB-alan-medium")).toBe("en");
    expect(voiceLocale("en_GB-alan-medium")).toBe("en_GB");
    expect(voiceAccentKey("en_GB-alan-medium")).toBe("gb");
    expect(voiceAccentKey("en_US-lessac-medium")).toBe("us");
  });

  it("no inventa locale cuando el id no la trae", () => {
    expect(voiceLocale("lessac")).toBe("");
    expect(voiceLocale("en_GB")).toBe("en_GB");
    expect(voiceAccentKey("lessac")).toBe("");
    expect(voiceLanguage("lessac")).toBe("lessac");
  });

  it("no se rompe con valores vacios", () => {
    expect(voiceLanguage("")).toBe("");
    expect(voiceLocale("")).toBe("");
    expect(voiceAccentKey("")).toBe("");
    expect(voiceLocale(undefined as unknown as string)).toBe("");
  });
});

describe("suggestAltVoice", () => {
  it("prefiere OTRA locale de la misma lengua (dos acentos de verdad)", () => {
    expect(
      suggestAltVoice(
        ["en_US-lessac-medium", "en_GB-alan-medium"],
        "en_US-lessac-medium",
      ),
    ).toBe("en_GB-alan-medium");
    expect(
      suggestAltVoice(
        ["en_US-lessac-medium", "en_GB-alan-medium"],
        "en_GB-alan-medium",
      ),
    ).toBe("en_US-lessac-medium");
  });

  it("si no hay otra locale, cae a otra voz de la misma lengua", () => {
    expect(
      suggestAltVoice(["en_US-lessac-medium", "en_US-amy-medium"], "en_US-lessac-medium"),
    ).toBe("en_US-amy-medium");
  });

  it("nunca cruza de idioma", () => {
    expect(
      suggestAltVoice(["en_US-lessac-medium", "es_MX-ald-medium"], "en_US-lessac-medium"),
    ).toBeNull();
  });

  it("devuelve null si no hay segunda voz (la UI mostrara solo A)", () => {
    expect(suggestAltVoice(["en_US-lessac-medium"], "en_US-lessac-medium")).toBeNull();
    expect(suggestAltVoice([], "en_US-lessac-medium")).toBeNull();
    expect(suggestAltVoice(["en_US-lessac-medium"], "")).toBe("en_US-lessac-medium");
  });
});

describe("voiceShortLabel / voiceDisplayName", () => {
  it("recorta la etiqueta larga a su nombre propio", () => {
    expect(voiceShortLabel("British English · Alan")).toBe("Alan");
    expect(voiceShortLabel("American English · Lessac (default)")).toBe("Lessac");
    expect(voiceShortLabel("Alan")).toBe("Alan");
  });

  it("cae al id cuando la etiqueta viene vacia", () => {
    expect(voiceShortLabel("", "en_GB-alan-medium")).toBe("alan");
  });

  it("compone un nombre legible cuando el backend no tiene etiqueta curada", () => {
    expect(
      voiceDisplayName({ id: "en_GB-alan-medium", name: "British English · Alan" }),
    ).toBe("Alan");
    // Etiqueta derivada del id: repite el id, no sirve en un selector estrecho.
    expect(
      voiceDisplayName({ id: "en_GB-northern_english_male-medium", name: "en_GB · northern_english_male (medium)" }),
    ).toBe("Northern English Male");
  });
});

describe("buildReplayText", () => {
  const OPTIONS = ["one", "two", "three"];
  const SCRIPT = "Emma has one brother and two sisters.";
  const PROMPT = "How many sisters does Emma have?";

  it("por defecto lee el texto del item, la pregunta y la respuesta correcta", () => {
    expect(
      buildReplayText(PROMPT, OPTIONS, { correctIndex: 1, script: SCRIPT }),
    ).toBe(
      "Emma has one brother and two sisters. How many sisters does Emma have?. two.",
    );
  });

  it("con `withOptions` anade las opciones con su letra y cierra con la clave", () => {
    expect(
      buildReplayText(PROMPT, OPTIONS, {
        scope: "withOptions",
        correctIndex: 1,
        script: SCRIPT,
      }),
    ).toBe(
      "Emma has one brother and two sisters. How many sisters does Emma have?. " +
        "A: one. B: two. C: three. B: two.",
    );
  });

  it("con `correct` lee solo la pregunta y la respuesta correcta", () => {
    expect(
      buildReplayText(PROMPT, OPTIONS, {
        scope: "correct",
        correctIndex: 1,
        script: SCRIPT,
      }),
    ).toBe("How many sisters does Emma have?. two.");
  });

  it("no repite el texto cuando el script ya es la pregunta", () => {
    // Muy comun en listening A1: lo que suena ES la pregunta.
    expect(
      buildReplayText("Where do you have breakfast?", ["At home"], {
        correctIndex: 0,
        script: "  Where do you   have breakfast?  ",
      }),
    ).toBe("Where do you have breakfast?. At home.");
  });

  it("respeta la letra original si alguna opcion viene vacia", () => {
    expect(
      buildReplayText("Pick one", ["First", "", "Third"], {
        scope: "withOptions",
      }),
    ).toBe("Pick one. A: First. C: Third.");
  });

  it("normaliza espacios y no duplica el punto final", () => {
    expect(
      buildReplayText("  Hello   there.  ", ["Yes  sir."], {
        scope: "withOptions",
      }),
    ).toBe("Hello there. A: Yes sir.");
  });

  it("sin opciones devuelve solo la frase; sin nada, cadena vacia", () => {
    expect(buildReplayText("Just the prompt", [])).toBe("Just the prompt.");
    expect(buildReplayText("coffee", [], { scope: "correct" })).toBe("coffee.");
    expect(buildReplayText("", [])).toBe("");
  });

  it("sin indice valido la respuesta se omite, no se inventa", () => {
    for (const correctIndex of [null, undefined, -1, 9]) {
      expect(
        buildReplayText(PROMPT, OPTIONS, { correctIndex, script: SCRIPT }),
      ).toBe(
        "Emma has one brother and two sisters. How many sisters does Emma have?.",
      );
      expect(
        buildReplayText(PROMPT, OPTIONS, {
          scope: "withOptions",
          correctIndex,
        }),
      ).toBe("How many sisters does Emma have?. A: one. B: two. C: three.");
    }
  });

  it("nunca deja la repeticion muda aunque el alcance elegido no tenga piezas", () => {
    // `correct` en un item cuyo unico contenido es el texto del audio: sin
    // pregunta ni respuesta, la eleccion del perfil no puede dejar sin altavoz.
    expect(
      buildReplayText("", [], { scope: "correct", script: "I'll be there at eight." }),
    ).toBe("I'll be there at eight.");
    expect(
      buildReplayText("", ["At home", "At work"], { scope: "correct" }),
    ).toBe("A: At home. B: At work.");
  });
});

describe("replayScope · normalizacion de la preferencia (V3.75.6)", () => {
  it("acepta los tres valores vigentes", () => {
    expect(replayScope("item")).toBe("item");
    expect(replayScope("withOptions")).toBe("withOptions");
    expect(replayScope("correct")).toBe("correct");
  });

  it("conserva el valor historico `all` como «item + opciones»", () => {
    // Un perfil que ya habia elegido la lectura larga no la pierde al cambiar el
    // juego de valores.
    expect(replayScope("all")).toBe("withOptions");
  });

  it("cualquier otro valor cae al defecto `item`", () => {
    expect(replayScope("")).toBe("item");
    expect(replayScope(undefined)).toBe("item");
    expect(replayScope(null)).toBe("item");
    expect(replayScope("cualquier-cosa")).toBe("item");
  });
});
