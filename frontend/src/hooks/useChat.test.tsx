// @vitest-environment jsdom
/**
 * Arranque de la sesión y ciclo de vida de la cuenta (V3.82).
 *
 * Lo que se fija aquí es la parte que **no** puede fallar en silencio:
 *
 * - El arranque ya no «elige» con quién entrar. Antes resolvía una cuenta de una
 *   lista y abría sesión nombrando a alguien; con el login por email eso
 *   desaparece, y con él la posibilidad de arrancar como otra persona.
 * - Entrar es un acto explícito, y sus desenlaces (credenciales malas, cuenta sin
 *   activar, freno) vuelven **tipados** para que la puerta pueda contarlos.
 * - Las acciones de cuenta (salir, baja) dejan el estado local como el servidor
 *   dice y no como el cliente supone.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import type { User } from "../types/api";
import { SessionLoginError } from "../api/session";
import type { ProfileRequestOutcome } from "../api/profileRequests";
import { useChat } from "./useChat";

vi.mock("../api/session", async (importOriginal) => {
  // Se conserva el módulo real: `SessionLoginError` tiene que ser **la misma
  // clase** que usa `useChat`, o su `instanceof` no reconocería ningún error.
  const actual = await importOriginal<typeof import("../api/session")>();
  return {
    ...actual,
    openSession: vi.fn(),
    getSession: vi.fn(),
    closeSession: vi.fn(),
    changePassword: vi.fn(),
    changeEmail: vi.fn(),
    resendVerification: vi.fn(),
    unenrollAccount: vi.fn(),
  };
});

vi.mock("../api/chat", () => ({
  getModels: vi.fn().mockResolvedValue({ models: [], default_model: null }),
  streamChat: vi.fn(),
}));
vi.mock("../api/academy", () => ({ completeLesson: vi.fn() }));
vi.mock("../api/conversations", () => ({
  createConversation: vi.fn(),
  deleteConversation: vi.fn(),
  getConversation: vi.fn(),
  listConversations: vi.fn().mockResolvedValue([]),
  saveConversation: vi.fn(),
}));
vi.mock("../api/users", () => ({
  updateUser: vi.fn(),
}));
vi.mock("../api/profileRequests", () => ({
  requestProfile: vi.fn(),
  requestProfileDelete: vi.fn(),
}));
vi.mock("../api/progress", () => ({
  getProgressHistory: vi.fn().mockResolvedValue(null),
}));
vi.mock("../api/settings", () => ({
  getSettings: vi.fn().mockResolvedValue({ settings: {} }),
  saveSettings: vi.fn().mockResolvedValue({ settings: {} }),
}));
vi.mock("../api/learning", () => ({
  analyzeText: vi.fn(),
  getEvents: vi.fn().mockResolvedValue([]),
  getProfile: vi.fn().mockResolvedValue(null),
}));

import { getSession, openSession } from "../api/session";
import * as sessionApi from "../api/session";
import { requestProfile, requestProfileDelete } from "../api/profileRequests";
import { ApiError } from "../api/client";

const openSessionMock = vi.mocked(openSession);
const getSessionMock = vi.mocked(getSession);
const requestProfileMock = vi.mocked(requestProfile);
const requestProfileDeleteMock = vi.mocked(requestProfileDelete);
const closeSessionMock = vi.mocked(sessionApi.closeSession);
const changePasswordMock = vi.mocked(sessionApi.changePassword);
const resendVerificationMock = vi.mocked(sessionApi.resendVerification);
const unenrollAccountMock = vi.mocked(sessionApi.unenrollAccount);

function user(id: string, name: string): User {
  return {
    id,
    name,
    avatar_color: "",
    avatar_emoji: "",
    avatar_image: "",
    email: `${id}@example.com`,
    has_password: true,
    created_at: "2026-01-01T00:00:00Z",
  };
}

const ANA = user("a", "Ana");
const BETO = user("b", "Beto");

beforeEach(() => {
  openSessionMock.mockReset();
  getSessionMock.mockReset();
  getSessionMock.mockResolvedValue(null);
  // Las acciones de cuenta arrancan con un desenlace razonable para que un test
  // que no las use no se lleve un `undefined` del mock recién reseteado.
  closeSessionMock.mockReset();
  closeSessionMock.mockResolvedValue({ closed: true });
  changePasswordMock.mockReset();
  resendVerificationMock.mockReset();
  resendVerificationMock.mockResolvedValue({
    sent: false,
    reason: "SMTP_NOT_CONFIGURED",
  });
  unenrollAccountMock.mockReset();
});

afterEach(cleanup);

/** Espera a que el arranque termine (la sesión comprobada). */
async function boot() {
  const rendered = renderHook(() => useChat());
  await waitFor(() => expect(rendered.result.current.usersLoaded).toBe(true));
  return rendered;
}

