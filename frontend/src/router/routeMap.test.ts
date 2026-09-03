import { describe, expect, it } from "vitest";
import type { Route } from "../app/routes";
import { pathToRoute, routeToPath } from "./routeMap";

const ALL_ROUTES: Route[] = [
  "home",
  "learn",
  "course",
  "progress",
  "journey",
  "vocabulary",
  "chat",
  "help",
];

describe("routeToPath", () => {
  it("mapea cada pantalla a su ruta canónica", () => {
    expect(routeToPath("home")).toBe("/");
    expect(routeToPath("course")).toBe("/formacion");
    expect(routeToPath("learn")).toBe("/aprender");
    expect(routeToPath("progress")).toBe("/progreso");
    expect(routeToPath("journey")).toBe("/progreso/trayectoria");
    expect(routeToPath("vocabulary")).toBe("/aprender/vocabulario");
    expect(routeToPath("chat")).toBe("/aprender/conversar");
    expect(routeToPath("help")).toBe("/ayuda");
  });
});

describe("round-trip routeToPath + pathToRoute", () => {
  it("devuelve la misma pantalla para los 8 valores de Route", () => {
    for (const route of ALL_ROUTES) {
      expect(pathToRoute(routeToPath(route))).toBe(route);
    }
  });
});

describe("pathToRoute: hoja antes que prefijo", () => {
  it("distingue la hoja trayectoria de la raíz de progreso", () => {
    expect(pathToRoute("/progreso/trayectoria")).toBe("journey");
    expect(pathToRoute("/progreso")).toBe("progress");
    expect(pathToRoute("/progreso/resumen")).toBe("progress");
    expect(pathToRoute("/progreso/trayectoria/detalle")).toBe("progress");
  });

  it("resuelve las hojas de conversar y vocabulario antes que aprender", () => {
    expect(pathToRoute("/aprender/conversar")).toBe("chat");
    expect(pathToRoute("/aprender/vocabulario")).toBe("vocabulary");
    expect(pathToRoute("/aprender")).toBe("learn");
    expect(pathToRoute("/aprender/otra")).toBe("learn");
    expect(pathToRoute("/aprender/otra/cosa")).toBe("learn");
  });

  it("considera todo /formacion como course (cualquier sub-nivel)", () => {
    expect(pathToRoute("/formacion")).toBe("course");
    expect(pathToRoute("/formacion/b1")).toBe("course");
    expect(pathToRoute("/formacion/b1/unidad-4")).toBe("course");
  });

  it("respeta la frontera de segmento (no confunde prefijos parciales)", () => {
    expect(pathToRoute("/formacionx")).toBe("home");
    expect(pathToRoute("/aprender-conversar")).toBe("home");
  });
});

describe("pathToRoute: rutas malformadas o desconocidas", () => {
  it("devuelve home para la raíz", () => {
    expect(pathToRoute("/")).toBe("home");
  });

  it("devuelve home para cadenas vacías o sin hash", () => {
    expect(pathToRoute("")).toBe("home");
    expect(pathToRoute("#")).toBe("home");
  });

  it("devuelve home para rutas desconocidas", () => {
    expect(pathToRoute("/desconocida")).toBe("home");
    expect(pathToRoute("/otro/nivel")).toBe("home");
  });

  it("devuelve home para sub-rutas de ayuda que no son la página de ayuda", () => {
    expect(pathToRoute("/ayuda")).toBe("help");
    expect(pathToRoute("/ayuda/contacto")).toBe("home");
  });
});

describe("pathToRoute: normalización de la entrada", () => {
  it("tolera trailing slash", () => {
    expect(pathToRoute("/formacion/")).toBe("course");
    expect(pathToRoute("/progreso/trayectoria/")).toBe("journey");
    expect(pathToRoute("/aprender/vocabulario/")).toBe("vocabulary");
    expect(pathToRoute("/ayuda/")).toBe("help");
  });

  it("tolera valores con '#' del hash de la URL", () => {
    expect(pathToRoute("#/progreso")).toBe("progress");
    expect(pathToRoute("#/aprender/conversar/")).toBe("chat");
    expect(pathToRoute("#/")).toBe("home");
  });
});
