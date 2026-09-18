import { afterEach, describe, expect, it, vi } from "vitest";
import {
  deleteCookie,
  readCookie,
  readUserIdCookie,
  writeCookie,
  writeUserIdCookie,
} from "./cookie";

describe("cookie", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("readCookie returns null when document is unavailable", () => {
    vi.unstubAllGlobals();
    expect(readCookie("x")).toBeNull();
  });

  it("writeCookie and readCookie round-trip a value", () => {
    vi.stubGlobal("document", { cookie: "" });
    writeCookie("k", "v");
    expect(readCookie("k")).toBe("v");
  });

  it("readCookie returns null for a missing key", () => {
    vi.stubGlobal("document", { cookie: "a=1; b=2" });
    expect(readCookie("c")).toBeNull();
    expect(readCookie("a")).toBe("1");
  });

  it("readCookie decodes URI-encoded values", () => {
    vi.stubGlobal("document", { cookie: "name=Ana%20L%C3%B3pez" });
    expect(readCookie("name")).toBe("Ana López");
  });

  it("deleteCookie clears the cookie", () => {
    vi.stubGlobal("document", { cookie: "" });
    deleteCookie("k");
    expect(document.cookie).toContain("k=;");
  });

  it("read/write the remembered user id", () => {
    vi.stubGlobal("document", { cookie: "" });
    expect(readUserIdCookie()).toBeNull();
    writeUserIdCookie("u1");
    expect(readUserIdCookie()).toBe("u1");
  });

  // V3.73.x: la cookie de perfil viaja por HTTPS en el runtime de producto y no
  // debe poder salir en claro. En el modo de desarrollo por HTTP no se marca,
  // porque el navegador la descartaría.
  it("writeCookie añade Secure cuando la página va por HTTPS", () => {
    vi.stubGlobal("document", { cookie: "" });
    vi.stubGlobal("location", { protocol: "https:" });
    writeCookie("k", "v");
    expect(document.cookie).toContain("; Secure");
  });

  it("writeCookie no añade Secure en HTTP (modo desarrollo)", () => {
    vi.stubGlobal("document", { cookie: "" });
    vi.stubGlobal("location", { protocol: "http:" });
    writeCookie("k", "v");
    expect(document.cookie).not.toContain("Secure");
  });

  it("deleteCookie marca Secure en HTTPS para poder borrar la cookie", () => {
    vi.stubGlobal("document", { cookie: "" });
    vi.stubGlobal("location", { protocol: "https:" });
    deleteCookie("k");
    expect(document.cookie).toContain("k=;");
    expect(document.cookie).toContain("; Secure");
  });
});
