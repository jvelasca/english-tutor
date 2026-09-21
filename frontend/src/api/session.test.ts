import { afterEach, describe, expect, it, vi } from "vitest";
import {
  closeSession,
  getSession,
  openSession,
  SessionPinError,
  setSessionPin,
} from "./session";

function mockFetch(
  ok: boolean,
  status: number,
  data: unknown,
  headers: Record<string, string> = {},
) {
  const fn = vi.fn().mockResolvedValue({
    ok,
    status,
    headers: { get: (name: string) => headers[name.toLowerCase()] ?? null },
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

/**
 * V3.76 (Fase 3 del P0 de identidad): el PIN opcional por perfil.
 *
 * Lo que se fija aquí es que la UI **pueda distinguir** los desenlaces. Hasta
 * ahora todos los 401 se convertían en un `Error` de texto y la puerta no habría
 * podido saber si tenía que pedir un PIN o decir «el backend no responde».
 */
describe("session api · PIN opcional (V3.76)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("openSession manda el pin solo cuando se le da", async () => {
    const fn = mockFetch(true, 200, { id: "u1", name: "Ana", has_pin: true });
    await openSession("u1", "4821");
    expect(JSON.parse(fn.mock.calls[0][1].body as string)).toEqual({
      user_id: "u1",
      pin: "4821",
    });

    // Sin pin, el cuerpo es el de siempre: un perfil sin PIN no cambia.
    await openSession("u1");
    expect(JSON.parse(fn.mock.calls[1][1].body as string)).toEqual({
      user_id: "u1",
    });
  });

  it("un 401 PIN_REQUIRED llega como desenlace tipado, no como avería", async () => {
    mockFetch(false, 401, { detail: "PIN_REQUIRED" });
    const err = await openSession("u1").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(SessionPinError);
    expect((err as SessionPinError).reason).toBe("pin-required");
  });

  it("un 401 PIN_INVALID se distingue de «falta el PIN»", async () => {
    mockFetch(false, 401, { detail: "PIN_INVALID" });
    const err = await openSession("u1", "0000").catch((e: unknown) => e);
    expect((err as SessionPinError).reason).toBe("pin-invalid");
  });

  it("el freno llega con su espera para poder contarla", async () => {
    mockFetch(false, 429, { detail: "PIN_THROTTLED" }, { "retry-after": "37" });
    const err = await openSession("u1", "0000").catch((e: unknown) => e);
    expect((err as SessionPinError).reason).toBe("pin-throttled");
    expect((err as SessionPinError).retryAfterSeconds).toBe(37);
  });

  it("un 401 de sesión (SESSION_REQUIRED) no se confunde con el PIN", async () => {
    mockFetch(false, 401, { detail: "SESSION_REQUIRED" });
    const err = await openSession("u1").catch((e: unknown) => e);
    expect(err).not.toBeInstanceOf(SessionPinError);
  });

  it("setSessionPin manda el actual y el nuevo por PUT", async () => {
    const fn = mockFetch(true, 200, { id: "u1", name: "Ana", has_pin: true });
    await expect(setSessionPin("1234", "5678")).resolves.toMatchObject({
      has_pin: true,
    });
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/session/pin");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({
      current_pin: "1234",
      new_pin: "5678",
    });
  });
});
