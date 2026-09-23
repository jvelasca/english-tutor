// @vitest-environment jsdom
/**
 * Arranque con contraseña y ciclo de vida de la cuenta (V3.81, Fase 3 del P0).
 *
 * Lo que se fija aquí es la parte que **no** puede fallar en silencio: el
 * arranque automático. Antes de la Fase 2, un `POST /api/session` que no fuera
 * 200 moría en un `catch` vacío, así que la app se quedaba sin cuenta activa y
 * sin decir por qué. Con una cuenta que tiene contraseña eso pasaría **siempre**,
 * y el alumno vería una puerta que no responde.
 *
 * Por eso los casos de aquí son de comportamiento del hook, no de la vista: que
 * la cuenta con credencial no se abra a ciegas, que la contraseña correcta deje
 * la sesión abierta, que la incorrecta se explique, y que las acciones de cuenta
 * (alta, salir, baja) dejen el estado local como el servidor dice y no como el
 * cliente supone.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import type { User } from "../types/api";
import { SessionPasswordError } from "../api/session";
import type { ProfileRequestOutcome } from "../api/profileRequests";
import { useChat } from "./useChat";

vi.mock("../api/session", async (importOriginal) => {
  // Se conserva el módulo real: `SessionPasswordError` tiene que ser **la misma
  // clase** que usa `useChat`, o su `instanceof` no reconocería ningún error.
  const actual = await importOriginal<typeof import("../api/session")>();
  return {
    ...actual,
    openSession: vi.fn(),
    getSession: vi.fn(),
    closeSession: vi.fn(),
    createAccount: vi.fn(),
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
  listUsers: vi.fn(),
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
import { listUsers } from "../api/users";
import { requestProfile, requestProfileDelete } from "../api/profileRequests";
import { ApiError } from "../api/client";

const openSessionMock = vi.mocked(openSession);
const getSessionMock = vi.mocked(getSession);
const listUsersMock = vi.mocked(listUsers);
const requestProfileMock = vi.mocked(requestProfile);
const requestProfileDeleteMock = vi.mocked(requestProfileDelete);
const closeSessionMock = vi.mocked(sessionApi.closeSession);
const createAccountMock = vi.mocked(sessionApi.createAccount);
const changePasswordMock = vi.mocked(sessionApi.changePassword);
const changeEmailMock = vi.mocked(sessionApi.changeEmail);
const resendVerificationMock = vi.mocked(sessionApi.resendVerification);
const unenrollAccountMock = vi.mocked(sessionApi.unenrollAccount);

function user(id: string, name: string, hasPassword = false): User {
  return {
    id,
    name,
    avatar_color: "",
    avatar_emoji: "",
    avatar_image: "",
    has_password: hasPassword,
    created_at: "2026-01-01T00:00:00Z",
  };
}

const ANA_CON_CLAVE = user("a", "Ana", true);
const BETO = user("b", "Beto");

beforeEach(() => {
  openSessionMock.mockReset();
  getSessionMock.mockReset();
  listUsersMock.mockReset();
  getSessionMock.mockResolvedValue(null);
  // Las acciones de cuenta arrancan con un desenlace razonable para que un test
  // que no las use no se lleve un `undefined` del mock recién reseteado.
  closeSessionMock.mockReset();
  closeSessionMock.mockResolvedValue({ closed: true });
  createAccountMock.mockReset();
  changePasswordMock.mockReset();
  changeEmailMock.mockReset();
  resendVerificationMock.mockReset();
  resendVerificationMock.mockResolvedValue({ sent: false, reason: "SMTP_NOT_CONFIGURED" });
  unenrollAccountMock.mockReset();
});

afterEach(cleanup);

/** Espera a que el arranque termine (la lista de perfiles cargada). */
async function boot() {
  const rendered = renderHook(() => useChat());
  await waitFor(() => expect(rendered.result.current.usersLoaded).toBe(true));
  return rendered;
}