describe("useChat · arranque de la sesión (V3.82)", () => {
  it("sin sesión no se abre ninguna: la app pide credencial", async () => {
    const { result } = await boot();

    expect(openSessionMock).not.toHaveBeenCalled();
    expect(result.current.currentUserId).toBeNull();
    expect(result.current.users).toEqual([]);
    expect(result.current.usersLoadFailed).toBe(false);
  });

  it("con sesión adoptada, la cuenta es la única que la app conoce", async () => {
    // V3.82: `users` deja de ser «las cuentas que existen» y pasa a ser «la
    // cuenta de esta sesión». Es lo que hace imposible que la app enumere a
    // nadie, y de paso lo que garantiza que el menú solo pueda hablar de ti.
    getSessionMock.mockResolvedValue(BETO);

    const { result } = await boot();

    await waitFor(() => expect(result.current.currentUserId).toBe("b"));
    expect(result.current.users).toEqual([BETO]);
    expect(result.current.usersLoadFailed).toBe(false);
  });

  it("con `must_change_password` la app marca el cambio forzado", async () => {
    // Se aprende de la respuesta del servidor, nunca se adivina.
    getSessionMock.mockResolvedValue({ ...ANA, must_change_password: true });

    const { result } = await boot();

    await waitFor(() => expect(result.current.currentUserId).toBe("a"));
    expect(result.current.mustChangePassword).toBe(true);
  });
});

describe("useChat · entrar con email y contraseña (V3.82)", () => {
  it("una credencial buena abre la cuenta de esa sesión", async () => {
    openSessionMock.mockResolvedValue(ANA);

    const { result } = await boot();
    let outcome: Awaited<ReturnType<typeof result.current.login>> | undefined;
    await act(async () => {
      outcome = await result.current.login("ana@example.com", "caballo-bateria");
    });

    expect(openSessionMock).toHaveBeenCalledWith("ana@example.com", "caballo-bateria");
    expect(outcome?.ok).toBe(true);
    await waitFor(() => expect(result.current.currentUserId).toBe("a"));
    expect(result.current.users).toEqual([ANA]);
  });

  it("una credencial mala vuelve como desenlace, no como avería", async () => {
    openSessionMock.mockRejectedValue(new SessionLoginError("invalid-credentials"));

    const { result } = await boot();
    let outcome: Awaited<ReturnType<typeof result.current.login>> | undefined;
    await act(async () => {
      outcome = await result.current.login("ana@example.com", "0000");
    });

    expect(outcome).toEqual({ ok: false, reason: "invalid-credentials" });
    expect(result.current.currentUserId).toBeNull();
    expect(result.current.users).toEqual([]);
  });

  it("una cuenta sin activar se distingue de una contraseña mala", async () => {
    openSessionMock.mockRejectedValue(new SessionLoginError("not-activated"));

    const { result } = await boot();
    let outcome: Awaited<ReturnType<typeof result.current.login>> | undefined;
    await act(async () => {
      outcome = await result.current.login("ana@example.com", "loquesea");
    });

    // La diferencia importa: el texto es «abre el enlace de tu correo», que sí se
    // puede hacer, en vez de «algo falló».
    expect(outcome).toEqual({ ok: false, reason: "not-activated" });
  });

  it("el freno llega con su espera para poder contarla", async () => {
    openSessionMock.mockRejectedValue(new SessionLoginError("throttled", 42));

    const { result } = await boot();
    let outcome: Awaited<ReturnType<typeof result.current.login>> | undefined;
    await act(async () => {
      outcome = await result.current.login("ana@example.com", "0000");
    });

    expect(outcome).toEqual({
      ok: false,
      reason: "throttled",
      retryAfterSeconds: 42,
    });
  });

  it("un backend caído no se disfraza de credencial mala", async () => {
    // Distinguirlo es lo que evita que alguien cambie su contraseña —y encima la
    // recuerde mal— por un servidor que no responde.
    openSessionMock.mockRejectedValue(new Error("sin red"));

    const { result } = await boot();
    let outcome: Awaited<ReturnType<typeof result.current.login>> | undefined;
    await act(async () => {
      outcome = await result.current.login("ana@example.com", "caballo-bateria");
    });

    expect(outcome).toEqual({ ok: false, reason: "error" });
  });
});

