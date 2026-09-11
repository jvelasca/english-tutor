// @vitest-environment jsdom
/**
 * Vitest del hook de ruta CEFR seleccionada (V3.48.1): persistencia doble
 * (localStorage inmediato + settings del backend) e hidratación por usuario.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { getSettings, saveSettings } from "../api/settings";
import { SELECTED_ROUTE_STORAGE_KEY } from "../utils/selectedRoute";
import { useSelectedRoute } from "./useSelectedRoute";

vi.mock("../api/settings", () => ({
  getSettings: vi.fn(),
  saveSettings: vi.fn(),
}));

const getSettingsMock = vi.mocked(getSettings);
const saveSettingsMock = vi.mocked(saveSettings);

describe("useSelectedRoute (V3.48.1)", () => {
  beforeEach(() => {
    window.localStorage.clear();
    getSettingsMock.mockReset();
    saveSettingsMock.mockReset();
    saveSettingsMock.mockResolvedValue({ settings: {} });
  });

  afterEach(cleanup);

  it("arranca en Auto cuando no hay nada guardado", () => {
    getSettingsMock.mockResolvedValue({ settings: {} });
    const { result } = renderHook(() => useSelectedRoute(null));
    expect(result.current.selectedLevel).toBeNull();
  });

  it("arranca de localStorage (inmediato, sin esperar al backend)", () => {
    window.localStorage.setItem(SELECTED_ROUTE_STORAGE_KEY, "B1");
    getSettingsMock.mockResolvedValue({ settings: {} });
    const { result } = renderHook(() => useSelectedRoute(null));
    expect(result.current.selectedLevel).toBe("B1");
  });

  it("al seleccionar escribe localStorage y persiste en settings", async () => {
    getSettingsMock.mockResolvedValue({ settings: {} });
    const { result } = renderHook(() => useSelectedRoute("user-1"));

    act(() => result.current.setSelectedLevel("C1"));

    expect(result.current.selectedLevel).toBe("C1");
    expect(window.localStorage.getItem(SELECTED_ROUTE_STORAGE_KEY)).toBe("C1");
    await waitFor(() =>
      expect(saveSettingsMock).toHaveBeenCalledWith("user-1", {
        selected_route_level: "C1",
      }),
    );
  });

  it("Auto borra la selección local y persiste la cadena vacía", async () => {
    window.localStorage.setItem(SELECTED_ROUTE_STORAGE_KEY, "B2");
    getSettingsMock.mockResolvedValue({ settings: {} });
    const { result } = renderHook(() => useSelectedRoute("user-1"));

    act(() => result.current.setSelectedLevel(null));

    expect(window.localStorage.getItem(SELECTED_ROUTE_STORAGE_KEY)).toBeNull();
    await waitFor(() =>
      expect(saveSettingsMock).toHaveBeenCalledWith("user-1", {
        selected_route_level: "",
      }),
    );
  });

  it("hidrata la ruta del perfil cuando el backend declara la clave", async () => {
    getSettingsMock.mockResolvedValue({
      settings: { selected_route_level: "A2" },
    });
    const { result } = renderHook(() => useSelectedRoute("user-2"));

    await waitFor(() => expect(result.current.selectedLevel).toBe("A2"));
    expect(window.localStorage.getItem(SELECTED_ROUTE_STORAGE_KEY)).toBe("A2");
  });

  it("respeta la selección local si el perfil no declara la clave", async () => {
    window.localStorage.setItem(SELECTED_ROUTE_STORAGE_KEY, "C2");
    getSettingsMock.mockResolvedValue({ settings: { other: "x" } });
    const { result } = renderHook(() => useSelectedRoute("user-3"));

    await waitFor(() => expect(getSettingsMock).toHaveBeenCalledWith("user-3"));
    expect(result.current.selectedLevel).toBe("C2");
  });
});
