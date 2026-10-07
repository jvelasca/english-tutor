import { describe, expect, it } from "vitest";
import { canGoBack, canGoForward, followTrail, pushTrail, startTrail } from "./historyTrail";

describe("pila de atrás y adelante", () => {
  it("al empezar no hay a dónde volver", () => {
    const trail = startTrail("/");
    expect(canGoBack(trail)).toBe(false);
    expect(canGoForward(trail)).toBe(false);
  });

  it("una visita nueva abre atrás y cierra el adelante", () => {
    let trail = pushTrail(startTrail("/"), "/diccionario");
    trail = pushTrail(trail, "/aprender");
    trail = followTrail(trail, "/diccionario");
    expect(canGoBack(trail)).toBe(true);
    expect(canGoForward(trail)).toBe(true);
    trail = pushTrail(trail, "/traductor");
    expect(trail.entries).toEqual(["/", "/diccionario", "/traductor"]);
    expect(canGoForward(trail)).toBe(false);
  });

  it("el atrás y el adelante del navegador recorren los vecinos", () => {
    let trail = pushTrail(startTrail("/"), "/diccionario");
    trail = followTrail(trail, "/");
    expect(trail.index).toBe(0);
    expect(canGoBack(trail)).toBe(false);
    trail = followTrail(trail, "/diccionario");
    expect(trail.index).toBe(1);
    expect(canGoForward(trail)).toBe(false);
  });
});
