// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import {
  canonicalPath,
  isRememberablePath,
  mergeStudyPlace,
  parseStudyPlace,
  pathToRestore,
  readLastPath,
  readStudyPlace,
  writeLastPath,
} from "./lastPlace";

describe("último sitio", () => {
  beforeEach(() => window.localStorage.clear());

  it("la raíz solo se sustituye por una ruta de estudio", () => {
    expect(pathToRestore("/", "/diccionario")).toBe("/diccionario");
    expect(pathToRestore("/", "/")).toBeNull();
    expect(pathToRestore("/aprender/listening", "/diccionario")).toBeNull();
    expect(pathToRestore("/", "/cuenta/activar")).toBeNull();
  });

  it("no recuerda las rutas de cuenta", () => {
    expect(isRememberablePath("/cuenta/activar")).toBe(false);
    expect(isRememberablePath("/diccionario")).toBe(true);
    expect(canonicalPath("#/traductor?x=1")).toBe("/traductor");
  });

  it("la ruta queda ligada al usuario", () => {
    writeLastPath("u1", "/diccionario");
    writeLastPath("u2", "/chat");
    expect(readLastPath("u1")).toBe("/diccionario");
    expect(readLastPath("u2")).toBe("/chat");
  });

  it("un sitio de estudio inválido no se acepta", () => {
    expect(parseStudyPlace("nope")).toBeNull();
    expect(parseStudyPlace(JSON.stringify({ tab: "mazos" }))).toBeNull();
    const place = parseStudyPlace(
      JSON.stringify({
        tab: "decks",
        scope: "deck",
        pick: "pending",
        level: "B2",
        deckId: 4,
      }),
    );
    expect(place?.tab).toBe("decks");
    expect(place?.deckId).toBe(4);
    expect(place?.level).toBe("B2");
    expect(
      parseStudyPlace(
        JSON.stringify({
          tab: "study",
          scope: "deck",
          pick: "failed",
          level: "A1",
          deckId: 2,
        }),
      )?.pick,
    ).toBe("unlearned");
    expect(
      parseStudyPlace(
        JSON.stringify({
          tab: "study",
          scope: "all",
          pick: "hard",
          level: "A1",
          deckId: null,
        }),
      )?.pick,
    ).toBe("hard");
  });

  it("un cambio se mezcla con lo ya guardado", () => {
    mergeStudyPlace("u1", {
      tab: "study",
      scope: "deck",
      pick: "pending",
      level: "A1",
      deckId: 7,
    });
    mergeStudyPlace("u1", { scope: "level", level: "B1" });
    expect(readStudyPlace("u1")).toMatchObject({
      tab: "study",
      scope: "level",
      level: "B1",
      deckId: 7,
    });
  });
});
