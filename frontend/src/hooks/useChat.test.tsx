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
  createUser: vi.fn(),
  listUsers: vi.fn(),
  updateUser: vi.fn(),
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

const openSessionMock = vi.mocked(openSession);
const getSessionMock = vi.mocked(getSession);
const listUsersMock = vi.mocked(listUsers);

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
