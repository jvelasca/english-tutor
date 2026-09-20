// @vitest-environment jsdom
/**
 * Vitest del hook de apariencia (V3.75.4). El mecanismo de la rampa de niveles
 * es un atributo del `<html>`, así que lo que se fija aquí es justo eso: que
 * `update({ levelScheme })` mueva `data-levels`, que la elección quede en
 * localStorage (inmediata, sin esperar al backend) y que viaje al perfil como
 * `level_scheme`.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { getSettings, saveSettings } from "../api/settings";
import { APPEARANCE_STORAGE_KEY, parseAppearance } from "../utils/appearance";
import { useAppearance } from "./useAppearance";

vi.mock("../api/settings", () => ({
  getSettings: vi.fn(),
  saveSettings: vi.fn(),
}));

const getSettingsMock = vi.mocked(getSettings);
const saveSettingsMock = vi.mocked(saveSettings);

function levelAttribute(): string | null {
  return document.documentElement.getAttribute("data-levels");
}

describe("useAppearance: rampa de niveles (V3.75.4)", () => {
  beforeEach(() => {
    window.localStorage.clear();
    getSettingsMock.mockReset();
    saveSettingsMock.mockReset();
    saveSettingsMock.mockResolvedValue({ settings: {} });
    document.documentElement.removeAttribute("data-levels");
  });

  afterEach(cleanup);

  it("declara el esquema por defecto en el documento", () => {
    getSettingsMock.mockResolvedValue({ settings: {} });
    renderHook(() => useAppearance(null));
    expect(levelAttribute()).toBe("traffic");
  });

  it("cambiar de esquema mueve data-levels, lo guarda y lo persiste por usuario", async () => {
    getSettingsMock.mockResolvedValue({ settings: {} });
    const { result } = renderHook(() => useAppearance("user-1"));

    act(() => result.current.update({ levelScheme: "mono" }));

    expect(levelAttribute()).toBe("mono");
    const stored = window.localStorage.getItem(APPEARANCE_STORAGE_KEY);
    expect(stored).toBeTruthy();
    expect(parseAppearance(stored).levelScheme).toBe("mono");
    await waitFor(() =>
      expect(saveSettingsMock).toHaveBeenCalledWith(
        "user-1",
        expect.objectContaining({ level_scheme: "mono" }),
      ),
    );
  });

  it("hidrata el esquema que declara el perfil", async () => {
    getSettingsMock.mockResolvedValue({
      settings: { level_scheme: "spectrum" },
    });
    renderHook(() => useAppearance("user-2"));

    await waitFor(() => expect(levelAttribute()).toBe("spectrum"));
    expect(
      parseAppearance(window.localStorage.getItem(APPEARANCE_STORAGE_KEY))
        .levelScheme,
    ).toBe("spectrum");
  });

  it("no adopta un esquema desconocido del perfil", async () => {
    // La respuesta del perfil se resuelve **después** del primer pintado: así el
    // hook intenta aplicar de verdad el valor desconocido. Con un `waitFor` sobre la
    // llamada al mock, la lectura podía ocurrir antes de la hidratación y el test
    // pasaba aunque el hook adoptara «arcoiris».
    let resolveSettings!: (value: Awaited<ReturnType<typeof getSettings>>) => void;
    getSettingsMock.mockReturnValue(
      new Promise((resolve) => {
        resolveSettings = resolve;
      }),
    );

    renderHook(() => useAppearance("user-3"));

    await act(async () => {
      resolveSettings({ settings: { level_scheme: "arcoiris" } });
      await Promise.resolve();
    });

    expect(levelAttribute()).toBe("traffic");
  });
});
