import { describe, expect, it } from "vitest";
import { AVATAR_COLORS, avatarColor, hashString, initials } from "./avatar";
import type { User } from "../types/api";

const user = (overrides: Partial<User> = {}): User => ({
  id: "u1",
  name: "Ana",
  created_at: "2026-01-01",
  ...overrides,
});

describe("initials", () => {
  it("devuelve las iniciales de un nombre compuesto", () => {
    expect(initials("Ana García")).toBe("AG");
  });

  it("devuelve una sola inicial para un nombre simple", () => {
    expect(initials("Ana")).toBe("A");
  });

  it("devuelve '?' para un nombre vacío", () => {
    expect(initials("")).toBe("?");
    expect(initials("   ")).toBe("?");
  });
});

describe("hashString", () => {
  it("es determinista", () => {
    expect(hashString("abc")).toBe(hashString("abc"));
  });

  it("devuelve un entero no negativo", () => {
    expect(hashString("algo")).toBeGreaterThanOrEqual(0);
  });
});

describe("avatarColor", () => {
  it("usa el color elegido por el usuario", () => {
    expect(avatarColor(user({ avatar_color: "#ff0000" }))).toBe("#ff0000");
  });

  it("cae a un color de la paleta cuando no hay color", () => {
    expect(AVATAR_COLORS).toContain(avatarColor(user()));
  });
});
