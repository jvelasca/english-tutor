/**
 * Vitest de `utils/dictionaryView` (V3.78.0).
 *
 * Fija las dos decisiones que hacen que el diccionario tenga TRES modos sin que
 * el panel incrustado se rompa:
 *
 * 1. El espacio de valores es de tres y el defecto es `lookup` (el modo que
 *    responde a «¿qué significa esta palabra?», que es con lo que se entra a un
 *    diccionario).
 * 2. Existe una frontera explícita hacia el panel incrustado (dos modos), para
 *    que el panel no pueda dejar persistido un modo que no sabe mostrar.
 */
import { describe, expect, it } from "vitest";
import {
  DEFAULT_DICTIONARY_VIEW,
  dictionaryViewFromSettings,
  dictionaryViewToSettings,
  isDictionaryView,
  PANEL_DICTIONARY_VIEWS,
  parseDictionaryView,
  toPanelView,
  type DictionaryView,
} from "./dictionaryView";

const ALL_VIEWS: DictionaryView[] = ["lookup", "personal", "flashcards"];

describe("dictionaryView · los tres modos", () => {
  it("el defecto es Consultar", () => {
    expect(DEFAULT_DICTIONARY_VIEW).toBe("lookup");
    expect(parseDictionaryView(null)).toBe("lookup");
    expect(parseDictionaryView("")).toBe("lookup");
    expect(parseDictionaryView(undefined)).toBe("lookup");
  });

  it("acepta los tres modos, incluido flashcards", () => {
    for (const view of ALL_VIEWS) {
      expect(isDictionaryView(view)).toBe(true);
      expect(parseDictionaryView(view)).toBe(view);
      // El JSON entrecomillado también se acepta (la clave la escriben dos
      // capas distintas y una pudo serializar).
      expect(parseDictionaryView(JSON.stringify(view))).toBe(view);
    }
  });

  it("un valor inválido cae al defecto y no se cuela", () => {
    for (const raw of ["nope", "{}", "[1]", "Personal", "  "]) {
      expect(parseDictionaryView(raw)).toBe("lookup");
      expect(isDictionaryView(raw)).toBe(false);
    }
    expect(dictionaryViewFromSettings({ dictionary_view: "nope" })).toBeNull();
  });

  it("un valor de una versión anterior sigue siendo válido", () => {
    // V3.39 persistió "personal"/"lookup" durante muchas versiones: se sigue
    // respetando, así que nadie pierde su pestaña al actualizar.
    expect(parseDictionaryView("personal")).toBe("personal");
    expect(parseDictionaryView("lookup")).toBe("lookup");
  });

  it("settings solo reconoce un modo válido y lo escribe redondo", () => {
    expect(dictionaryViewFromSettings({ dictionary_view: "flashcards" })).toBe(
      "flashcards",
    );
    expect(dictionaryViewFromSettings({})).toBeNull();
    expect(dictionaryViewFromSettings(undefined)).toBeNull();
    expect(dictionaryViewToSettings("flashcards")).toEqual({
      dictionary_view: "flashcards",
    });
  });
});

describe("dictionaryView · frontera del panel incrustado", () => {
  it("flashcards se proyecta a personal (el panel no sabe estudiar)", () => {
    expect(toPanelView("flashcards")).toBe("personal");
  });

  it("los otros dos modos pasan tal cual", () => {
    expect(toPanelView("personal")).toBe("personal");
    expect(toPanelView("lookup")).toBe("lookup");
  });

  it("el panel declara sus dos modos y ninguno es flashcards", () => {
    expect([...PANEL_DICTIONARY_VIEWS]).toEqual(["personal", "lookup"]);
    expect(PANEL_DICTIONARY_VIEWS).not.toContain("flashcards");
  });
});
