import { describe, expect, it } from "vitest";
import { nextDefaultUserName, resolveInitialUserId } from "./users";
import type { User } from "../types/api";

const user = (id: string): User => ({ id, name: id, created_at: "2026-01-01" });

describe("nextDefaultUserName", () => {
  it("returns the base name when there are no users", () => {
    expect(nextDefaultUserName([])).toBe("Usuario");
  });

  it("returns the base name when it is not taken", () => {
    expect(nextDefaultUserName(["Ana", "Luis"])).toBe("Usuario");
  });

  it("appends a numeric suffix when the base name is taken", () => {
    expect(nextDefaultUserName(["Usuario"])).toBe("Usuario 2");
  });

  it("skips suffixes already in use", () => {
    expect(nextDefaultUserName(["Usuario", "Usuario 2"])).toBe("Usuario 3");
  });
});

describe("resolveInitialUserId", () => {
  it("auto-selecciona el único usuario", () => {
    expect(resolveInitialUserId([user("a")])).toBe("a");
  });

  it("no auto-selecciona cuando hay varios usuarios", () => {
    expect(resolveInitialUserId([user("a"), user("b")])).toBeNull();
  });

  it("devuelve null cuando no hay usuarios", () => {
    expect(resolveInitialUserId([])).toBeNull();
  });

  it("prefiere el perfil recordado cuando existe", () => {
    expect(resolveInitialUserId([user("a"), user("b")], "b")).toBe("b");
  });

  it("ignora el perfil recordado si ya no existe", () => {
    expect(resolveInitialUserId([user("a"), user("b")], "desaparecido")).toBeNull();
  });
});
