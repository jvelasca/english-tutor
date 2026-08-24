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
});
