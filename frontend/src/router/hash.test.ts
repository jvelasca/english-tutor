import { describe, expect, it } from "vitest";
import {
  formatPath,
  isActive,
  joinPath,
  normalizeHash,
  parseSegments,
  pathToHash,
} from "./hash";
import {
  FORMATION_PATH,
  HELP_PATH,
  HOME_PATH,
  LEARN_PATH,
  LEGACY_CHAT_ACTIVITY,
  LEGACY_LEARN_ALIAS,
  LEGACY_VOCABULARY_ACTIVITY,
  PROGRESS_PATH,
  formationLevelPath,
  learnActivityPath,
} from "./paths";

describe("normalizeHash", () => {
  it("convierte '#/inicio' en '/inicio'", () => {
    expect(normalizeHash("#/inicio")).toBe("/inicio");
  });

  it("convierte cadena vacía en la raíz", () => {
    expect(normalizeHash("")).toBe("/");
  });

  it("convierte '#/' en la raíz", () => {
    expect(normalizeHash("#/")).toBe("/");
  });

  it("deja la raíz '/' como está", () => {
    expect(normalizeHash("/")).toBe("/");
  });

  it("acepta una ruta sin '#'", () => {
    expect(normalizeHash("/aprender/listening")).toBe("/aprender/listening");
  });

  it("colapsa barras duplicadas", () => {
    expect(normalizeHash("/a//b")).toBe("/a/b");
    expect(normalizeHash("#/a///b/")).toBe("/a/b");
  });

  it("recorta la barra final salvo en la raíz", () => {
    expect(normalizeHash("/inicio/")).toBe("/inicio");
    expect(normalizeHash("#/formacion/")).toBe("/formacion");
  });

  it("antepone la barra inicial cuando falta", () => {
    expect(normalizeHash("inicio")).toBe("/inicio");
  });

  it("conserva los segmentos percent-encoded sin decodificarlos", () => {
    expect(normalizeHash("#/formacion/B1%20Test")).toBe(
      "/formacion/B1%20Test",
    );
    expect(normalizeHash("#/formacion/b%C3%A1sico")).toBe(
      "/formacion/b%C3%A1sico",
    );
  });
});

describe("pathToHash", () => {
  it("convierte '/inicio' en '#/inicio'", () => {
    expect(pathToHash("/inicio")).toBe("#/inicio");
  });

  it("convierte la raíz en '#/'", () => {
    expect(pathToHash("/")).toBe("#/");
  });

  it("es simétrica con normalizeHash", () => {
    const raws = [
      "#/inicio",
      "",
      "#/",
      "/",
      "/aprender/listening",
      "#/formacion/b1%20intermediate",
      "#/formacion/",
      "/inicio/",
      "/a//b",
    ];
    for (const raw of raws) {
      const normalized = normalizeHash(raw);
      expect(normalizeHash(pathToHash(normalized))).toBe(normalized);
    }
  });
});

describe("parseSegments", () => {
  it("devuelve [] para la raíz", () => {
    expect(parseSegments("/")).toEqual([]);
  });

  it("divide una ruta en sus segmentos", () => {
    expect(parseSegments("/formacion/b1")).toEqual(["formacion", "b1"]);
  });

  it("normaliza la entrada antes de dividir", () => {
    expect(parseSegments("#/aprender/listening/")).toEqual([
      "aprender",
      "listening",
    ]);
  });

  it("decodifica segmentos percent-encoded", () => {
    expect(parseSegments("/formacion/b1%20intermediate")).toEqual([
      "formacion",
      "b1 intermediate",
    ]);
    expect(parseSegments("/formacion/b%C3%A1sico")).toEqual([
      "formacion",
      "básico",
    ]);
  });

  it("conserva el segmento literal si la codificación es inválida", () => {
    expect(parseSegments("/formacion/%E0%A4%A")).toEqual([
      "formacion",
      "%E0%A4%A",
    ]);
  });
});

describe("formatPath", () => {
  it("une segmentos con barra inicial", () => {
    expect(formatPath(["formacion", "b1"])).toBe("/formacion/b1");
  });

  it("devuelve la raíz para un array vacío", () => {
    expect(formatPath([])).toBe("/");
  });

  it("percent-codifica los segmentos", () => {
    expect(formatPath(["formacion", "b1 intermediate"])).toBe(
      "/formacion/b1%20intermediate",
    );
    expect(formatPath(["formacion", "básico"])).toBe("/formacion/b%C3%A1sico");
    expect(formatPath(["formacion", "b1", "x/y"])).toBe(
      "/formacion/b1/x%2Fy",
    );
  });

  it("ignora segmentos vacíos", () => {
    expect(formatPath(["formacion", "", "b1"])).toBe("/formacion/b1");
    expect(formatPath(["", ""])).toBe("/");
  });

  it("hace round-trip con parseSegments para segmentos que requieren encode", () => {
    const segments = ["formacion", "b1 intermediate", "nivel básico", "x/y"];
    expect(parseSegments(formatPath(segments))).toEqual(segments);
  });
});

