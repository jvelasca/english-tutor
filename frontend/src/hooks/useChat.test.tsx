// @vitest-environment jsdom
/**
 * Arranque con PIN (V3.76, Fase 3 del P0 de identidad).
 *
 * Lo que se fija aquí es la parte que **no** puede fallar en silencio: el
 * arranque automático. Antes de esta fase, un `POST /api/session` que no fuera
 * 200 moría en un `catch` vacío, así que la app se quedaba sin perfil activo y
 * sin decir por qué. Con un perfil que tiene PIN eso pasaría **siempre**, y el
 * alumno vería una puerta de perfiles que no responde.
 *
 * Por eso los casos de aquí son de comportamiento del hook, no de la vista: que
 * el perfil con PIN no se abra a ciegas, que el PIN correcto deje la sesión
 * abierta, y que el incorrecto se explique en vez de desaparecer.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import type { User } from "../types/api";
import { SessionPinError } from "../api/session";
import type { ProfileRequestOutcome } from "../api/profileRequests";
import { useChat } from "./useChat";

vi.mock("../api/session", async (importOriginal) => {
  // Se conserva el módulo real: `SessionPinError` tiene que ser **la misma
  // clase** que usa `useChat`, o su `instanceof` no reconocería ningún error.
  const actual = await importOriginal<typeof import("../api/session")>();
  return {
    ...actual,
    openSession: vi.fn(),
    getSession: vi.fn(),
    setSessionPin: vi.fn(),
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
import { listUsers } from "../api/users";
import { requestProfile, requestProfileDelete } from "../api/profileRequests";

const openSessionMock = vi.mocked(openSession);
const getSessionMock = vi.mocked(getSession);
const listUsersMock = vi.mocked(listUsers);
const requestProfileMock = vi.mocked(requestProfile);
const requestProfileDeleteMock = vi.mocked(requestProfileDelete);

function user(id: string, name: string, hasPin = false): User {
  return {
    id,
    name,
    avatar_color: "",
    avatar_emoji: "",
    avatar_image: "",
    has_pin: hasPin,
    created_at: "2026-01-01T00:00:00Z",
  };
}

const ANA_CON_PIN = user("a", "Ana", true);
const BETO = user("b", "Beto");

beforeEach(() => {
  openSessionMock.mockReset();
  getSessionMock.mockReset();
  listUsersMock.mockReset();
  getSessionMock.mockResolvedValue(null);
});

afterEach(cleanup);

/** Espera a que el arranque termine (la lista de perfiles cargada). */
async function boot() {
  const rendered = renderHook(() => useChat());
  await waitFor(() => expect(rendered.result.current.usersLoaded).toBe(true));
  return rendered;
}

describe("useChat · arranque con PIN (V3.76)", () => {
  it("un perfil sin PIN se abre solo, como siempre", async () => {
    listUsersMock.mockResolvedValue([BETO]);
    openSessionMock.mockResolvedValue(BETO);

    const { result } = await boot();

    await waitFor(() => expect(result.current.currentUserId).toBe("b"));
    expect(openSessionMock).toHaveBeenCalledWith("b", undefined);
  });

  it("un perfil con PIN no se abre a ciegas: se pide el PIN", async () => {
    listUsersMock.mockResolvedValue([ANA_CON_PIN]);

    const { result } = await boot();

    // Ni un POST condenado a 401 ni un arranque mudo: la puerta recibe el
    // perfil que espera su PIN.
    expect(openSessionMock).not.toHaveBeenCalled();
    expect(result.current.pinPromptUserId).toBe("a");
    expect(result.current.currentUserId).toBeNull();
    expect(result.current.pinFeedback).toBeNull();
  });

  it("el PIN correcto deja el perfil activo y cierra el paso", async () => {
    listUsersMock.mockResolvedValue([ANA_CON_PIN]);
    openSessionMock.mockResolvedValue(ANA_CON_PIN);

    const { result } = await boot();
    await act(async () => {
      await result.current.submitPin("a", "4821");
    });

    expect(openSessionMock).toHaveBeenCalledWith("a", "4821");
    await waitFor(() => expect(result.current.currentUserId).toBe("a"));
    expect(result.current.pinPromptUserId).toBeNull();
    expect(result.current.pinFeedback).toBeNull();
  });

  it("un PIN incorrecto se explica y no activa el perfil", async () => {
    listUsersMock.mockResolvedValue([ANA_CON_PIN]);
    openSessionMock.mockRejectedValue(new SessionPinError("pin-invalid"));

    const { result } = await boot();
    await act(async () => {
      await result.current.submitPin("a", "0000");
    });

    expect(result.current.pinFeedback).toBe("pin-invalid");
    expect(result.current.currentUserId).toBeNull();
    expect(result.current.pinPromptUserId).toBe("a");
  });

  it("el freno del servidor llega con su espera", async () => {
    listUsersMock.mockResolvedValue([ANA_CON_PIN]);
    openSessionMock.mockRejectedValue(new SessionPinError("pin-throttled", 42));

    const { result } = await boot();
    await act(async () => {
      await result.current.submitPin("a", "0000");
    });

    expect(result.current.pinFeedback).toBe("pin-throttled");
    expect(result.current.pinRetryAfter).toBe(42);
  });

  it("elegir en el selector un perfil con PIN también pide el PIN", async () => {
    // El caso de cambio de perfil dentro de la app: el servidor responde 401
    // `PIN_REQUIRED` y la puerta tiene que aparecer aunque ya hubiera un perfil
    // activo (si no, el paso quedaría invisible detrás de la app).
    listUsersMock.mockResolvedValue([BETO, ANA_CON_PIN]);
    getSessionMock.mockResolvedValue(BETO);
    const { result } = await boot();
    await waitFor(() => expect(result.current.currentUserId).toBe("b"));

    openSessionMock.mockRejectedValueOnce(new SessionPinError("pin-required"));
    act(() => result.current.selectUser("a"));

    await waitFor(() => expect(result.current.pinPromptUserId).toBe("a"));
    // El perfil anterior sigue activo: cancelar devuelve a la app tal cual.
    expect(result.current.currentUserId).toBe("b");
  });

  it("cancelar el PIN devuelve a la puerta sin tocar la sesión", async () => {
    listUsersMock.mockResolvedValue([ANA_CON_PIN]);
    const { result } = await boot();
    expect(result.current.pinPromptUserId).toBe("a");

    act(() => result.current.cancelPin());
    expect(result.current.pinPromptUserId).toBeNull();
    expect(result.current.pinFeedback).toBeNull();
    expect(result.current.currentUserId).toBeNull();
    expect(openSessionMock).not.toHaveBeenCalled();
  });
});

describe("useChat · pedir un perfil (V3.77)", () => {
  it("pedir un perfil no lo crea ni abre sesión: deja la solicitud", async () => {
    // La app dejó de crear perfiles: por LAN solo se puede **pedir**, y una
    // solicitud no es un perfil. Si esto abriera sesión, la app se pintaría con
    // un `currentUserId` que no existe y todas las peticiones darían 401.
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
    // El perfil sigue en la lista: la baja la resuelve el webmaster, no la app.
    expect(result.current.users.map((u) => u.id)).toContain("b");
  });
});
