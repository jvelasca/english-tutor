import { describe, expect, it } from "vitest";
import {
  LAYOUT_DEFAULTS,
  clampRight,
  clampSidebar,
  parseLayout,
  serializeLayout,
} from "./layout";

describe("parseLayout", () => {
  it("devuelve los valores por defecto cuando no hay raw", () => {
    expect(parseLayout(null)).toEqual(LAYOUT_DEFAULTS);
    expect(parseLayout(undefined)).toEqual(LAYOUT_DEFAULTS);
    expect(parseLayout("")).toEqual(LAYOUT_DEFAULTS);
  });

  it("devuelve los valores por defecto ante JSON corrupto", () => {
    expect(parseLayout("esto no es json")).toEqual(LAYOUT_DEFAULTS);
  });

  it("parsea un layout válido", () => {
    const layout = parseLayout('{"sidebarWidth": 320, "rightWidth": 420}');
    expect(layout).toEqual({ sidebarWidth: 320, rightWidth: 420 });
  });

  it("recorta valores fuera de rango", () => {
    const layout = parseLayout('{"sidebarWidth": 5, "rightWidth": 99999}');
    expect(layout.sidebarWidth).toBeGreaterThanOrEqual(200);
    expect(layout.rightWidth).toBeLessThanOrEqual(900);
  });
});

describe("clamps", () => {
  it("clampSidebar respeta el mínimo", () => {
    expect(clampSidebar(1)).toBeGreaterThanOrEqual(200);
  });

  it("clampRight respeta el máximo", () => {
    expect(clampRight(100000)).toBeLessThanOrEqual(900);
  });
});

describe("serializeLayout", () => {
  it("serializa y se puede volver a parsear", () => {
    const layout = { sidebarWidth: 300, rightWidth: 400 };
    expect(parseLayout(serializeLayout(layout))).toEqual(layout);
  });
});