describe("useChat · pedir una cuenta (V3.77; email y avatar en V3.82)", () => {
  it("pedir una cuenta no la crea ni abre sesión: deja la solicitud", async () => {
    // Una solicitud no es una cuenta. Si esto abriera sesión, la app se pintaría
    // con un `currentUserId` que no existe y todo daría 401.
    requestProfileMock.mockResolvedValue({
      ok: true,
      request: {
        id: 1,
        kind: "create",
        display_name: "Ana",
        user_id: "",
        note: "",
        email: "ana@example.com",
        requested_at: "2026-09-21T22:00:00Z",
        status: "pending",
        decided_at: "",
        decided_note: "",
        resolved_user_id: "",
      },
    });

    const { result } = await boot();
    let outcome: ProfileRequestOutcome | undefined;
    await act(async () => {
      outcome = await result.current.requestProfileForGate(
        "  Ana  ",
        " ana@example.com ",
        { avatar_emoji: "🦊" },
      );
    });

    expect(requestProfileMock).toHaveBeenCalledWith(
      "Ana",
      " ana@example.com ",
      { avatar_emoji: "🦊" },
      "",
    );
    expect(outcome).toEqual({ ok: true, request: expect.objectContaining({ id: 1 }) });
    expect(openSessionMock).not.toHaveBeenCalled();
    expect(result.current.currentUserId).toBeNull();
  });

  it("un email ya con cuenta se cuenta como tal, no como error del servidor", async () => {
    requestProfileMock.mockResolvedValue({ ok: false, reason: "email-taken" });

    const { result } = await boot();
    let outcome: ProfileRequestOutcome | undefined;
    await act(async () => {
      outcome = await result.current.requestProfileForGate("Ana", "ana@example.com");
    });

    expect(outcome).toEqual({ ok: false, reason: "email-taken" });
  });

  it("sin nombre se propone el siguiente nombre por defecto", async () => {
    // En la cola del webmaster «Usuario» es más útil que una fila vacía.
    requestProfileMock.mockResolvedValue({ ok: true, request: {} as never });

    const { result } = await boot();
    await act(async () => {
      await result.current.requestProfileForGate("   ", "ana@example.com");
    });

    expect(requestProfileMock).toHaveBeenCalledWith(
      "Usuario",
      "ana@example.com",
      {},
      "",
    );
  });

  it("pedir la baja no borra nada: solo registra la solicitud", async () => {
    getSessionMock.mockResolvedValue(BETO);
    requestProfileDeleteMock.mockResolvedValue({
      ok: true,
      request: { id: 9, kind: "delete", status: "pending" } as never,
    });

    const { result } = await boot();
    let outcome: ProfileRequestOutcome | undefined;
    await act(async () => {
      outcome = await result.current.requestProfileRemoval("ya no lo uso");
    });

    expect(requestProfileDeleteMock).toHaveBeenCalledWith("ya no lo uso");
    expect(outcome?.ok).toBe(true);
    // La cuenta sigue ahí: la baja la resuelve el webmaster, no la app.
    expect(result.current.users.map((u) => u.id)).toContain("b");
  });
});

