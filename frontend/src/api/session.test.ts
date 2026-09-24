import { afterEach, describe, expect, it, vi } from "vitest";
import {
  activateAccount,
  ActivationError,
  changeEmail,
  changePassword,
  closeSession,
  forgotPassword,
  getSession,
  openSession,
  resendVerification,
  resetPassword,
  ResetError,
  SessionLoginError,
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

  it("openSession abre sesión con POST /api/session y email + contraseña", async () => {
    const fn = mockFetch(true, 200, { id: "u1", name: "Ana" });
    await openSession(" ana@example.com ", "caballo-bateria");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/session");
    expect(init.method).toBe("POST");
    // El email se limpia en el borde de la API; la contraseña **no** se toca (un
    // espacio ahí puede ser parte de la clave).
    expect(JSON.parse(init.body as string)).toEqual({
      email: "ana@example.com",
      password: "caballo-bateria",
    });
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
    // creer que no hay sesión (pintaría la puerta y ocultaría el fallo real).
    mockFetch(false, 500, { detail: "boom" });
    await expect(getSession()).rejects.toThrow();
  });

  it("un 404 (la cuenta de la cookie ya no existe) se lee como «sin sesión»", async () => {
    // V3.80.2. Es el caso real: el webmaster purga una cuenta desde la consola y
    // el navegador se queda con una cookie firmada que apunta a nadie. Antes esto
    // lanzaba, tumbaba el arranque entero y la puerta salía sin salida.
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
 * V3.82: la entrada es email + contraseña, y el desenlace llega **tipado**.
 *
 * Lo que se fija aquí es que la puerta pueda distinguir los casos. Un `Error` de
 * texto los aplanaba todos, y con eso la puerta no habría podido decir «tu cuenta
 * no está activada» (una frase útil) en vez de «algo falló» (que no lo es).
 */
describe("session api · entrada por email (V3.82)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("un 401 se lee como credenciales que no cuadran, sin decir cuál falla", async () => {
    mockFetch(false, 401, { detail: "INVALID_CREDENTIALS" });
    const err = await openSession("ana@example.com", "no-es-esta").catch(
      (e: unknown) => e,
    );
    expect(err).toBeInstanceOf(SessionLoginError);
    expect((err as SessionLoginError).reason).toBe("invalid-credentials");
  });

  it("una cuenta sin activar se distingue de una contraseña mala", async () => {
    // Es la diferencia que evita que alguien se quede dando vueltas con su
    // contraseña: la cuenta existe y está autorizada, pero la invitación sigue
    // esperando en el correo.
    mockFetch(false, 403, { detail: "ACCOUNT_NOT_ACTIVATED" });
    const err = await openSession("ana@example.com", "loquesea").catch(
      (e: unknown) => e,
    );
    expect((err as SessionLoginError).reason).toBe("not-activated");
  });

  it("«fuera de servicio» y «dada de baja» llegan como desenlaces distintos", async () => {
    mockFetch(false, 403, { detail: "PROFILE_DISABLED" });
    await expect(openSession("a@b.es", "x")).rejects.toMatchObject({
      reason: "disabled",
    });
    mockFetch(false, 403, { detail: "ACCOUNT_UNENROLLED" });
    await expect(openSession("a@b.es", "x")).rejects.toMatchObject({
      reason: "unenrolled",
    });
  });

  it("el freno llega con su espera para poder contarla", async () => {
    mockFetch(false, 429, { detail: "PASSWORD_THROTTLED" }, { "retry-after": "37" });
    const err = await openSession("ana@example.com", "no-es-esta").catch(
      (e: unknown) => e,
    );
    expect((err as SessionLoginError).reason).toBe("throttled");
    expect((err as SessionLoginError).retryAfterSeconds).toBe(37);
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

/**
 * V3.82: activación (poner la contraseña desde la invitación) y restablecimiento
 * (contraseña nueva desde el correo). Los dos van **sin sesión** y los dos tienen
 * que poder decir «ese enlace ya no vale».
 */
describe("session api · activación y recuperación (V3.82)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("activateAccount manda token y contraseña a POST /api/account/activate", async () => {
    const fn = mockFetch(true, 200, { id: "u1", name: "Ana" });
    await activateAccount("invitacion", "caballo-bateria");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/account/activate");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      token: "invitacion",
      password: "caballo-bateria",
    });
  });

  it("una invitación caducada se distingue de una ya usada", async () => {
    mockFetch(false, 400, { detail: "ACTIVATION_TOKEN_EXPIRED" });
    const expired = await activateAccount("t", "caballo-bateria").catch(
      (e: unknown) => e,
    );
    expect((expired as ActivationError).reason).toBe("expired");

    mockFetch(false, 400, { detail: "ACTIVATION_TOKEN_INVALID" });
    const used = await activateAccount("t", "caballo-bateria").catch(
      (e: unknown) => e,
    );
    expect((used as ActivationError).reason).toBe("invalid");
  });

  it("forgotPassword manda solo el email y no promete un envío", async () => {
    const fn = mockFetch(true, 200, { sent: true });
    await forgotPassword(" ana@example.com ");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/account/forgot-password");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ email: "ana@example.com" });
  });

  it("resetPassword manda token y contraseña a POST /api/account/reset-password", async () => {
    const fn = mockFetch(true, 200, { id: "u1" });
    await resetPassword("del-correo", "otra-clave-larga");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/account/reset-password");
    expect(JSON.parse(init.body as string)).toEqual({
      token: "del-correo",
      password: "otra-clave-larga",
    });
  });

  it("un enlace de restablecimiento gastado llega como «no válido»", async () => {
    mockFetch(false, 400, { detail: "RESET_TOKEN_INVALID" });
    const err = await resetPassword("t", "otra-clave-larga").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ResetError);
    expect((err as ResetError).reason).toBe("invalid");
  });

  it("una avería del backend no se disfraza de enlace inválido", async () => {
    // La diferencia importa: «pide otro enlace» y «algo va mal» mandan a hacer
    // cosas distintas, y confundirlas hace repetir un paso que no era el problema.
    mockFetch(false, 500, { detail: "boom" });
    const err = await resetPassword("t", "otra-clave-larga").catch((e: unknown) => e);
    expect((err as ResetError).reason).toBe("error");
  });
});
