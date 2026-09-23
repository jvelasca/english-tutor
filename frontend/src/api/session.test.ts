import { afterEach, describe, expect, it, vi } from "vitest";
import {
  changeEmail,
  changePassword,
  closeSession,
  createAccount,
  getSession,
  openSession,
  resendVerification,
  SessionPasswordError,
  unenrollAccount,
  verifyEmail,
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

  it("getSession devuelve la cuenta cuando hay sesión", async () => {
    mockFetch(true, 200, { id: "u1", name: "Ana" });
    await expect(getSession()).resolves.toEqual({ id: "u1", name: "Ana" });
  });

  it("getSession solo trata el 401 como «sin sesión»: un 500 sigue siendo error", async () => {
    // La mordida de `unauthorizedAsNull`: si el backend está roto, la app no debe
    // creer que no hay sesión (pintaría el selector y ocultaría el fallo real).
    mockFetch(false, 500, { detail: "boom" });
    await expect(getSession()).rejects.toThrow();
  });

  it("un 404 (la cuenta de la cookie ya no existe) se lee como «sin sesión»", async () => {
    // V3.80.2. Es el caso real: el webmaster purga una cuenta desde la consola y
    // el navegador se queda con una cookie firmada que apunta a nadie. Antes esto
    // lanzaba, tumbaba el arranque entero y la puerta salía con la lista vacía.
    const fn = mockFetch(false, 404, { detail: "Usuario no encontrado" });
    await expect(getSession()).resolves.toBeNull();
    // Y la cookie muerta se retira en el mismo paso: sin el `DELETE`, el fallo se
    // reproduciría en cada recarga.
    expect(fn.mock.calls.map((call) => [call[0], call[1]?.method])).toEqual([
      ["/api/session", undefined],
      ["/api/session", "DELETE"],
    ]);
  });

  it("un 403 de cuenta fuera de servicio también es «sin sesión», no una avería", async () => {
    // `PROFILE_DISABLED` significa «tu cuenta está desactivada o dada de baja»:
    // la respuesta honesta es la misma que un 401, no un error que pintar.
    mockFetch(false, 403, { detail: "PROFILE_DISABLED" });
    await expect(getSession()).resolves.toBeNull();
  });

  it("si el backend no responde, retirar la cookie no puede tumbar la lectura", async () => {
    // El `DELETE` es best-effort: si también falla, `getSession` sigue diciendo
    // «no hay sesión» en vez de propagar el fallo secundario.
    const fn = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        headers: { get: () => null },
        json: async () => ({ detail: "Usuario no encontrado" }),
      })
      .mockRejectedValueOnce(new Error("sin red"));
    vi.stubGlobal("fetch", fn);
    await expect(getSession()).resolves.toBeNull();
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
 * V3.81 (Fase 3 del P0 de identidad): la cuenta con contraseña.
 *
 * Lo que se fija aquí es que la UI **pueda distinguir** los desenlaces. Todos los
 * 401 se convertían en un `Error` de texto, y con eso la puerta no habría podido
 * saber si tenía que pedir la contraseña o decir «el backend no responde».
 */
describe("session api · cuenta y contraseña (V3.81)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("openSession manda la contraseña solo cuando se le da", async () => {
    const fn = mockFetch(true, 200, { id: "u1", name: "Ana", has_password: true });
    await openSession("u1", "caballo-bateria");
    expect(JSON.parse(fn.mock.calls[0][1].body as string)).toEqual({
      user_id: "u1",
      password: "caballo-bateria",
    });

    // Sin contraseña el cuerpo es el de siempre: una cuenta heredada sin
    // credencial (o el caso de «aún no sé si la tiene») no cambia.
    await openSession("u1");
    expect(JSON.parse(fn.mock.calls[1][1].body as string)).toEqual({
      user_id: "u1",
    });
  });

  it("un 401 PASSWORD_REQUIRED llega como desenlace tipado, no como avería", async () => {
    mockFetch(false, 401, { detail: "PASSWORD_REQUIRED" });
    const err = await openSession("u1").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(SessionPasswordError);
    expect((err as SessionPasswordError).reason).toBe("password-required");
  });

  it("un 401 PASSWORD_INVALID se distingue de «falta la contraseña»", async () => {
    mockFetch(false, 401, { detail: "PASSWORD_INVALID" });
    const err = await openSession("u1", "no-es-esta").catch((e: unknown) => e);
    expect((err as SessionPasswordError).reason).toBe("password-invalid");
  });

  it("el freno llega con su espera para poder contarla", async () => {
    mockFetch(false, 429, { detail: "PASSWORD_THROTTLED" }, { "retry-after": "37" });
    const err = await openSession("u1", "no-es-esta").catch((e: unknown) => e);
    expect((err as SessionPasswordError).reason).toBe("password-throttled");
    expect((err as SessionPasswordError).retryAfterSeconds).toBe(37);
  });

  it("un 401 de sesión (SESSION_REQUIRED) no se confunde con la contraseña", async () => {
    mockFetch(false, 401, { detail: "SESSION_REQUIRED" });
    const err = await openSession("u1").catch((e: unknown) => e);
    expect(err).not.toBeInstanceOf(SessionPasswordError);
  });

  it("createAccount manda nombre, email y contraseña a POST /api/users", async () => {
    const fn = mockFetch(true, 200, { id: "u2", name: "Marta" });
    await createAccount("Marta", " marta@example.com ", "caballo-bateria");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/users");
    expect(init.method).toBe("POST");
    // El email se limpia en el borde de la API: el backend también lo normaliza,
    // pero no se le manda basura que ya se puede quitar aquí.
    expect(JSON.parse(init.body as string)).toEqual({
      name: "Marta",
      email: "marta@example.com",
      password: "caballo-bateria",
    });
  });

  it("changePassword manda la actual y la nueva por PUT", async () => {
    const fn = mockFetch(true, 200, { id: "u1", name: "Ana", has_password: true });
    await expect(changePassword("vieja-clave", "nueva-clave")).resolves.toMatchObject({
      has_password: true,
    });
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/session/password");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({
      current_password: "vieja-clave",
      new_password: "nueva-clave",
    });
  });

  it("changePassword admite no tener contraseña actual (cuenta heredada)", async () => {
    const fn = mockFetch(true, 200, { id: "u1", name: "Ana" });
    await changePassword(null, "nueva-clave");
    expect(JSON.parse(fn.mock.calls[0][1].body as string)).toEqual({
      current_password: null,
      new_password: "nueva-clave",
    });
  });

  it("changeEmail exige la contraseña y manda el email nuevo", async () => {
    const fn = mockFetch(true, 200, { id: "u1", name: "Ana" });
    await changeEmail("mi-clave", " nueva@example.com ");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/session/email");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({
      password: "mi-clave",
      email: "nueva@example.com",
    });
  });

  it("unenrollAccount manda la contraseña y devuelve el desenlace", async () => {
    const fn = mockFetch(true, 200, { unenrolled: true, user: { id: "u1" } });
    await expect(unenrollAccount("mi-clave")).resolves.toMatchObject({
      unenrolled: true,
    });
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/account/unenroll");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ password: "mi-clave" });
  });

  it("resendVerification cuenta que no hay correo en vez de fingir un envío", async () => {
    // El modo híbrido se cuenta en la respuesta: `sent: false` no es un error, es
    // «aquí no hay SMTP y lo confirma el webmaster». Una UI que pintara «enviado»
    // haría esperar un correo que no va a llegar.
    mockFetch(true, 200, { sent: false, reason: "SMTP_NOT_CONFIGURED" });
    await expect(resendVerification()).resolves.toEqual({
      sent: false,
      reason: "SMTP_NOT_CONFIGURED",
    });
  });

  it("verifyEmail va sin sesión: lo que autoriza es el token", async () => {
    const fn = mockFetch(true, 200, { id: "u1", email_verified: true });
    await verifyEmail("token-de-un-solo-uso");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/account/verify");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      token: "token-de-un-solo-uso",
    });
  });
});
