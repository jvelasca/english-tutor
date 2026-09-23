import { describe, expect, it } from "vitest";
import { planSession } from "./session";
import type { User } from "../types/api";

function user(id: string, hasPassword = false): User {
  return {
    id,
    name: id,
    avatar_color: "",
    avatar_emoji: "",
    avatar_image: "",
    has_password: hasPassword,
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

/**
 * V3.81 (Fase 3 del P0): la contraseña entra en la decisión de arranque.
 *
 * Es la razón de que `planSession` sea una función pura: el caso «cuenta con
 * contraseña» es justo el que se rompería en silencio —un `POST` condenado a 401
 * cuyo error se traga el arranque— y aquí se comprueba sin navegador ni servidor.
 */
describe("planSession · contraseña por cuenta (V3.81)", () => {
  it("pide la contraseña en vez de abrir a ciegas cuando la cuenta la tiene", () => {
    expect(planSession([user("a", true)], null)).toEqual({
      action: "password",
      userId: "a",
    });
  });

  it("no pide contraseña si la cuenta no la tiene", () => {
    expect(planSession([user("a", false)], null)).toEqual({
      action: "open",
      userId: "a",
    });
  });

  it("una sesión ya abierta se adopta aunque la cuenta tenga contraseña", () => {
    // La contraseña se tecleó al abrir esa sesión: volver a pedirla en cada
    // arranque del mismo navegador sería pedirla dos veces por lo mismo.
    expect(planSession([user("a", true)], "a")).toEqual({
      action: "adopt",
      userId: "a",
    });
  });

  it("con varias cuentas y ninguna elegida no pide nada todavía", () => {
    expect(planSession([user("a", true), user("b")], null)).toEqual({
      action: "none",
    });
  });

  it("si la cuenta con contraseña es la única y la sesión era huérfana, la pide", () => {
    expect(planSession([user("a", true)], "fantasma")).toEqual({
      action: "password",
      userId: "a",
    });
  });
});