describe("useChat · arranque con contraseña (V3.81)", () => {
  it("una cuenta sin contraseña se abre sola: es el caso heredado", async () => {
    listUsersMock.mockResolvedValue([BETO]);
    openSessionMock.mockResolvedValue(BETO);

    const { result } = await boot();

    await waitFor(() => expect(result.current.currentUserId).toBe("b"));
    expect(openSessionMock).toHaveBeenCalledWith("b", undefined);
  });

  it("una cuenta con contraseña no se abre a ciegas: se pide", async () => {
    listUsersMock.mockResolvedValue([ANA_CON_CLAVE]);

    const { result } = await boot();

    // Ni un POST condenado a 401 ni un arranque mudo: la puerta recibe la
    // cuenta que espera su contraseña.
    expect(openSessionMock).not.toHaveBeenCalled();
    expect(result.current.passwordPromptUserId).toBe("a");
    expect(result.current.currentUserId).toBeNull();
    expect(result.current.passwordFeedback).toBeNull();
  });

  it("la contraseña correcta deja la cuenta activa y cierra el paso", async () => {
    listUsersMock.mockResolvedValue([ANA_CON_CLAVE]);
    openSessionMock.mockResolvedValue(ANA_CON_CLAVE);

    const { result } = await boot();
    await act(async () => {
      await result.current.submitPassword("a", "4821");
    });

    expect(openSessionMock).toHaveBeenCalledWith("a", "4821");
    await waitFor(() => expect(result.current.currentUserId).toBe("a"));
    expect(result.current.passwordPromptUserId).toBeNull();
    expect(result.current.passwordFeedback).toBeNull();
  });

  it("una contraseña incorrecta se explica y no activa la cuenta", async () => {
    listUsersMock.mockResolvedValue([ANA_CON_CLAVE]);
    openSessionMock.mockRejectedValue(new SessionPasswordError("password-invalid"));

    const { result } = await boot();
    await act(async () => {
      await result.current.submitPassword("a", "0000");
    });

    expect(result.current.passwordFeedback).toBe("password-invalid");
    expect(result.current.currentUserId).toBeNull();
    expect(result.current.passwordPromptUserId).toBe("a");
  });

  it("el freno del servidor llega con su espera", async () => {
    listUsersMock.mockResolvedValue([ANA_CON_CLAVE]);
    openSessionMock.mockRejectedValue(new SessionPasswordError("password-throttled", 42));

    const { result } = await boot();
    await act(async () => {
      await result.current.submitPassword("a", "0000");
    });

    expect(result.current.passwordFeedback).toBe("password-throttled");
    expect(result.current.passwordRetryAfter).toBe(42);
  });

  it("elegir en el selector una cuenta con contraseña también la pide", async () => {
    // El caso de cambio de cuenta dentro de la app: el servidor responde 401
    // `PASSWORD_REQUIRED` y la puerta tiene que aparecer aunque ya hubiera una
    // cuenta activa (si no, el paso quedaría invisible detrás de la app).
    listUsersMock.mockResolvedValue([BETO, ANA_CON_CLAVE]);
    getSessionMock.mockResolvedValue(BETO);
    const { result } = await boot();
    await waitFor(() => expect(result.current.currentUserId).toBe("b"));

    openSessionMock.mockRejectedValueOnce(new SessionPasswordError("password-required"));
    act(() => result.current.selectUser("a"));

    await waitFor(() => expect(result.current.passwordPromptUserId).toBe("a"));
    // La cuenta anterior sigue activa: cancelar devuelve a la app tal cual.
    expect(result.current.currentUserId).toBe("b");
  });

  it("cancelar la contraseña devuelve a la puerta sin tocar la sesión", async () => {
    listUsersMock.mockResolvedValue([ANA_CON_CLAVE]);
    const { result } = await boot();
    expect(result.current.passwordPromptUserId).toBe("a");

    act(() => result.current.cancelPassword());
    expect(result.current.passwordPromptUserId).toBeNull();
    expect(result.current.passwordFeedback).toBeNull();
    expect(result.current.currentUserId).toBeNull();
    expect(openSessionMock).not.toHaveBeenCalled();
  });
});

