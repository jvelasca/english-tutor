/**
 * Vitest de la ruta CEFR seleccionada (V3.48.1): validación/parseo tolerante,
 * persistencia en settings y prioridad de nivel para servir preguntas.
 */
import { describe, expect, it } from "vitest";
import {
  isSelectedRouteLevel,
  parseSelectedRouteLevel,
  resolveRouteLevel,
  selectedRouteFromSettings,
  selectedRouteToSettings,
  SELECTED_ROUTE_SETTING_KEY,
} from "./selectedRoute";

describe("selectedRoute: validación", () => {
  it("acepta solo los seis niveles CEFR de ruta", () => {
    for (const level of ["A1", "A2", "B1", "B2", "C1", "C2"]) {
      expect(isSelectedRouteLevel(level)).toBe(true);
    }
    for (const bad of ["A0", "C3", "a1", "", null, undefined, 3, {}]) {
      expect(isSelectedRouteLevel(bad)).toBe(false);
    }
  });
});

describe("selectedRoute: parseo tolerante de localStorage", () => {
  it("acepta el valor plano y su JSON", () => {
    expect(parseSelectedRouteLevel("B1")).toBe("B1");
    expect(parseSelectedRouteLevel('"C2"')).toBe("C2");
  });

  it("cae a Auto (null) ante ausencia o valor inválido", () => {
    expect(parseSelectedRouteLevel(null)).toBeNull();
    expect(parseSelectedRouteLevel(undefined)).toBeNull();
    expect(parseSelectedRouteLevel("")).toBeNull();
    expect(parseSelectedRouteLevel("Z9")).toBeNull();
    expect(parseSelectedRouteLevel("{")).toBeNull();
  });
});

describe("selectedRoute: settings del backend", () => {
  it("lee la clave persistida y valida el valor", () => {
    expect(
      selectedRouteFromSettings({ [SELECTED_ROUTE_SETTING_KEY]: "B2" }),
    ).toBe("B2");
    expect(selectedRouteFromSettings({ other: "B1" })).toBeNull();
    expect(
      selectedRouteFromSettings({ [SELECTED_ROUTE_SETTING_KEY]: "" }),
    ).toBeNull();
    expect(selectedRouteFromSettings(undefined)).toBeNull();
  });

  it("persiste Auto como cadena vacía", () => {
    expect(selectedRouteToSettings("C1")).toEqual({
      [SELECTED_ROUTE_SETTING_KEY]: "C1",
    });
    expect(selectedRouteToSettings(null)).toEqual({
      [SELECTED_ROUTE_SETTING_KEY]: "",
    });
  });
});

describe("selectedRoute: prioridad session > ruta seleccionada > recomendada", () => {
  it("la sesión activa manda sobre todo", () => {
    expect(resolveRouteLevel("A2", "B1", "C1")).toBe("A2");
  });

  it("sin sesión manda la ruta seleccionada", () => {
    expect(resolveRouteLevel(null, "B1", "C1")).toBe("B1");
    expect(resolveRouteLevel(undefined, "B1", "C1")).toBe("B1");
  });

  it("sin sesión ni selección cae al nivel recomendado o a Auto (null)", () => {
    expect(resolveRouteLevel(null, null, "C1")).toBe("C1");
    expect(resolveRouteLevel(null, null, null)).toBeNull();
    expect(resolveRouteLevel(undefined, null, undefined)).toBeNull();
  });
});
