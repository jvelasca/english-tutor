// @vitest-environment jsdom
/**
 * Solicitudes de perfil (V3.77).
 *
 * Lo que se fija aquí es la **traducción de desenlaces**: el backend distingue
 * «ya está pedido» (409), «cola llena» (429), «cupo por IP» (429 con
 * `RATE_LIMITED`) y «nombre que no sirve» (422), y la pantalla necesita esa
 * distinción para decir cosas distintas. Convertirlo todo en `false` —como hacía
 * el alta anterior— obligaría a la UI a decir «algo falló» y a nadie le sirve.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./client";
import { requestProfile, requestProfileDelete } from "./profileRequests";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function respondOnce(status: number, body: unknown): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("requestProfile", () => {
  it("registra la solicitud sin sesión, con email y avatar (V3.82)", async () => {
    const fetchMock = respondOnce(201, { id: 4, kind: "create", status: "pending" });

    const outcome = await requestProfile(
      "Ana",
      " ana@example.com ",
      { avatar_color: "#6366f1", avatar_emoji: "🦊" },
      " 3.º ESO ",
    );

    expect(outcome).toEqual({
      ok: true,
      request: expect.objectContaining({ id: 4 }),
    });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/profile-requests");
    expect(init.method).toBe("POST");
    // Nombre, email y nota van recortados: los espacios de sobra son ruido en
    // una cola que lee una persona. El avatar va tal cual se eligió, y lo que no
    // se eligió **no se manda** (el backend distingue «sin elegir» de «elegido»).
    expect(JSON.parse(init.body as string)).toEqual({
      display_name: "Ana",
      email: "ana@example.com",
      note: "3.º ESO",
      avatar_color: "#6366f1",
      avatar_emoji: "🦊",
    });
  });

  it("sin avatar elegido el cuerpo no lleva huecos vacíos", async () => {
    const fetchMock = respondOnce(201, { id: 4 });

    await requestProfile("Ana", "ana@example.com");

    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual({
      display_name: "Ana",
      email: "ana@example.com",
      note: "",
    });
  });

  it("un nombre vacío no llega a la red", async () => {
    const fetchMock = respondOnce(201, {});

    const outcome = await requestProfile("   ", "ana@example.com");

    expect(outcome).toEqual({ ok: false, reason: "invalid" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("traduce cada estado del backend a su motivo", async () => {
    const casos: Array<[number, unknown, string]> = [
      [409, { detail: "Ya hay una solicitud pendiente" }, "duplicate"],
      // V3.82: un 409 puede ser «ya pediste esto» (duplicado) o «ese email ya
      // tiene cuenta». La respuesta útil es distinta —esperar vs entrar o
      // recuperar la contraseña—, así que no se juntan.
      [409, { detail: "EMAIL_TAKEN" }, "email-taken"],
      [422, { detail: "Nombre de perfil no válido" }, "invalid"],
      [429, { detail: "Hay demasiadas solicitudes pendientes" }, "full"],
      // El 429 del cupo por IP llega con `code: RATE_LIMITED`, que el cliente
      // convierte en `detail: "RATE_LIMITED"`: no es «cola llena», es «espera».
      [429, { detail: "RATE_LIMITED", code: "RATE_LIMITED" }, "throttled"],
      [500, { detail: "boom" }, "offline"],
    ];

    for (const [status, body, esperado] of casos) {
      respondOnce(status, body);
      const outcome = await requestProfile("Ana", "ana@example.com");
      expect(outcome, `status ${status}`).toEqual({
        ok: false,
        reason: esperado,
      });
    }
  });

  it("una caída de red no lanza: la pantalla tiene que poder decirlo", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new ApiError(0, "network")),
    );

    await expect(requestProfile("Ana", "ana@example.com")).resolves.toEqual({
      ok: false,
      reason: "offline",
    });
  });
});

describe("requestProfileDelete", () => {
  it("pide la baja del perfil de la sesión, sin id en la ruta", async () => {
    const fetchMock = respondOnce(201, { id: 9, kind: "delete", status: "pending" });

    const outcome = await requestProfileDelete("ya no lo uso");

    expect(outcome.ok).toBe(true);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    // Sin `{id}`: no existe la forma de pedir la baja del perfil de otro.
    expect(url).toBe("/api/profile-requests/delete");
    expect(JSON.parse(init.body as string)).toEqual({ note: "ya no lo uso" });
  });

  it("una baja repetida se cuenta como ya pedida", async () => {
    respondOnce(409, { detail: "Ya hay una solicitud pendiente" });

    expect(await requestProfileDelete()).toEqual({
      ok: false,
      reason: "duplicate",
    });
  });
});