describe("useChat · pedir una cuenta (V3.77)", () => {
  it("pedir una cuenta no la crea ni abre sesión: deja la solicitud", async () => {
    // La app dejó de crear cuentas a la primera: por LAN solo se puede
    // **pedir**, y una solicitud no es una cuenta. Si esto abriera sesión, la app
    // se pintaría con un `currentUserId` que no existe y todo daría 401.
    listUsersMock.mockResolvedValue([]);
    requestProfileMock.mockResolvedValue({
      ok: true,
      request: {
        id: 1,
        kind: "create",
        display_name: "Ana",
        user_id: "",
        note: "",
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
      outcome = await result.current.requestProfileForGate("  Ana  ");
    });

    expect(requestProfileMock).toHaveBeenCalledWith("Ana");
    expect(outcome).toEqual({ ok: true, request: expect.objectContaining({ id: 1 }) });
    expect(openSessionMock).not.toHaveBeenCalled();
    expect(result.current.currentUserId).toBeNull();
    expect(result.current.users).toEqual([]);
  });

  it("un nombre ya pedido se cuenta como tal, no como error del servidor", async () => {
    listUsersMock.mockResolvedValue([]);
    requestProfileMock.mockResolvedValue({ ok: false, reason: "duplicate" });

    const { result } = await boot();
    let outcome: ProfileRequestOutcome | undefined;
    await act(async () => {
      outcome = await result.current.requestProfileForGate("Ana");
    });

    expect(outcome).toEqual({ ok: false, reason: "duplicate" });
  });

  it("sin nombre se propone el siguiente nombre por defecto", async () => {
    // En la cola del webmaster «Usuario 2» es más útil que una fila vacía.
    listUsersMock.mockResolvedValue([user("b", "Usuario")]);
    requestProfileMock.mockResolvedValue({ ok: true, request: {} as never });

    const { result } = await boot();
    await act(async () => {
      await result.current.requestProfileForGate("   ");
    });

    expect(requestProfileMock).toHaveBeenCalledWith("Usuario 2");
  });

  it("pedir la baja no borra nada: solo registra la solicitud", async () => {
    listUsersMock.mockResolvedValue([BETO]);
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
    // La cuenta sigue en la lista: la baja la resuelve el webmaster, no la app.
    expect(result.current.users.map((u) => u.id)).toContain("b");
  });
});

describe("useChat · arranque cuando la sonda de sesión falla (V3.80.2)", () => {
  it("un fallo de la sesión NO vacía la lista de usuarios", async () => {
    // El fallo real que colgaba la app: la cookie de sesión apuntaba a una cuenta
    // purgada, `GET /api/session` contestaba 404 y el `Promise.all` del arranque
    // lo convertía en un rechazo conjunto, así que `setUsers` no se ejecutaba
    // nunca. La puerta salía con la lista **vacía** y sin forma de salir.
    listUsersMock.mockResolvedValue([user("a", "Ana"), BETO]);
    getSessionMock.mockRejectedValue(new Error("GET /api/session 404"));

    const { result } = await boot();

    expect(result.current.users.map((u) => u.name)).toEqual(["Ana", "Beto"]);
    // El fallo de la sesión no se confunde con un fallo de la lista.
    expect(result.current.usersLoadFailed).toBe(false);
  });

  it("si lo que falla es la lista, se dice en vez de fingir que no hay usuarios", async () => {
    listUsersMock.mockRejectedValue(new Error("backend arrancando"));
    getSessionMock.mockResolvedValue(null);

    const { result } = await boot();

    expect(result.current.users).toEqual([]);
    expect(result.current.usersLoadFailed).toBe(true);
  });

  it("reintentar vuelve a pedir la lista y deja la puerta usable", async () => {
    // `reloadUsers` es la salida que faltaba: un backend que tarda dos segundos
    // de más no debe obligar a recargar el navegador a mano.
    listUsersMock.mockRejectedValueOnce(new Error("todavía arrancando"));
    getSessionMock.mockResolvedValue(null);
    const { result } = await boot();
    expect(result.current.usersLoadFailed).toBe(true);

    listUsersMock.mockResolvedValue([BETO]);
    await act(async () => {
      await result.current.reloadUsers();
    });

    expect(result.current.usersLoadFailed).toBe(false);
    expect(result.current.users.map((u) => u.id)).toEqual(["b"]);
  });
});

describe("useChat · ciclo de vida de la cuenta (V3.81)", () => {
  it("el alta deja la cuenta activa sin volver a pedir la contraseña", async () => {
    // Quien acaba de registrarse ya ha escrito lo que hay que escribir: pedirle
    // la contraseña otra vez en el paso siguiente sería castigar el registro.
    listUsersMock.mockResolvedValue([]);
    createAccountMock.mockResolvedValue(ANA_CON_CLAVE);
    openSessionMock.mockResolvedValue(ANA_CON_CLAVE);

    const { result } = await boot();
    let outcome: Awaited<ReturnType<typeof result.current.createAccountForGate>> | undefined;
    await act(async () => {
      outcome = await result.current.createAccountForGate(
        "  Ana  ",
        " ana@example.com ",
        "caballo-bateria",
      );
    });

    expect(createAccountMock).toHaveBeenCalledWith(
      "Ana",
      "ana@example.com",
      "caballo-bateria",
    );
    expect(openSessionMock).toHaveBeenCalledWith("a", "caballo-bateria");
    expect(outcome?.ok).toBe(true);
    await waitFor(() => expect(result.current.currentUserId).toBe("a"));
  });

  it("un nombre o un email ya usados vuelven como desenlace, no como avería", async () => {
    listUsersMock.mockResolvedValue([]);
    createAccountMock.mockRejectedValue(
      new ApiError(409, "EMAIL_TAKEN", { message: "EMAIL_TAKEN" }),
    );

    const { result } = await boot();
    let outcome: Awaited<ReturnType<typeof result.current.createAccountForGate>> | undefined;
    await act(async () => {
      outcome = await result.current.createAccountForGate("Ana", "ana@example.com", "caballo-bateria");
    });

    expect(outcome).toEqual({ ok: false, reason: "email-taken" });
  });

  it("el alta desde la LAN se cuenta como «no es tu equipo», no como caída", async () => {
    listUsersMock.mockResolvedValue([]);
    createAccountMock.mockRejectedValue(
      new ApiError(403, "no", { message: "no" }),
    );

    const { result } = await boot();
    let outcome: Awaited<ReturnType<typeof result.current.createAccountForGate>> | undefined;
    await act(async () => {
      outcome = await result.current.createAccountForGate("Ana", "ana@example.com", "caballo-bateria");
    });

    expect(outcome).toEqual({ ok: false, reason: "not-local" });
  });

  it("Salir cierra la sesión en el servidor y devuelve a la puerta", async () => {
    // `closeSession()` existía desde V3.75 sin que nadie la llamara: en un equipo
    // compartido no había forma de salir salvo borrar las cookies a mano.
    listUsersMock.mockResolvedValue([BETO]);
    // La primera sonda devuelve la sesión abierta; tras salir, el servidor ya no
    // la reconoce (que es lo que hace de verdad al caducar la cookie).
    getSessionMock.mockResolvedValueOnce(BETO).mockResolvedValue(null);
    closeSessionMock.mockResolvedValue({ closed: true });

    const { result } = await boot();
    await waitFor(() => expect(result.current.currentUserId).toBe("b"));

    await act(async () => {
      await result.current.signOut();
    });

    expect(closeSessionMock).toHaveBeenCalled();
    expect(result.current.currentUserId).toBeNull();
  });

  it("un cambio de contraseña fallido se cuenta con su motivo, no como avería", async () => {
    listUsersMock.mockResolvedValue([BETO]);
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

  it("la contraseña temporal del webmaster obliga a cambiarla", async () => {
    // Se aprende de la respuesta del servidor, nunca se adivina: `useChat` marca
    // el aviso con el `must_change_password` que viene en la cuenta.
    const conTemporal = { ...ANA_CON_CLAVE, must_change_password: true };
    listUsersMock.mockResolvedValue([conTemporal]);
    getSessionMock.mockResolvedValue(conTemporal);

    const { result } = await boot();
    await waitFor(() => expect(result.current.currentUserId).toBe("a"));
    expect(result.current.mustChangePassword).toBe(true);
  });

  it("darse de baja cierra la sesión sin borrar nada", async () => {
    listUsersMock.mockResolvedValue([BETO]);
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
    listUsersMock.mockResolvedValue([]);
    resendVerificationMock.mockResolvedValue({
      sent: false,
      reason: "SMTP_NOT_CONFIGURED",
    });

    const { result } = await boot();
    let sent: boolean | undefined;
    await act(async () => {
      sent = await result.current.resendVerificationNow();
    });

    expect(sent).toBe(false);
  });
});
