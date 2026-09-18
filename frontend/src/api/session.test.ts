import { afterEach, describe, expect, it, vi } from "vitest";
import { closeSession, getSession, openSession } from "./session";

function mockFetch(ok: boolean, status: number, data: unknown) {
  const fn = vi.fn().mockResolvedValue({
    ok,
    status,
    json: async () => data,
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("session api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("openSession abre sesión con POST /api/session y { user_id }", async () => {
    const fn = mockFetch(true, 200, { id: "u1", name: "Ana" });
    await openSession("u1");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/session");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ user_id: "u1" });
  });

  it("getSession resuelve null cuando el backend responde 401", async () => {
    const fn = mockFetch(false, 401, { detail: "SESSION_REQUIRED" });
    await expect(getSession()).resolves.toBeNull();
    expect(fn.mock.calls[0][0]).toBe("/api/session");
  });

  it("getSession devuelve el perfil cuando hay sesión", async () => {
    mockFetch(true, 200, { id: "u1", name: "Ana" });
    await expect(getSession()).resolves.toEqual({ id: "u1", name: "Ana" });
  });

  it("getSession solo trata el 401 como «sin sesión»: un 500 sigue siendo error", async () => {
    // La mordida de `unauthorizedAsNull`: si el backend está roto, la app no debe
    // creer que no hay sesión (pintaría el selector y ocultaría el fallo real).
    mockFetch(false, 500, { detail: "boom" });
    await expect(getSession()).rejects.toThrow();
  });

  it("closeSession cierra sesión con DELETE /api/session", async () => {
    const fn = mockFetch(true, 200, { closed: true });
    await expect(closeSession()).resolves.toEqual({ closed: true });
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/session");
    expect(init.method).toBe("DELETE");
  });
});