describe("useChat · arranque cuando la sonda de sesión falla (V3.80.2)", () => {
  it("un fallo de la sesión se declara en vez de fingir «no hay sesión»", async () => {
    // Un backend caído no es «no hay sesión»: si se confundieran, la puerta
    // ofrecería entrar y el alumno teclearía su contraseña contra nadie.
    getSessionMock.mockRejectedValue(new Error("GET /api/session 500"));

    const { result } = await boot();

    expect(result.current.usersLoadFailed).toBe(true);
    expect(result.current.currentUserId).toBeNull();
  });

  it("reintentar vuelve a comprobar la sesión y deja la puerta usable", async () => {
    // `reloadSession` es la salida que faltaba: un backend que tarda dos segundos
    // de más no debe obligar a recargar el navegador a mano.
    getSessionMock.mockRejectedValueOnce(new Error("todavía arrancando"));
    const { result } = await boot();
    expect(result.current.usersLoadFailed).toBe(true);

    getSessionMock.mockResolvedValue(BETO);
    await act(async () => {
      await result.current.reloadSession();
    });

    expect(result.current.usersLoadFailed).toBe(false);
    expect(result.current.users.map((u) => u.id)).toEqual(["b"]);
  });
});

describe("useChat · ciclo de vida de la cuenta (V3.81)", () => {
  it("Salir cierra la sesión en el servidor y devuelve a la puerta", async () => {
    // `closeSession()` existía desde V3.75 sin que nadie la llamara: en un equipo
    // compartido no había forma de salir salvo borrar las cookies a mano.
    getSessionMock.mockResolvedValueOnce(BETO).mockResolvedValue(null);

    const { result } = await boot();
    await waitFor(() => expect(result.current.currentUserId).toBe("b"));

    await act(async () => {
      await result.current.signOut();
    });

    expect(closeSessionMock).toHaveBeenCalled();
    expect(result.current.currentUserId).toBeNull();
    expect(result.current.users).toEqual([]);
  });

  it("un cambio de contraseña fallido se cuenta con su motivo, no como avería", async () => {
    getSessionMock.mockResolvedValue(BETO);
    changePasswordMock.mockRejectedValue(
      new ApiError(401, "PASSWORD_INVALID", { message: "PASSWORD_INVALID" }),
    );

    const { result } = await boot();
    await waitFor(() => expect(result.current.currentUserId).toBe("b"));

    let outcome: Awaited<ReturnType<typeof result.current.changePasswordNow>> | undefined;
    await act(async () => {
      outcome = await result.current.changePasswordNow("no-es-esta", "otra-caballo");
    });

    expect(outcome).toEqual({ ok: false, reason: "password-invalid" });
  });

  it("darse de baja cierra la sesión sin borrar nada", async () => {
    getSessionMock.mockResolvedValueOnce(BETO).mockResolvedValue(null);
    unenrollAccountMock.mockResolvedValue({
      unenrolled: true,
      user: { ...BETO, status: "unenrolled" },
    });

    const { result } = await boot();
    await waitFor(() => expect(result.current.currentUserId).toBe("b"));

    await act(async () => {
      await result.current.unenrollNow("caballo-bateria");
    });

    expect(unenrollAccountMock).toHaveBeenCalledWith("caballo-bateria");
    // La app vuelve a la puerta: el servidor ya retiró la cookie y seguir
    // pintando la app sería mentir hasta el siguiente 403.
    expect(result.current.currentUserId).toBeNull();
  });

  it("reenviar la verificación sin SMTP no finge un envío", async () => {
    getSessionMock.mockResolvedValue(BETO);

    const { result } = await boot();
    await waitFor(() => expect(result.current.currentUserId).toBe("b"));

    let sent: boolean | undefined;
    await act(async () => {
      sent = await result.current.resendVerificationNow();
    });

    expect(sent).toBe(false);
  });
});
