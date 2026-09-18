import { describe, expect, it } from "vitest";
import { planSession } from "./session";
import type { User } from "../types/api";

function user(id: string): User {
  return {
    id,
    name: id,
    avatar_color: "",
    avatar_emoji: "",
    avatar_image: "",
    created_at: "2026-01-01T00:00:00Z",
  };
}

describe("planSession", () => {
  it("adopta el perfil de la sesión sin volver a abrirla", () => {
    expect(planSession([user("a"), user("b")], "b")).toEqual({
      action: "adopt",
      userId: "b",
    });
  });

  it("abre sesión cuando hay un único perfil y ninguna sesión", () => {
    // El caso del equipo recién instalado: sin este `open`, la app pintaría el
    // perfil como activo y todas las peticiones darían 401 (V3.75).
    expect(planSession([user("a")], null)).toEqual({
      action: "open",
      userId: "a",
    });
  });

  it("no hace nada con varios perfiles y ninguna sesión", () => {
    // El alumno elige: el selector abre la sesión (`selectUser`), no el arranque.
    expect(planSession([user("a"), user("b")], null)).toEqual({ action: "none" });
  });

  it("no hace nada sin perfiles", () => {
    expect(planSession([], null)).toEqual({ action: "none" });
  });

  it("no arrastra una sesión de un perfil que ya no existe", () => {
    // Sesión huérfana + varios perfiles: `none`. Abrir sesión para un id fantasma
    // fallaría (404) y dejaría la app sin perfil activo pero sin selector.
    expect(planSession([user("a"), user("b")], "fantasma")).toEqual({
      action: "none",
    });
  });

  it("cae al perfil único si la sesión apuntaba a un perfil borrado", () => {
    expect(planSession([user("a")], "fantasma")).toEqual({
      action: "open",
      userId: "a",
    });
  });
});