describe("isActive", () => {
  it("la raíz como destino solo está activa en la raíz", () => {
    expect(isActive("/formacion", "/")).toBe(false);
    expect(isActive("/", "/")).toBe(true);
  });

  it("devuelve true con igualdad exacta", () => {
    expect(isActive("/formacion", "/formacion")).toBe(true);
    expect(isActive("/formacion/b1", "/formacion/b1")).toBe(true);
  });

  it("considera activo un destino ancestro de la ruta actual", () => {
    expect(isActive("/formacion/b1", "/formacion", { exact: false })).toBe(
      true,
    );
    expect(isActive("/formacion/b1", "/formacion")).toBe(true);
  });

  it("respeta la frontera de segmento", () => {
    expect(isActive("/formacion-b1", "/formacion", { exact: false })).toBe(
      false,
    );
  });

  it("no activa destinos en otra rama", () => {
    expect(isActive("/aprender/listening", "/formacion")).toBe(false);
  });

  it("con exact: true exige igualdad exacta", () => {
    expect(isActive("/formacion/b1", "/formacion", { exact: true })).toBe(
      false,
    );
    expect(isActive("/formacion", "/formacion", { exact: true })).toBe(true);
    expect(isActive("/formacion/b1", "/", { exact: true })).toBe(false);
  });

  it("normaliza la entrada antes de comparar", () => {
    expect(isActive("/formacion/", "/formacion")).toBe(true);
    expect(isActive("#/formacion/b1", "/formacion")).toBe(true);
  });
});

describe("joinPath", () => {
  it("une sobre la raíz", () => {
    expect(joinPath("/", "inicio")).toBe("/inicio");
  });

  it("une segmentos a una ruta base", () => {
    expect(joinPath("/formacion", "b1")).toBe("/formacion/b1");
    expect(joinPath("/formacion", "b1", "unidad-4")).toBe(
      "/formacion/b1/unidad-4",
    );
  });

  it("normaliza la barra final de la base", () => {
    expect(joinPath("/aprender/", "listening")).toBe("/aprender/listening");
  });

  it("devuelve la base normalizada si no hay segmentos", () => {
    expect(joinPath("/formacion/")).toBe("/formacion");
  });

  it("percent-codifica los segmentos añadidos", () => {
    expect(joinPath("/formacion", "b1 intermediate")).toBe(
      "/formacion/b1%20intermediate",
    );
  });
});

describe("paths (constantes y builders)", () => {
  it("define las rutas raíz de los mundos", () => {
    expect(HOME_PATH).toBe("/");
    expect(FORMATION_PATH).toBe("/formacion");
    expect(LEARN_PATH).toBe("/aprender");
    expect(PROGRESS_PATH).toBe("/progreso");
    expect(HELP_PATH).toBe("/ayuda");
  });

  it("formationLevelPath construye el deep link de nivel", () => {
    expect(formationLevelPath("b1")).toBe("/formacion/b1");
    expect(formationLevelPath("b1 intermediate")).toBe(
      "/formacion/b1%20intermediate",
    );
  });

  it("learnActivityPath construye el deep link de actividad", () => {
    expect(learnActivityPath("listening")).toBe("/aprender/listening");
    expect(learnActivityPath("conversar")).toBe("/aprender/conversar");
  });

  it("los builders generan rutas que parsean en sus segmentos", () => {
    expect(parseSegments(formationLevelPath("b1 intermediate"))).toEqual([
      "formacion",
      "b1 intermediate",
    ]);
    expect(parseSegments(learnActivityPath("vocabulario"))).toEqual([
      "aprender",
      "vocabulario",
    ]);
  });

  it("define los alias de las actividades legadas", () => {
    expect(LEGACY_LEARN_ALIAS).toBe(LEARN_PATH);
    expect(LEGACY_LEARN_ALIAS).toBe("/aprender");
    expect(LEGACY_CHAT_ACTIVITY).toBe("conversar");
    expect(LEGACY_VOCABULARY_ACTIVITY).toBe("vocabulario");
  });
});
